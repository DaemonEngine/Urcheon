#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import sys
from colorama import Fore, Style, init

# keep an eye on the default Python's print function
_print = print

verbosely = False

def print(message):
	# I duplicate print() because I will add colouring support and verbose/quiet support in the future
	if sys.stdout.isatty():
		message = Fore.GREEN + message + Style.RESET_ALL
	_print(message)

def verbose(message):
	if verbosely:
		if sys.stdout.isatty():
			message = Style.DIM + message + Style.RESET_ALL
		_print(message)

def warning(message):
	message = "Warning: " + message
	if sys.stdout.isatty():
		message = Fore.YELLOW + message + Style.RESET_ALL
	_print(message)

def notice(message):
	message = "Notice: " + message
	if sys.stdout.isatty():
		message = Style.BRIGHT + message + Style.RESET_ALL
	_print(message)

def error(message):
	message = "Error: " + message
	if sys.stdout.isatty():
		message = Fore.RED + message + Style.RESET_ALL
	_print(message)
	raise ValueError(message)
