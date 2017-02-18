#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import sys

# keep an eye on the default Python's print function
_print = print

verbosely = False

def print(message):
	# I duplicate print() because I will add colouring support and verbose/quiet support in the future
	_print(message)

def verbose(message):
	if verbosely:
		_print(message)

def warning(message):
	_print("Warning: " + message)

def notice(message):
	_print("Notice: " + message)

def error(message):
	_print("Error: " + message)
	sys.exit()
