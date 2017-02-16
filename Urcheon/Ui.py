#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import sys

class Ui():
	def __init__(self):
		self.verbosely = False

	def print(self, message):
		# I duplicate print() because I will add colouring support and verbose/quiet support in the future
		print(message)

	def verbose(self, message):
		if self.verbosely:
			print(message)

	def warning(self, message):
		print("Warning: " + message)

	def notice(self, message):
		print("Notice: " + message)

	def error(self, message):
		print("Error: " + message)
		sys.exit()

