#!/bin/bash


##############################################################################################
# Author		: Saatvik Gulati
# Date:			: 22/03/2023
# Description		: To run local stack with the help of this file.
# 			: This file checks for vpn, docker and in the end cleansup too
# Required		: Requires Linux to run. This will include WSL (Ubuntu preferred)
#			: Requires env defination to be upto date in ssh config, .pgpass
# Usage Example		: To run the file ./dod-stack.bash or bash dod-stack.bash
#               	: Enter env which you want to ssh to
#				: prp1
#				: prd1
#				: dev2
##############################################################################################

RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;94m'
NC='\033[0m' # No Color

echo -ne "\033]0;DOD-Stack\a"

printf "You are $USER on $PWD\n"

declare -l cont_name='redis'
declare -l env_name=''



function dockerChecks(){
	if ! docker info > /dev/null 2>&1; then
		printf "$RED This script uses docker, and it isn't running - please start docker and try again! $NC\n"
		cleanUp
		return 1
	fi
	if [ $(docker ps -q -f status=running -f name=^/${cont_name}$) ]; then
		return 0
	elif [ $(docker ps -q -f status=exited -f name=^/${cont_name}$) ]; then
		docker start $cont_name > /dev/null
		return 0
	else
		docker run --name $cont_name -d -p 127.0.0.1:6379:6379 $cont_name:latest > /dev/null
		return 0
	fi
}

function vpnChecks(){
	if curl -s https://vpn-test-emzo-kops1.service.ops.iptho.co.uk/ > /dev/null; then
		return 0
	else
		printf "$RED VPN is off $NC\n"
		cleanUp
		return 1
	fi
}

function cleanUp(){

	kill -9 $(lsof -t -i:22) > /dev/null 2>&1

	docker container rm -f $cont_name > /dev/null 2>&1

	docker volume prune -f > /dev/null 2>&1

}

function stackUp(){

	# final checks
	if vpnChecks && dockerChecks; then
	
		cd $DOD_ROOT/dod-stack

		dotenv -e .env tmuxp load dod-stack.yaml
	else
		exit 1
	fi
}
function ssh_env(){
	if vpnChecks && dockerChecks; then
		printf "$BLUE Please enter the env you want to ssh to- prp1 or prd1 or dev2: $NC\n"

		read env_name
		
		if lsof -t -i:22 > /dev/null; then
			:
		else
			case $env_name in
				prp1)
					printf "$YELLOW Starting ssh $env_name $NC\n"
					ssh -fN $env_name
				;;
				prd1)
					printf "$YELLOW Starting ssh $env_name $NC\n"
					ssh -fN $env_name
				;;
				dev2)
					printf "$YELLOW Starting ssh $env_name $NC\n"
					ssh -fN $env_name
				;;
				*)
					printf "$RED Invalid argument '$env_name' please mention prp1 or prd1 or dev2 exiting $NC\n"
					cleanUp
					exit 1
				;;
			esac
		fi
	else
		exit  1
	fi
}



function main(){
	# does ssh to env
	ssh_env

	# brings the stack up
	stackUp

	# Cleans when ending
	cleanUp
}


# Calling main function
main
