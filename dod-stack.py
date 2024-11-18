#!/usr/bin/env python
import subprocess
import os
import getpass
import sys
import logging
import time
import concurrent.futures as cf
from typing import List

try:
    from tqdm.auto import tqdm
except ImportError:
    subprocess.run('pip install tqdm -q', shell=True)
    from tqdm.auto import tqdm

"""
Author: Saatvik Gulati
Date: 18/11/2024
Description: Runs a local stack and performs necessary checks.
Requirements: Linux operating system, with env definitions updated in ssh config and .pgpass.
              Requires dev2 env to be up to connect to any env
Usage Example:
    To run the file, use the command 'python dod-stack.py' or 'python3 dod-stack.py' or dod-stack.py if alias is set.
    When prompted, enter the env you want to ssh to (prp1, prd1, or dev2).

"""


class LocalStack:

    def __init__(self):
        self.cont_name = 'redis'
        self.user = getpass.getuser()
        self.cwd = os.getcwd()
        self.dod_root = os.environ.get('DOD_ROOT')
        self.colors = {
            "RED": '\033[0;31m',
            "AMBER": '\033[38;5;208m',
            "GREEN": '\033[0;32m',
            "BLUE": '\033[0;94m',
            "NC": '\033[0m',  # No Color
            "VIOLET": '\033[1;35m'
        }
        self.logger = self.setup_logger()
        self.env_name = 'dev2'
        self.environments = {
            'prp1': 'https://dod-dashboard-prp1-kube1.service.np.iptho.co.uk',
            'dev2': 'https://dod-dashboard-ho-it-dev2-i-cw-ops-kube1.service.np.iptho.co.uk',
            'dev1': 'https://dod-dashboard-ho-it-dev1-i-cw-ops-kube1.service.np.iptho.co.uk'
        }

    def get_valid_ports(self) -> List:
        """
        fetches all the ports from config
        fetches all the ports from config
        :rtype: List
        :return: return a List of valid ports
        """
        ssh_config_path = os.path.expanduser('~/.ssh/config')
        valid_ports = []

        if os.path.exists(ssh_config_path):
            with open(ssh_config_path, 'r') as ssh_config_file:
                lines = ssh_config_file.readlines()
                inside_host_block = False
                local_forwards = []

                for line in lines:
                    line = line.strip()
                    if line.startswith('Host '):
                        if inside_host_block and self.env_name in host_line:
                            valid_ports.extend(local_forwards)
                            local_forwards = []
                        host_line = line
                        if self.env_name in line:
                            inside_host_block = True
                        else:
                            inside_host_block = False
                    elif inside_host_block and line.startswith('LocalForward '):
                        tokens = line.split()
                        local_forward_port = int(tokens[1])
                        local_forwards.append(local_forward_port)

                # Add local forwards from the last host block if needed
                if inside_host_block and self.env_name in host_line:
                    valid_ports.extend(local_forwards)
        else:
            self.logger.error(f'{self.colors["RED"]}~/.ssh/config file not found{self.colors["NC"]}')
            self.clean_up()
            sys.exit(1)

        return valid_ports

    def compare_pgpass_and_env(self, env_port) -> bool:
        """
        Compare .pgpass and .env
        :param env_port: Port from .env
        :rtype: bool
        :return: True if port found in .pgpass, False otherwise
        """
        pgpass_file_path = os.path.expanduser("~/.pgpass")

        if not os.path.exists(pgpass_file_path):
            self.logger.error(f'{self.colors["RED"]}~/.pgpass file not found{self.colors["NC"]}')
            self.clean_up()
            sys.exit(1)

        with open(pgpass_file_path, 'r') as pgpass_file:
            for line in pgpass_file:
                fields = line.strip().split(':')
                if len(fields) >= 5:
                    pgpass_host = fields[0]
                    pgpass_port = int(fields[1])

                    # Compare only if the host is "localhost" and port matches the env_port
                    if pgpass_host == 'localhost' and pgpass_port == env_port:
                        self.logger.info(
                            f'{self.colors["GREEN"]}Port {pgpass_port} found in .pgpass{self.colors["NC"]}')
                        return True

        self.logger.error(f'{self.colors["RED"]}Port {env_port} not found in .pgpass{self.colors["NC"]}')
        self.clean_up()
        sys.exit(1)

    def check_pgpass_env_ssh(self):
        """
        Goes into .env and checks with the ssh config if it's up-to-date
        :rtype: None
        :return: null
        """
        try:
            os.chdir(f'{self.dod_root}/dod-stack')
        except FileNotFoundError:
            self.logger.error(f'{self.colors["RED"]}No dod-stack repo or file exiting{self.colors["NC"]}')
            self.clean_up()
            sys.exit(1)

        if not os.path.exists(f'{self.dod_root}/dod-stack/.env'):
            self.logger.error(
                f'{self.colors["RED"]} {self.dod_root}/dod-stack/.env file not found{self.colors["NC"]}')
            self.clean_up()
            sys.exit(1)

        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()  # Remove leading/trailing whitespaces

                # Skip comments and empty lines
                if line.startswith('#') or not line:
                    continue

                if 'DATABASE_PORT_OPS_DOD_MART' in line:
                    env_port = int(line.split('=')[1].strip())
                    self.logger.info(f'{self.colors["GREEN"]}Found line: {line}{self.colors["NC"]}')
                    self.logger.info(f'{self.colors["GREEN"]}Extracted port: {env_port}{self.colors["NC"]}')

                    valid_ports = self.get_valid_ports()

                    if env_port in valid_ports:
                        if self.compare_pgpass_and_env(env_port):
                            self.logger.info(
                                f'{self.colors["GREEN"]}Valid port found {env_port} in SSH config, .env, and .pgpass{self.colors["NC"]}')
                            return True
                        else:
                            self.logger.error(
                                f'{self.colors["RED"]}Port in .env does not match .pgpass {env_port}{self.colors["NC"]}')
                            self.clean_up()
                            sys.exit(1)
                    else:
                        self.logger.error(
                            f'{self.colors["RED"]}Port in .env does not match any valid ports{self.colors["NC"]}')
                        self.clean_up()
                        sys.exit(1)

                    break
            else:
                self.logger.error(
                    f'{self.colors["RED"]}DATABASE_PORT_OPS_DOD_MART not found in .env{self.colors["NC"]}')
                self.clean_up()
                sys.exit(1)

    def setup_logger(self) -> logging.Logger:
        """
        Setting up logging
        :return: formatted logger
        :rtype: logging.Logger
        """
        logger = logging.getLogger(__name__)
        # Setting logging colors
        log_colors = {
            logging.DEBUG: self.colors["BLUE"],
            logging.INFO: self.colors["GREEN"],
            logging.WARNING: self.colors["AMBER"],
            logging.ERROR: self.colors["RED"],
            logging.CRITICAL: self.colors["RED"]
        }
        log_format = '%(asctime)s - %(levelname)s : %(message)s'
        date_format = '%d-%m-%Y %H:%M:%S'
        # Set level and message color
        for level, color in log_colors.items():
            logging.addLevelName(level, color + logging.getLevelName(level) + self.colors["NC"])

        formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
        # Set different colors for asctime based on the logging level
        formatter.formatTime = lambda record, date_fmt=date_format: f'{log_colors[record.levelno]}{time.strftime(date_fmt, time.localtime(record.created))}{self.colors["NC"]}'
        logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(console_handler)
        console_handler.setFormatter(formatter)
        return logger

    @staticmethod
    def update_pip():
        """
        Update pip
        :rtype: void
        """
        subprocess.run('pip install --upgrade pip -q', shell=True)

    def check_env(self):
        """
        Checks if the environment is up or not
        :return: True if environment is active
        :rtype: bool
        :exception subprocess.TimeoutExpired: if the curl command times out
        :exception KeyboardInterrupt: catching ^c
        """

        try:
            if self.env_name in self.environments:
                url = self.environments[self.env_name]
                with tqdm(total=100, desc=f'{self.colors["BLUE"]}Checking {self.env_name} environment',
                          bar_format='{l_bar}{bar:10}{r_bar}') as pbar:
                    output = subprocess.run(f'curl -s -I {url}', timeout=10, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    if output.returncode == 0:
                        pbar.update(50)
                        time.sleep(1)
                        pbar.update(50)
                        pbar.set_description(f'{self.colors["GREEN"]}Checking {self.env_name} environment (success)')
                        return True
                    else:
                        pbar.set_description(f'{self.colors["RED"]}Checking {self.env_name} environment (failed)')
                        raise Exception(f'{self.colors["RED"]}Checking {self.env_name} environment (failed)')
        except KeyboardInterrupt:
            raise

    def run_checks(self):
        try:
            with cf.ThreadPoolExecutor(max_workers=3) as ex:
                futures = (
                    ex.submit(self.vpn_checks),
                    ex.submit(self.check_env),
                    ex.submit(self.docker_checks)
                )
                vpn_pass = futures[0].result(timeout = 15)
                check_pass = futures[1].result(timeout = 15)
                docker_pass = futures[2].result(timeout = 15)
            if vpn_pass and check_pass and docker_pass:
                return True
        except Exception as e:
            self.logger.error(e)
            return False
        except KeyboardInterrupt:
            self.logger.error(f'\n{self.colors["RED"]}Exiting script...{self.colors["NC"]}')
            for future in futures:
                if future.running():
                    future.cancel()
            self.clean_up()
            sys.exit(1)
        except cf.TimeoutError:
            return False

    def vpn_checks(self) -> bool:
        """
        Constantly Checks VPN connection
        :return: true if vpn on
        :rtype: bool
        :exception KeyboardInterrupt: catching ^c
        """
        try:
            if subprocess.run('curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/', shell=True,
                              stdout=subprocess.DEVNULL).returncode == 0:
                return True

            else:
                time.sleep(1)
                raise Exception(f'{self.colors["RED"]}VPN is off{self.colors["NC"]}')
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            raise

    def docker_checks(self) -> bool:
        """
        Constantly Check if Docker is running and start Redis container if needed
        :return: true is docker on
        :rtype: bool
        :exception KeyboardInterrupt: catching ^c
        """
        try:
            # check if docker is on
            if subprocess.run('docker info', shell=True, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode != 0:
                raise Exception(
                    f'{self.colors["RED"]}This script uses docker, and it isn\'t running - please start docker{self.colors["NC"]}')

            # if docker container found running do nothing
            elif subprocess.run(f'docker ps -q -f name={self.cont_name} -f status=running', shell=True,
                                stderr=subprocess.DEVNULL, stdout=subprocess.PIPE).stdout:
                return True

            elif subprocess.run(f'docker ps -q -f name={self.cont_name} -f status=exited', shell=True,
                                stderr=subprocess.DEVNULL, stdout=subprocess.PIPE).stdout:
                # Check if Redis container is exited, start if needed
                subprocess.run(f'docker start {self.cont_name}', shell=True, stdout=subprocess.DEVNULL)
                return True
            elif subprocess.run(f'docker ps -q -f name={self.cont_name} -f status=created', shell=True,
                                stderr=subprocess.DEVNULL, stdout=subprocess.PIPE).stdout:
                self.clean_up()
                subprocess.run(
                    f'docker run --name {self.cont_name} -d -p 127.0.0.1:6379:6379 {self.cont_name}:latest',
                    shell=True, stdout=subprocess.DEVNULL)
                return True
            else:
                subprocess.run(
                    f'docker run --name {self.cont_name} -d -p 127.0.0.1:6379:6379 {self.cont_name}:latest',
                    shell=True, stdout=subprocess.DEVNULL)
                return True
        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
            raise

    def ssh_env(self) -> None:
        """
        Constantly checks for ssh params
        :rtype: void or exit
        :exception KeyboardInterrupt: catching ^c
        """
        while True:
            if self.run_checks():
                if self.dod_root:
                    if not LocalStack.is_ssh_running():  # when ssh not running start ssh
                        try:
                            valid = False
                            while not valid:
                                self.env_name = input(
                                    f'{self.colors["VIOLET"]}Please enter the env you want to ssh to:\nprp1\ndev2\ndev1\n{self.colors["NC"]}').strip().lower()
                                if self.env_name in self.environments:
                                    valid = True
                                    self.logger.info(
                                        f'{self.colors["GREEN"]}Starting ssh {self.env_name}{self.colors["NC"]}')
                                    subprocess.run(f'ssh -fN {self.env_name}', shell=True)
                                    if LocalStack.is_ssh_running():
                                        break
                                else:
                                    self.logger.error(
                                        f'{self.colors["RED"]}Invalid argument \'{self.env_name}\' please mention prp1 or dev2 pls enter again{self.colors["NC"]}')

                        except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                            self.logger.error(f'\n{self.colors["RED"]}Exiting script...{self.colors["NC"]}')
                            self.clean_up()
                            sys.exit(1)

                    else:
                        self.logger.warning(
                            f'{self.colors["AMBER"]}ssh is running skipping{self.colors["NC"]}')  # if ssh session open then skip
                        break
                else:
                    self.logger.error(f'{self.colors["RED"]}env variable DOD_ROOT not set{self.colors["NC"]}')
                    self.clean_up()
                    sys.exit(1)

    def stack_up(self) -> None:
        """
        final checks
        :exception subprocess.CalledProcessError: package error
        :exception FileNotFoundError: repo or file not found
        :exception KeyboardInterrupt: catching ^c
        :rtype: void
        """
        if self.check_pgpass_env_ssh() and self.run_checks():
            if self.dod_root:
                try:
                    os.chdir(f'{self.dod_root}/dod-stack')
                    subprocess.run('dotenv -e .env tmuxp load dod-stack.yaml', shell=True, check=True,
                                   stderr=subprocess.DEVNULL)
                except FileNotFoundError:  # catching if file or repo doesn't exist or env variable doesn't exist
                    self.logger.error(f'{self.colors["RED"]}No dod-stack repo or file exiting{self.colors["NC"]}')
                except subprocess.CalledProcessError as e:
                    self.logger.error(
                        f'{self.colors["RED"]}An error occurred: {e}\ninstall pip dependencies from dod-stack repo:\ncd $DOD_ROOT/dod-stack\npip install -r requirements.txt{self.colors["NC"]}')
                except KeyboardInterrupt:  # trying to catch if somebody presses ^C
                    self.logger.error(f'\n{self.colors["RED"]}Exiting script...{self.colors["NC"]}')

            else:
                self.logger.error(f'{self.colors["RED"]}env variable DOD_ROOT not set{self.colors["NC"]}')

    def clean_up(self):
        """
        cleans up docker and ssh session and tmux session
        :rtype: void
        """

        if LocalStack.get_tmux_session_id():
            subprocess.run('tmux kill-session -t DOD_Stack', shell=True)
        subprocess.run(f'kill -9 {str(LocalStack.get_ssh_pid())}', shell=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        subprocess.run(f'docker container rm -f {self.cont_name} && docker volume prune -f', shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def main(self):
        """
        Main function for program
        :rtype: void
        """
        if sys.platform == 'linux':
            # set title of shell
            sys.stdout.write("\x1b]2;DOD-Stack\x07")
            # prints user and pwd
            self.logger.debug(f'{self.colors["BLUE"]}You are {self.user} in {self.cwd}{self.colors["NC"]}')
            LocalStack.update_pip()
            self.ssh_env()
            self.stack_up()
            self.clean_up()
        else:
            self.logger.error('This script only works on Linux machines or WSL.')

    @staticmethod
    def get_tmux_session_id() -> int:
        """
        get tmux session id
        :return: tmux session id
        :rtype: int
        :exception subprocess.CallProcessError: no session exception
        """
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
        process = subprocess.Popen('lsof -t -i:22', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if err:
            return 0
        return int(out.decode().strip()) if out else None


if __name__ == '__main__':
    local = LocalStack()
    local.main()
