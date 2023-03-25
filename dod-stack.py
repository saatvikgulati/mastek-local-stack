import subprocess
import os
import getpass
"""
Author			: Saatvik Gulati
Date:			: 25/03/2023
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
        self.RED='\033[0;31m'
        self.YELLOW='\033[0;33m'
        self.BLUE='\033[0;94m'
        self.NC='\033[0m' # No Color
        print("You are {} in {}".format(self.user,self.cwd))

    def vpn_checks(self)->bool:
        """
        Check VPN connection
        """
        if subprocess.run('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            return True

        else:
            print('{}VPN is off{}'.format(self.RED, self.NC))
            self.clean_up()
            return False

    def docker_checks(self)->bool:
        """
        Check if Docker is running and start Redis container if needed
        """
        if subprocess.run('docker info', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            print("{}This script uses docker, and it isn't running - please start docker and try again!{}".format(self.RED, self.NC))
            self.clean_up()
            exit(1)

        # Check if Redis container is running, start if needed
        running_containers = subprocess.run('docker ps -q -f name={} -f status=running'.format(self.cont_name),shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
        if running_containers:
            return True

        else:
            exited_containers = subprocess.run('docker ps -q -f name={} -f status=exited'.format(self.cont_name),shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
            if exited_containers:
                subprocess.run(['docker', 'start', self.cont_name], stdout=subprocess.DEVNULL)
                return True

            else:
                subprocess.run('docker run --name {} -d -p 127.0.0.1:6379:6379 {}:latest'.format(self.cont_name,self.cont_name),shell=True, stdout=subprocess.DEVNULL)
                return True

    def ssh_env(self):
        if self.vpn_checks() and self.docker_checks():
            if not LocalStack.is_ssh_running():
                try:
                    print('{}Please enter the env you want to ssh to- prp1 or prd1 or dev2:{}'.format(self.BLUE, self.NC))
                    env_name = input().strip().lower()

                except KeyboardInterrupt:
                    print('\n{}Exiting script...{}'.format(self.RED, self.NC))
                    self.clean_up()
                    exit(1)

                if env_name == 'prp1':
                    print('{}Starting ssh {}{}'.format(self.YELLOW,env_name,self.NC))
                    p=subprocess.Popen('ssh -fN {}'.format(env_name), shell=True)
                    p.wait()

                elif env_name == 'prd1':
                    print('{}Starting ssh {}{}'.format(self.YELLOW,env_name,self.NC))
                    p=subprocess.Popen('ssh -fN {}'.format(env_name), shell=True)
                    p.wait()
                elif env_name == 'dev2':
                    print('{}Starting ssh {}{}'.format(self.YELLOW, env_name,self.NC))
                    p=subprocess.Popen('ssh -fN {}'.format(env_name), shell=True)
                    p.wait()
                else:
                    print('{}Invalid argument \'{}\' please mention prp1 or prd1 or dev2 exiting{}'.format(self.RED, self.env_name,self.NC))
                    self.clean_up()
                    exit(1)
            else:
                pass
        else:
            self.clean_up()
            exit(1)
    def stack_up(self):
        # final checks
        if self.vpn_checks() and self.docker_checks() and LocalStack.is_ssh_running():
            dod_root = os.environ.get('DOD_ROOT')
            os.chdir('{}/dod-stack'.format(dod_root))
            p=subprocess.Popen('dotenv -e .env tmuxp load dod-stack.yaml', shell=True)
            p.wait()
        else:
            self.clean_up()
            exit(1)
    def clean_up(self):
        subprocess.call('kill -9 {}'.format(str(LocalStack.get_ssh_pid())), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call('docker container rm -f {}'.format(self.cont_name), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call('docker volume prune -f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def is_ssh_running():
        return True if LocalStack.get_ssh_pid() else False

    @staticmethod
    def get_ssh_pid():
        process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if err:
            return None
        return int(out.decode().strip()) if out else None

if __name__=='__main__':
    local=LocalStack()
    local.ssh_env()
    local.stack_up()
    local.clean_up()
