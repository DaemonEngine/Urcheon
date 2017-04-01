#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon.StageParse import StageParse
from Urcheon import Map
from Urcheon import Bsp
import sys


def main():
	arg_stage = StageParse(description="%(prog)s is a gentle intendant for my lovely granger's garden.")
	arg_stage.addStage("map", help="map parser")
	arg_stage.addStage("bsp", help="bsp parser")

	arg_stage = arg_stage.parseArgs()

	stage = None

	if arg_stage.map:
		stage = Map

	if arg_stage.bsp:
		stage = Bsp

	if stage:
		del sys.argv[1]
		stage.main(stage=arg_stage.stage)
		

if __name__ == "__main__":
	main()
