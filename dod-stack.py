import subprocess
import os
import getpass
import sys
import logging
import time

try:
    from tqdm.auto import tqdm
except ImportError:
    subprocess.run('pip install tqdm -q', shell=True)
    from tqdm.auto import tqdm

"""
Author: Saatvik Gulati
Date: 25/07/2023
Description: Runs a local stack and performs necessary checks.
Requirements: Linux operating system, with env definitions updated in ssh config and .pgpass.
              Requires dev2 env to be up to connect to any env
Usage Example:
    To run the file, use the command 'python dod-stack.py' or 'python3 dod-stack.py' or dod-stack.py if alias is set.
    When prompted, enter the env you want to ssh to (prp1, prd1, or dev2).

"""


class LocalStack:

    def __init__(self):
        self.__cont_name = 'redis'
        self.__user = getpass.getuser()
        self.__cwd = os.getcwd()
        self.__dod_root = os.environ.get('DOD_ROOT')
        self.__colors = {
            'RED': '\033[0;31m',
            'AMBER': '\033[38;5;208m',
            'GREEN': '\033[0;32m',
            'BLUE': '\033[0;94m',
            'NC': '\033[0m',
            'VIOLET': '\033[1;35m'
        }
        self.__logger = self.setup_logger()
        self.__env_name = 'dev2'
        self.__environments = {
            'prd1': 'https://dod-dashboard-prd1-kube1.service.pr.iptho.co.uk',
            'prp1': 'https://dod-dashboard-prp1-kube1.service.np.iptho.co.uk',
            'dev2': 'https://dod-dashboard-ho-it-dev2-i-cw-ops-kube1.service.np.iptho.co.uk'
        }

    def setup_logger(self) -> logging.Logger:
        """
        Setting up logging
        :return: formatted logger
        :rtype: logging.Logger
        """
        __logger = logging.getLogger(__name__)
        # Setting logging colors
        __log_colors = {
            logging.DEBUG: self.__colors["BLUE"],
            logging.INFO: self.__colors["GREEN"],
            logging.WARNING: self.__colors["AMBER"],
            logging.ERROR: self.__colors["RED"],
            logging.CRITICAL: self.__colors["RED"],
        }
        __log_format = '%(asctime)s - %(levelname)s : %(message)s'
        __date_format = '%d-%m-%Y %H:%M:%S'
        # Set level and message color
        for level, color in __log_colors.items():
            logging.addLevelName(level, color + logging.getLevelName(level) + self.__colors["NC"])

        __formatter = logging.Formatter(fmt=__log_format, datefmt=__date_format)
        # Set different colors for asctime based on the logging level
        __formatter.formatTime = lambda __record, __date_fmt=__date_format: f'{__log_colors[__record.levelno]}{time.strftime(__date_fmt, time.localtime(__record.created))}{self.__colors["NC"]}'
        __logger.setLevel(logging.DEBUG)
        __console_handler = logging.StreamHandler(sys.stdout)
        __logger.addHandler(__console_handler)
        __console_handler.setFormatter(__formatter)
        return __logger

    def check_env(self):
        """
        Checks if the environment is up or not
        :return: True if environment is active
        :rtype: bool
        :exception subprocess.TimeoutExpired: if the curl command times out
        :exception KeyboardInterrupt: catching ^c
        """

        try:
            if self.__env_name in self.__environments:
                __url = self.__environments[self.__env_name]
                with tqdm(total=100, desc=f'{self.__colors["BLUE"]}Checking {self.__env_name} environment',
                          bar_format='{l_bar}{bar:10}{r_bar}') as pbar:
                    __output = subprocess.run(f'curl -s -I {__url}', timeout=5, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    __status_code = int(__output.stdout.decode('utf-8').split()[1])
                    if __status_code == 502 or __status_code == 404 or __status_code == 503:
                        pbar.set_description(f'{self.__colors["RED"]}Checking {self.__env_name} environment (failed)')
                        self.clean_up()
                        sys.exit(1)
                    else:
                        pbar.update(50)
                        time.sleep(1)
                        pbar.update(50)
                        pbar.set_description(f'{self.__colors["GREEN"]}Checking {self.__env_name} environment (success)')
                        return True
        except subprocess.TimeoutExpired:
            tqdm.write(f'\n{self.__colors["GREEN"]}You are not SC cleared to access prd{self.__colors["NC"]}')
            self.clean_up()
            sys.exit(1)
        except KeyboardInterrupt:
            tqdm.write(f'\n{self.__colors["RED"]}Exiting script...{self.__colors["NC"]}')
            self.clean_up()
            sys.exit(1)
        if LocalStack.is_ssh_running():
            return self.__env_name

    def vpn_checks(self) -> bool:
        """
        Constantly Checks VPN connection
        :return: true if vpn on
        :rtype: bool
        :exception KeyboardInterrupt: catching ^c
        """
        while True:
            try:
                if subprocess.run('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True, stdout=subprocess.DEVNULL).returncode == 0:
                    return True

                else:
                    self.__logger.critical(f'{self.__colors["RED"]}VPN is off retrying in 5 seconds{self.__colors["NC"]}')
                    time.sleep(5)
                    continue
            except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                self.__logger.error(f'\n{self.__colors["RED"]}Exiting script...{self.__colors["NC"]}')
                self.clean_up()
                sys.exit(1)

    def docker_checks(self) -> bool:
        """
        Constantly Check if Docker is running and start Redis container if needed
        :return: true is docker on
        :rtype: bool
        :exception KeyboardInterrupt: catching ^c
        """
        while True:
            try:
                # check if docker is on
                if subprocess.run('docker info', shell=True, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).returncode != 0:
                    self.__logger.critical(
                        f'{self.__colors["RED"]}This script uses docker, and it isn\'t running - please start docker retrying again in 5 seconds{self.__colors["NC"]}')
                    time.sleep(5)
                    continue

                # if docker container found running do nothing
                elif subprocess.run(f'docker ps -q -f name={self.__cont_name} -f status=running', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE).stdout:
                    return True

                elif subprocess.run(f'docker ps -q -f name={self.__cont_name} -f status=exited', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE).stdout:
                    # Check if Redis container is exited, start if needed
                    subprocess.run(f'docker start {self.__cont_name}', shell=True, stdout=subprocess.DEVNULL)
                    return True

                else:
                    subprocess.run(f'docker run --name {self.__cont_name} -d -p 127.0.0.1:6379:6379 {self.__cont_name}:latest', shell=True, stdout=subprocess.DEVNULL)
                    return True
            except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                self.__logger.error(f'\n{self.__colors["RED"]}Exiting script...{self.__colors["NC"]}')
                self.clean_up()
                sys.exit(1)

    def ssh_env(self):
        """
        Constantly checks for ssh params
        :rtype: void or exit
        :exception KeyboardInterrupt: catching ^c
        """
        while True:
            if self.vpn_checks() and self.check_env() and self.docker_checks():  # if vpn and docker is on then only ssh
                if self.__dod_root:
                    if not LocalStack.is_ssh_running():  # when ssh not running start ssh
                        try:
                            valid = False
                            while not valid:
                                self.__env_name = input(f'{self.__colors["VIOLET"]}Please enter the env you want to ssh to:\nprp1\nprd1\ndev2\n{self.__colors["NC"]}').strip().lower()

                                if self.__env_name in self.__environments and self.check_env():
                                    valid = True
                                    self.__logger.info(
                                        f'{self.__colors["GREEN"]}Starting ssh {self.__env_name}{self.__colors["NC"]}')
                                    subprocess.run(f'ssh -fN {self.__env_name}', shell=True)
                                    if LocalStack.is_ssh_running():
                                        break
                                else:
                                    self.__logger.error(
                                        f'{self.__colors["RED"]}Invalid argument \'{self.__env_name}\' please mention prp1 or prd1 or dev2 pls enter again{self.__colors["NC"]}')
                                    continue

                        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                            self.__logger.error(f'\n{self.__colors["RED"]}Exiting script...{self.__colors["NC"]}')
                            self.clean_up()
                            sys.exit(1)

                    else:
                        self.__logger.warning(
                            f'{self.__colors["AMBER"]}ssh is running skipping{self.__colors["NC"]}')  # if ssh session open then skip
                        break
                else:
                    self.__logger.error(f'{self.__colors["RED"]}env variable DOD_ROOT not set{self.__colors["NC"]}')
                    self.clean_up()
                    sys.exit(1)

    def stack_up(self):
        """
        final checks
        :exception subprocess.CalledProcessError: package error
        :exception FileNotFoundError: repo or file not found
        :exception KeyboardInterrupt: catching ^c
        :rtype: void
        """
        if self.vpn_checks() and self.docker_checks():
            if self.__dod_root:
                try:
                    os.chdir(f'{self.__dod_root}/dod-stack')
                    subprocess.run('dotenv -e .env tmuxp load dod-stack.yaml', shell=True, check=True,
                                   stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError as e:
                    self.__logger.error(f'{self.__colors["RED"]}An error occurred: {e}\ninstall pip dependencies from dod-stack repo:\ncd $DOD_ROOT/dod-stack\npip install -r requirement.txt{self.__colors["NC"]}')
                except FileNotFoundError:  # catching if file or repo doesn't exist or env variable doesn't exist
                    self.__logger.error(f'{self.__colors["RED"]}No dod-stack repo or file exiting{self.__colors["NC"]}')
                except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                    self.__logger.error(f'\n{self.__colors["RED"]}Exiting script...{self.__colors["NC"]}')

            else:
                self.__logger.error(f'{self.__colors["RED"]}env variable DOD_ROOT not set{self.__colors["NC"]}')

    def clean_up(self):
        """
        cleans up docker and ssh session and tmux session
        :rtype: void
        """

        if LocalStack.get_tmux_session_id():
            subprocess.run('tmux kill-session -t DOD\ Stack', shell=True)
        subprocess.run(f'kill -9 {str(LocalStack.get_ssh_pid())}', shell=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        subprocess.run(f'docker container rm -f {self.__cont_name} && docker volume prune -f', shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def update_pip() -> None:
        """updates pip
        :rtype: None
        """
        subprocess.run('pip install --upgrade pip -q', shell=True)

    def main(self):
        """
        Main function for program
        :rtype: void
        """
        if sys.platform == 'linux':
            # set title of shell
            sys.stdout.write("\x1b]2;DOD-Stack\x07")
            # prints user and pwd
            self.__logger.debug(f'{self.__colors["BLUE"]}You are {self.__user} in {self.__cwd}{self.__colors["NC"]}')
            LocalStack.update_pip()
            self.ssh_env()
            self.stack_up()
            self.clean_up()
        else:
            self.__logger.error('This script only works on Linux machines or WSL.')

    @staticmethod
    def get_tmux_session_id() -> int:
        """
        get tmux session id
        :return: tmux session id
        :rtype: int
        :exception subprocess.CallProcessError: no session exception
        """
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
            # If no session is found, return 0
            return 0

    @staticmethod
    def is_ssh_running() -> bool:
        """
        checks if ssh is running
        :return: ssh running true or false
        :rtype: bool
        """
        return True if LocalStack.get_ssh_pid() else False

    @staticmethod
    def get_ssh_pid() -> int:
        """
        gets ssh process id
        :return: ssh process id
        :rtype: int
        """
        __process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        __out, __err = __process.communicate()
        if __err:
            return 0
        return int(__out.decode().strip()) if __out else None


if __name__ == '__main__':
    local = LocalStack()
    local.main()
