#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Bsp
from Urcheon import Map
import argparse
import logging
from logging import debug
import sys


def main():
	description="Esquirel is a gentle intendant for my lovely granger's garden."
	parser = argparse.ArgumentParser(description=description)

	parser.add_argument("-D", "--debug", help="print debug information", action="store_true")

	subparsers = parser.add_subparsers(help='contexts')
	subparsers.required = True

	map_parser = subparsers.add_parser('map', help='inspect or edit a map file')
	Map.add_arguments(map_parser)
	map_parser.set_defaults(func=Map.main)

	bsp_parser = subparsers.add_parser('bsp', help='inspect or edit a bsp file')
	Bsp.add_arguments(bsp_parser)
	bsp_parser.set_defaults(func=Bsp.main)

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		debug("Debug logging activated")
		debug("args: " + str(args))

	args.func(args)
