#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon.StageParse import StageParse
from Urcheon import Pak
import sys


def main():
	arg_stage = StageParse(description="%(prog)s is a tender knight who takes care of my lovely granger's little flower.")
	arg_stage.addStage("clean", help="clean stuff")
	arg_stage.addStage("discover", help="discover files")
	arg_stage.addStage("build", help="build test pakdir")
	arg_stage.addStage("package", help="package release pak")

	arg_stage = arg_stage.parseArgs()

	stage = None

	if arg_stage.clean:
		stage = Pak.clean

	if arg_stage.discover:
		stage = Pak.discover

	if arg_stage.build:
		stage = Pak.build

	if arg_stage.package:
		stage = Pak.package

	if stage:
		del sys.argv[1]
		stage(arg_stage.stage)
		

if __name__ == "__main__":
	main()
