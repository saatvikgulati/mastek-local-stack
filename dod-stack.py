import subprocess
import os
import getpass
import sys

"""
Author			: Saatvik Gulati
Date:			: 27/03/2023
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
        self.__cont_name='redis'
        self.__user = getpass.getuser()
        self.__cwd = os.getcwd()
        self.__dod_root = os.environ.get('DOD_ROOT')
        self.__RED='\033[0;31m'
        self.__YELLOW='\033[0;33m'
        self.__GREEN = '\033[0;32m'
        self.__BLUE='\033[0;94m'
        self.__NC='\033[0m' # No Color
        # set title of shell
        sys.stdout.write("\x1b]2;DOD-Stack\x07")
        # prints user and pwd
        print(f"You are {self.__user} in {self.__cwd}")

    def vpn_checks(self)->bool:
        """
        Check VPN connection
        """
        try:
            if subprocess.call('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True, stdout=subprocess.DEVNULL) == 0:
                return True

            else:
                print(f'{self.__RED}VPN is off{self.__NC}')
                self.clean_up()
                return False
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            print(f'\n{self.__RED}Exiting script...{self.__NC}')
            self.clean_up()
            exit(1)


    def docker_checks(self)->bool:
        """
        Check if Docker is running and start Redis container if needed
        """
        try:
            # check if docker is on
            if subprocess.call('docker info', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                print(f"{self.__RED}This script uses docker, and it isn't running - please start docker and try again!{self.__NC}")
                self.clean_up()
                exit(1)

            # if docker container found running do nothing
            running_containers = subprocess.check_output(f'docker ps -q -f name={self.__cont_name} -f status=running',shell=True).decode().strip()
            if running_containers:
                return True

            else:
                # Check if Redis container is exited, start if needed
                exited_containers = subprocess.check_output(f'docker ps -q -f name={self.__cont_name} -f status=exited',shell=True).decode().strip()
                if exited_containers:
                    subprocess.run(f'docker start {self.__cont_name}', shell=True, stdout=subprocess.DEVNULL)
                    return True

                else:
                    subprocess.call(f'docker run --name {self.__cont_name} -d -p 127.0.0.1:6379:6379 {self.__cont_name}:latest',shell=True, stdout=subprocess.DEVNULL)
                    return True
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            print(f'\n{self.__RED}Exiting script...{self.__NC}')
            self.clean_up()
            exit(1)


    def ssh_env(self):
        if self.vpn_checks() and self.docker_checks():
                if self.__dod_root: # if vpn and docker is on then only ssh
                    if not LocalStack.is_ssh_running(): # when ssh not running start ssh
                        try:
                            print(f"{self.__BLUE}Please enter the env you want to ssh to:\nprp1\nprd1\ndev2{self.__NC}")
                            __env_name = input().strip().lower()
                            __envs=(
                                'prp1',
                                'prd1',
                                'dev2'
                            )
                            if __env_name in __envs:
                                print(f'{self.__YELLOW}Starting ssh {__env_name}{self.__NC}')
                                subprocess.run(f'ssh -fN {__env_name}', shell=True)
                            else:
                                print(f'{self.__RED}Invalid argument \'{__env_name}\' please mention prp1 or prd1 or dev2 exiting{self.__NC}')
                                self.clean_up()
                                exit(1)

                        except KeyboardInterrupt: # trying to catch if somebody presses ^C
                            print(f'\n{self.__RED}Exiting script...{self.__NC}')
                            self.clean_up()
                            exit(1)

                    else:
                        print(f"{self.__GREEN}ssh is running skipping{self.__NC}") # if ssh session open then skip
                else:
                    print(f"{self.__RED}env variable DOD_ROOT not set{self.__NC}")
                    self.clean_up()
                    exit(1)
    def stack_up(self):
        # final checks
        if self.vpn_checks() and self.docker_checks():
            if self.__dod_root:
                try:
                    os.chdir(f'{self.__dod_root}/dod-stack')
                    subprocess.run('dotenv -e .env tmuxp load dod-stack.yaml', shell=True, check=True, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError as e:
                    print(f"{self.__RED}An error occurred: {e}\ninstall pip dependencies from dod-stack repo:\ncd $DOD_ROOT/dod-stack\npip install -r requirement.txt{self.__NC}")
                except FileNotFoundError: # catching if file or repo doesn't exist or env variable doesn't exist
                    print(f"{self.__RED}No dod-stack repo or file exiting{self.__NC}")
                except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                    print(f'\n{self.__RED}Exiting script...{self.__NC}')

            else:
                print(f"{self.__RED}env variable DOD_ROOT not set{self.__NC}")

    def clean_up(self):
        # cleans up docker and ssh session and tmux session
        if LocalStack.get_tmux_session_id():
            subprocess.call('tmux kill-session -t DOD\ Stack', shell=True)
        subprocess.call(f'kill -9 {str(LocalStack.get_ssh_pid())}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(f'docker container rm -f {self.__cont_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call('docker volume prune -f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def main(self):
        self.ssh_env()
        self.stack_up()
        self.clean_up()

    @staticmethod
    def get_tmux_session_id()->int:
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
    def is_ssh_running()->bool:
        # checks if ssh is running
        return True if LocalStack.get_ssh_pid() else False

    @staticmethod
    def get_ssh_pid()->int:
        # gets ssh process id
        process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if err:
            return None
        return int(out.decode().strip()) if out else None

if __name__=='__main__':
    local=LocalStack()
    local.main()
