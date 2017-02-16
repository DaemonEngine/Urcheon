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
from Urcheon import Pak
import sys

def main():
	arg_stage = StageParse(description="%(prog)s is a tender knight who takes care of my lovely granger's little flower.")
	arg_stage.addStage("map", help="map parser")
	arg_stage.addStage("bsp", help="bsp parser")
	arg_stage.addStage("pak", help="pak builder")

	arg_stage = arg_stage.parseArgs()

	stage = None

	if arg_stage.map:
		stage = Map

	if arg_stage.bsp:
		stage = Bsp

	if arg_stage.pak:
		stage = Pak

	if stage:
		del sys.argv[1]
		stage.main(stage=arg_stage.stage)
		

if __name__ == "__main__":
	main()
