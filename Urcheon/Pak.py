#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon import Action
from Urcheon import MapCompiler
from Urcheon import SourceTree
from Urcheon import Ui
import __main__ as m
import argparse
import logging
import multiprocessing
import os
import subprocess
import sys
import threading
import zipfile
from collections import OrderedDict


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


class Builder():
	def __init__(self, source_dir, build_dir, game_name=None, map_profile=None, auto_actions=False):
		if not game_name:
			pak_config = SourceTree.Config(source_dir)
			game_name = pak_config.requireKey("game")

		self.game_name = game_name

		if not map_profile:
			map_config = MapCompiler.Config(source_dir)
			map_profile = map_config.requireDefaultProfile()
			self.map_profile = map_profile

		self.action_list = Action.List(source_dir, game_name)

		# implicit action list
		if auto_actions:
			self.action_list.computeActions()

		self.source_dir = source_dir
		self.build_dir = build_dir
		self.game_name = game_name
		self.map_profile = map_profile

		# read predefined actions first
		self.action_list.readActions()


	# TODO: buildpack
	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.build_dir):
			logging.debug("found build dir: " + self.build_dir)
		else:
			logging.debug("create build dir: " + self.build_dir)
			os.makedirs(self.build_dir, exist_ok=True)

		logging.debug("reading build list from source dir: " + self.source_dir)

		for action in Action.Directory().directory:
			for file_path in self.action_list.active_action_dict[action.keyword]:
				# no need to use multiprocessing module to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				a = action(self.source_dir, self.build_dir, file_path, game_name=self.game_name, map_profile=self.map_profile)

				if not action.parallel:
					# action that can't be multithreaded
					a.run()
				else:
					# args expect an iterable, hence the comma inside parenthesis otherwise the string is passed as is
					# since we call a foreign function, we must pass itself
					thread = threading.Thread(target=a.run)

					while threading.active_count() > multiprocessing.cpu_count():
						pass

					thread.start()


class Packer():
	def __init__(self, pk3dir, pk3):
		self.pk3dir_path = pk3dir
		self.pk3_path = pk3

	def createSubdirs(self, pack_path):
		pack_subdir = os.path.dirname(pack_path)
		if pack_subdir == "":
			pack_subdir = "."

		if os.path.isdir(pack_subdir):
			logging.debug("found pack subdir: " +  pack_subdir)
		else:
			logging.debug("create pack subdir: " + pack_subdir)
			os.makedirs(pack_subdir, exist_ok=True)

	def pack(self):
		Ui.print("Packing " + self.pk3dir_path + " to: " + self.pk3_path)
		self.createSubdirs(self.pk3_path)
		logging.debug("opening: " + self.pk3_path)

		# remove existing file (do not write in place) to force the game engine to reread the file
		if os.path.isfile(self.pk3_path):
			logging.debug("remove existing pack: " + self.pk3_path)
			os.remove(self.pk3_path)

		pk3 = zipfile.ZipFile(self.pk3_path, "w", zipfile.ZIP_DEFLATED)

		orig_dir = os.getcwd()
		os.chdir(self.pk3dir_path)
		for dirname, subdirname_list, file_name_list in os.walk('.'):
			for file_name in file_name_list:
				file_path = os.path.join(dirname, file_name)[len(os.path.curdir + os.path.sep):]
				Ui.print("adding file to archive: " + file_path)
				pk3.write(file_path)

		logging.debug("closing: " + self.pk3_path)
		pk3.close()

		Ui.print("Package written: " + self.pk3_path)


class Cleaner():
	def __init__(self):
		None

	def cleanTest(self, test_dir):
		None

	def cleanPaks(self, pkg_dir, pak_name):
		None


def main(stage=None):

	if stage:
		prog_name = os.path.basename(m.__file__) + " " + stage
	else:
		prog_name = os.path.basename(m.__file__)

	description = "%(prog)s is a pak builder for my lovely granger."

	args = argparse.ArgumentParser(description=description, prog=prog_name)
	args.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	args.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	args.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s, default: %(default)s")
	args.add_argument("-sd", "--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	args.add_argument("-bp", "--build-prefix", dest="build_prefix", metavar="DIRNAME", default="build", help="build in prefix %(metavar)s, default: %(default)s")
	args.add_argument("-tp", "--test-parent", dest="test_parent_dir", metavar="DIRNAME", default="test", help="build test pakdir in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-pp", "--pkg-parent", dest="release_parent_dir", metavar="DIRNAME", default="pkg", help="build release pak in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-td", "--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as directory %(metavar)s")
	args.add_argument("-pf", "--pkg-file", dest="pkg_file", metavar="FILENAME", help="build release pak as file %(metavar)s")
	args.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", help="build map with profile %(metavar)s, default: %(default)s")
	args.add_argument("-ev", "--extra-version", dest="extra_version", metavar="VERSION", help="add %(metavar)s to pak version string")
	args.add_argument("-u", "--update-actions", dest="update", help="compute actions, write down list", action="store_true")
	args.add_argument("-b", "--build", dest="build", help="build source pakdir", action="store_true")
	args.add_argument("-a", "--auto-actions", dest="auto_actions", help="compute actions at build time and do not store the list", action="store_true")
	args.add_argument("-p", "--package", dest="package", help="compress release pak", action="store_true")
	args.add_argument("-c", "--clean", dest="clean", help="clean previous build", action="store_true")

	args = args.parse_args()

	env_build_prefix = os.getenv("BUILDPREFIX")
	env_test_parent_dir = os.getenv("TESTPARENT")
	env_release_parent_dir = os.getenv("PKGPARENT")

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	if args.update:
		action_list = Action.List(args.source_dir, args.game_name)
		action_list.updateActions()

	if args.package or args.build or args.clean:
		if args.build_prefix:
			build_prefix = args.build_prefix

		if env_build_prefix:
			if args.build_prefix:
				Ui.warning("build dir “" + build_prefix + "” superseded by env BUILDPREFIX: " + env_build_prefix)
			build_prefix = env_build_prefix

		if args.test_parent_dir:
			test_parent_dir = args.test_parent_dir

		if env_test_parent_dir:
			if args.test_parent_dir:
				Ui.warning("build test dir “" + test_parent_dir + "” superseded by env TESTPARENT: " + env_test_parent_dir)
			test_parent_dir = env_test_parent_dir

		if args.release_parent_dir:
			release_parent_dir = args.release_parent_dir

		if env_release_parent_dir:
			if args.release_parent_dir:
				Ui.warning("build pkg dir “" + release_parent_dir + "” superseded by env PKGPARENT: " + env_release_parent_dir)
			release_parent_dir = env_release_parent_dir

		if args.test_dir:
			test_dir = args.test_dir
		else:
			pak_config = SourceTree.Config(args.source_dir)
			pak_name = pak_config.requireKey("name")
			test_dir = build_prefix + os.path.sep + test_parent_dir + os.path.sep + pak_name + "_test" + os.path.extsep + "pk3dir"

	if args.build:
		if args.auto_actions:
			builder = Builder(args.source_dir, test_dir, game_name=args.game_name, map_profile=args.map_profile, auto_actions=True)
		else:
			builder = Builder(args.source_dir, test_dir, game_name=args.game_name, map_profile=args.map_profile)

		builder.build()

	if args.package:
		if args.pkg_file:
			pkg_file = args.pkg_file
		else:
			pak_config = SourceTree.Config(args.source_dir)
			pak_name = pak_config.requireKey("name")
			pak_version = pak_config.requireKey("version")

			if args.extra_version:
				pak_version += args.extra_version
			pkg_file = build_prefix + os.path.sep + release_parent_dir + os.path.sep + pak_name + "_" + pak_version + os.path.extsep + "pk3"

		packer = Packer(test_dir, pkg_file)
		packer.pack()

	if args.clean:
		cleaner = Cleaner()
		cleaner.cleanTest(test_dir)
		cleaner.cleanPaks(release_parent_dir, pak_name)


if __name__ == "__main__":
	main()
