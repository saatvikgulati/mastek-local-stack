import subprocess
import os
import getpass
import sys

"""
Author			: Saatvik Gulati
Date:			: 26/03/2023
Description		: To run local stack with the help of this file.
 			: This file checks for vpn, docker and in the end cleansup too
Required		: Requires Linux to run. This will include WSL (Ubuntu preferred)
			: Requires env defination to be upto date in ssh config, .pgpass
Usage Example		: To run the file python dod-stack.py or python3 dod-stack.py
         	      	: Enter env which you want to ssh to
				: prp1
				: prd1
				: dev2
"""
class LocalStack:

    def __init__(self):
        self.cont_name='redis'
        self.user = getpass.getuser()
        self.cwd = os.getcwd()
        self.dod_root = os.environ.get('DOD_ROOT')
        self.RED='\033[0;31m'
        self.YELLOW='\033[0;33m'
        self.GREEN = '\033[0;32m'
        self.BLUE='\033[0;94m'
        self.NC='\033[0m' # No Color
        # set title of shell
        sys.stdout.write("\x1b]2;DOD-Stack\x07")
        # prints user and pwd
        print(f"You are {self.user} in {self.cwd}")

    def vpn_checks(self)->bool:
        """
        Check VPN connection
        """
        try:
            if subprocess.call('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True, stdout=subprocess.DEVNULL) == 0:
                return True

            else:
                print(f'{self.RED}VPN is off{self.NC}')
                self.clean_up()
                return False
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            print(f'\n{self.RED}Exiting script...{self.NC}')
            self.clean_up()
            exit(1)


    def docker_checks(self)->bool:
        """
        Check if Docker is running and start Redis container if needed
        """
        try:
            # check if docker is on
            if subprocess.call('docker info', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                print(f"{self.RED}This script uses docker, and it isn't running - please start docker and try again!{self.NC}")
                self.clean_up()
                exit(1)

            # if docker container found running do nothing
            running_containers = subprocess.check_output(f'docker ps -q -f name={self.cont_name} -f status=running',shell=True).decode().strip()
            if running_containers:
                return True

            else:
                # Check if Redis container is exited, start if needed
                exited_containers = subprocess.check_output(f'docker ps -q -f name={self.cont_name} -f status=exited',shell=True).decode().strip()
                if exited_containers:
                    subprocess.run(f'docker start {self.cont_name}', shell=True, stdout=subprocess.DEVNULL)
                    return True

                else:
                    subprocess.call(f'docker run --name {self.cont_name} -d -p 127.0.0.1:6379:6379 {self.cont_name}:latest',shell=True, stdout=subprocess.DEVNULL)
                    return True
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            print(f'\n{self.RED}Exiting script...{self.NC}')
            self.clean_up()
            exit(1)


    def ssh_env(self):
        if self.vpn_checks() and self.docker_checks():
            if self.dod_root: # if vpn and docker is on then only ssh
                if not LocalStack.is_ssh_running(): # when ssh not running start ssh
                    try: 
                        print(f"{self.BLUE}Please enter the env you want to ssh to:\nprp1\nprd1\ndev2{self.NC}")
                        env_name = input().strip().lower()
                        envs=[
                            'prp1',
                            'prd1',
                            'dev2'
                        ]
                        if env_name in envs:
                            print(f'{self.YELLOW}Starting ssh {env_name}{self.NC}')
                            subprocess.run(f'ssh -fN {env_name}', shell=True)
                        else:
                            print(f'{self.RED}Invalid argument \'{env_name}\' please mention prp1 or prd1 or dev2 exiting{self.NC}')
                            self.clean_up()
                            exit(1)

                    except KeyboardInterrupt: # trying to catch if somebody presses ^C
                        print(f'\n{self.RED}Exiting script...{self.NC}')
                        self.clean_up()
                        exit(1)

                else:
                    print(f"{self.GREEN}ssh is running skipping{self.NC}") # if ssh session open then skip
            else:
                print(f"{self.RED}env variable DOD_ROOT not set{self.NC}")
                self.clean_up()
                exit(1)
    def stack_up(self):
        # final checks
        if self.vpn_checks() and self.docker_checks():
            if self.dod_root:
                try:
                    os.chdir(f'{self.dod_root}/dod-stack')
                    subprocess.run('dotenv -e .env tmuxp load dod-stack.yaml', shell=True, check=True, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError as e:
                    print(f"{self.RED}An error occurred: {e}\ninstall pip dependencies from dod-stack repo:\ncd $DOD_ROOT/dod-stack\npip install -r requirement.txt{self.NC}")
                except FileNotFoundError: # catching if file or repo doesn't exist or env variable doesn't exist
                    print(f"{self.RED}No dod-stack repo or file exiting{self.NC}")
                except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                    print(f'\n{self.RED}Exiting script...{self.NC}')
            else:
                print(f"{self.RED}env variable DOD_ROOT not set{self.NC}")

    def clean_up(self):
        # cleans up docker and ssh session and tmux session
        if LocalStack.get_tmux_session_id():
            subprocess.call('tmux kill-session -t DOD\ Stack', shell=True)
        subprocess.call(f'kill -9 {str(LocalStack.get_ssh_pid())}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(f'docker container rm -f {self.cont_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call('docker volume prune -f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def main(self):
        self.ssh_env()
        self.stack_up()
        self.clean_up()

    @staticmethod
    def get_tmux_session_id():
        # Run the `tmux ls` command and capture the output
        try:
            output = subprocess.check_output('tmux ls', shell=True, stderr=subprocess.DEVNULL)

            # Decode the output from bytes to string
            output = output.decode('utf-8')

            # Split the output into lines
            lines = output.strip().split('\n')

            # Parse the session ID from the first line of output
            if len(lines) > 0:
                session_id = lines[0].split(':')[0]
                return session_id
        except subprocess.CalledProcessError:
            # If no session is found, return None
            return None

    @staticmethod
    def is_ssh_running():
        # checks if ssh is running
        return True if LocalStack.get_ssh_pid() else False

    @staticmethod
    def get_ssh_pid():
        # gets ssh process id
        process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if err:
            return None
        return int(out.decode().strip()) if out else None

if __name__=='__main__':
    local=LocalStack()
    local.main()
