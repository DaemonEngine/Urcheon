#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import Urcheon.MapCutter
import Urcheon.BspCutter
import Urcheon.PakMallet
import __main__ as m
import argparse
import sys
import os
from collections import OrderedDict


class ArgStage():
	def __init__(self):
		self.description = None
		self.stage_dict = OrderedDict()
		self.stage = None

	def addStage(self, stage_name, help=None):
		self.stage_dict[stage_name] = help
		setattr(self, stage_name, False)

	def printHelp(self, bad_arg=None, lone_stage=None):
		prog_name = os.path.basename(m.__file__)
		print("usage: " + prog_name + " [-h] <stage> [stage arguments]")

		if bad_arg:
			print(prog_name + ": error: unrecognized argument: " + bad_arg)
			sys.exit()

		if lone_stage:
			print("")
			print(prog_name + ": error: missing stage argument")
			print("")
			print("  try: " + prog_name + " " + lone_stage + " -h")
			sys.exit()

		if self.description:
			print("")
			print(self.description)

		print("")
		print("optional argument:")
		print("  -h, --help\tshow this help message and exit")

		if len(self.stage_dict.keys()) != 0:
			print("")
			print("stages:")
			for stage_name in self.stage_dict.keys():
				if self.stage_dict[stage_name]:
					print("  " + stage_name + "\t\t" + self.stage_dict[stage_name])
				else:
					print("  " + stage_name)

		print("")
		print("stage options:")
		print("  try: " + prog_name + " stage -h")

		sys.exit()

	def parseArgs(self):
		if len(sys.argv) == 1:
			sys.exit()

		arg = sys.argv[1]

		if arg == "-h" or arg == "--help":
			self.printHelp()

		if len(sys.argv) == 2:
			self.printHelp(lone_stage=arg)

		if arg in self.stage_dict.keys():
			setattr(self, arg, True)
			self.stage = arg
		else:
			self.printHelp(bad_arg=arg)

		return self


def main():
	arg_stage = ArgStage()
	arg_stage.description="urcheon is a tender knight who takes care of my lovely granger's little flower."
	arg_stage.addStage("map", help="map parser")
	arg_stage.addStage("bsp", help="bsp parser")
	arg_stage.addStage("pak", help="pak builder")

	arg_stage = arg_stage.parseArgs()

	stage = None

	if arg_stage.map:
		stage = Urcheon.MapCutter

	if arg_stage.bsp:
		stage = Urcheon.BspCutter

	if arg_stage.pak:
		stage = Urcheon.PakMallet

	if stage:
		del sys.argv[1]
		stage.main(stage=arg_stage.stage)
		

if __name__ == "__main__":
	main()
