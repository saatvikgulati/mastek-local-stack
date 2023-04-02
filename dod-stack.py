import subprocess
import os
import getpass
import sys
import logging
import time
"""
Author: Saatvik Gulati
Date: 2/04/2023
Description: Runs a local stack and performs necessary checks.
Requirements: Linux operating system, with env definitions updated in ssh config and .pgpass.
Usage Example:
  To run the file, use the command 'python dod-stack.py' or 'python3 dod-stack.py' or dod-stack.py if alias is set.
  When prompted, enter the env you want to ssh to (prp1, prd1, or dev2).

"""
class LocalStack:

    def __init__(self):
        self.__cont_name='redis'
        self.__user = getpass.getuser()
        self.__cwd = os.getcwd()
        self.__dod_root = os.environ.get('DOD_ROOT')
        self.__RED='\033[0;31m'
        self.__AMBER='\033[38;5;208m'
        self.__GREEN = '\033[0;32m'
        self.__BLUE='\033[0;94m'
        self.__NC='\033[0m' # No Color
        self.__VIOLET='\033[1;35m'
        self.__logger=self.setup_logger()
        # set title of shell
        sys.stdout.write("\x1b]2;DOD-Stack\x07")
        # prints user and pwd
        self.__logger.debug(f"{self.__BLUE}You are {self.__user} in {self.__cwd}{self.__NC}")

    def setup_logger(self) -> logging.Logger:
        __logger = logging.getLogger('LocalStack')
        # Setting logging colors
        __log_colors = {
            logging.DEBUG: self.__BLUE,
            logging.INFO: self.__GREEN,
            logging.WARNING: self.__AMBER,
            logging.ERROR: self.__RED,
            logging.CRITICAL: self.__RED
        }
        __log_format = '%(asctime)s - %(levelname)s : %(message)s'
        __date_format = '%d-%m-%Y %H:%M:%S'
        # Set level and message color
        for level, color in __log_colors.items():
            logging.addLevelName(level, color + logging.getLevelName(level) + self.__NC)

        __formatter = logging.Formatter(fmt=__log_format, datefmt=__date_format)
        # Set different colors for asctime based on the logging level
        __formatter.formatTime = lambda __record, __date_fmt=__date_format: f"{__log_colors[__record.levelno]}{time.strftime(__date_fmt, time.localtime(__record.created))}{self.__NC}"
        __logger.setLevel(logging.DEBUG)
        __console_handler = logging.StreamHandler(sys.stdout)
        __logger.addHandler(__console_handler)
        __console_handler.setFormatter(__formatter)
        return __logger

    def vpn_checks(self)->bool:
        """
        Check VPN connection
        """
        try:
            if subprocess.run('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True, stdout=subprocess.DEVNULL).returncode == 0:
                return True

            else:
                self.__logger.critical(f'{self.__RED}VPN is off{self.__NC}')
                self.clean_up()
                return False
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            self.__logger.error(f'\n{self.__RED}Exiting script...{self.__NC}')
            self.clean_up()
            exit(1)


    def docker_checks(self)->bool:
        """
        Check if Docker is running and start Redis container if needed
        """
        try:
            # check if docker is on
            if subprocess.run('docker info', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                self.__logger.critical(f"{self.__RED}This script uses docker, and it isn't running - please start docker and try again!{self.__NC}")
                self.clean_up()
                exit(1)

            # if docker container found running do nothing
            __running_containers = subprocess.check_output(f'docker ps -q -f name={self.__cont_name} -f status=running',shell=True).decode().strip()
            if __running_containers:
                return True

            else:
                # Check if Redis container is exited, start if needed
                __exited_containers = subprocess.check_output(f'docker ps -q -f name={self.__cont_name} -f status=exited',shell=True).decode().strip()
                if __exited_containers:
                    subprocess.run(f'docker start {self.__cont_name}', shell=True, stdout=subprocess.DEVNULL)
                    return True

                else:
                    subprocess.run(f'docker run --name {self.__cont_name} -d -p 127.0.0.1:6379:6379 {self.__cont_name}:latest',shell=True, stdout=subprocess.DEVNULL)
                    return True
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            self.__logger.error(f'\n{self.__RED}Exiting script...{self.__NC}')
            self.clean_up()
            exit(1)


    def ssh_env(self):
        if self.vpn_checks() and self.docker_checks():
                if self.__dod_root: # if vpn and docker is on then only ssh
                    if not LocalStack.is_ssh_running(): # when ssh not running start ssh
                        try:
                            __env_name = input(f"{self.__VIOLET}Please enter the env you want to ssh to:\nprp1\nprd1\ndev2\n{self.__NC}").strip().lower()
                            __env_s=(
                                'prp1',
                                'prd1',
                                'dev2'
                            )
                            if __env_name in __env_s:
                                self.__logger.info(f'{self.__GREEN}Starting ssh {__env_name}{self.__NC}')
                                subprocess.run(f'ssh -fN {__env_name}', shell=True)
                            else:
                                self.__logger.error(f'{self.__RED}Invalid argument \'{__env_name}\' please mention prp1 or prd1 or dev2 exiting{self.__NC}')
                                self.clean_up()
                                exit(1)

                        except KeyboardInterrupt: # trying to catch if somebody presses ^C
                            self.__logger.error(f'\n{self.__RED}Exiting script...{self.__NC}')
                            self.clean_up()
                            exit(1)

                    else:
                        self.__logger.warning(f"{self.__AMBER}ssh is running skipping{self.__NC}") # if ssh session open then skip
                else:
                    self.__logger.error(f"{self.__RED}env variable DOD_ROOT not set{self.__NC}")
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
                    self.__logger.error(f"{self.__RED}An error occurred: {e}\ninstall pip dependencies from dod-stack repo:\ncd $DOD_ROOT/dod-stack\npip install -r requirement.txt{self.__NC}")
                except FileNotFoundError: # catching if file or repo doesn't exist or env variable doesn't exist
                    self.__logger.error(f"{self.__RED}No dod-stack repo or file exiting{self.__NC}")
                except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                    self.__logger.error(f'\n{self.__RED}Exiting script...{self.__NC}')

            else:
                self.__logger.error(f"{self.__RED}env variable DOD_ROOT not set{self.__NC}")

    def clean_up(self):
        # cleans up docker and ssh session and tmux session
        if LocalStack.get_tmux_session_id():
            subprocess.run('tmux kill-session -t DOD\ Stack', shell=True)
        subprocess.run(f'kill -9 {str(LocalStack.get_ssh_pid())}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f'docker container rm -f {self.__cont_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run('docker volume prune -f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def main(self):
        self.ssh_env()
        self.stack_up()
        self.clean_up()

    @staticmethod
    def get_tmux_session_id()->int:
        # Run the `tmux ls` command and capture the output
        try:
            __output = subprocess.check_output('tmux ls', shell=True, stderr=subprocess.DEVNULL)

            # Decode the output from bytes to string
            __output = __output.decode('utf-8')

            # Split the output into lines
            __lines = __output.strip().split('\n')

            # Parse the session ID from the first line of output
            if len(__lines) > 0:
                __session_id = __lines[0].split(':')[0]
                return __session_id
        except subprocess.CalledProcessError:
            # If no session is found, return None
            return 0

    @staticmethod
    def is_ssh_running()->bool:
        # checks if ssh is running
        return True if LocalStack.get_ssh_pid() else False

    @staticmethod
    def get_ssh_pid()->int:
        # gets ssh process id
        __process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        __out, __err = __process.communicate()
        if __err:
            return 0
        return int(__out.decode().strip()) if __out else None

if __name__=='__main__':
    local=LocalStack()
    local.main()
