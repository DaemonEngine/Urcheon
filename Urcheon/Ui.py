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

verbosity = None


def laconic(message):
	if sys.stdout.isatty():
		message = Fore.GREEN + message + Style.RESET_ALL
	_print(message)


def print(message):
	if verbosity != "laconic":
		if sys.stdout.isatty():
			message = Fore.GREEN + message + Style.RESET_ALL
		_print(message)


def verbose(message):
	if verbosity == verbose:
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


def error(message, silent=False):
	_message = message
	message = "Error: " + message

	if sys.stdout.isatty():
		message = Fore.RED + message + Style.RESET_ALL
	_print(message)

	if silent:
		raise SystemExit()
	else:
		raise ValueError(_message)
