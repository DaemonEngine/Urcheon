#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Action
from Urcheon import Default
from Urcheon import FileSystem
from Urcheon import MapCompiler
from Urcheon import Repository
from Urcheon import Ui
import __main__ as m
import argparse
import logging
import multiprocessing
import os
import sys
import tempfile
import threading
import zipfile
from collections import OrderedDict


class Builder():
	def __init__(self, source_dir, action_list, stage, build_dir, game_name=None, map_profile=None, is_nested=False, since_reference=None, parallel=True):
		self.source_dir = source_dir
		self.action_list = action_list
		self.stage = stage
		self.build_dir = build_dir
		self.is_nested = is_nested
		self.since_reference = since_reference
		self.parallel = parallel

		# Do not look for pak configuration in temporary directories, do not build temporary stuff in system build directories
		if not is_nested:
			pak_config = Repository.Config(source_dir)

			if not game_name:
				game_name = pak_config.requireKey("game")

			self.pak_name = pak_config.requireKey("name")

		else:
			self.build_dir = build_dir

		self.game_name = game_name

		if not map_profile:
			map_config = MapCompiler.Config(source_dir, game_name=self.game_name)
			map_profile = map_config.requireDefaultProfile()
			self.map_profile = map_profile

		self.map_profile = map_profile


	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.build_dir):
			logging.debug("found build dir: " + self.build_dir)
		else:
			logging.debug("create build dir: " + self.build_dir)
			os.makedirs(self.build_dir, exist_ok=True)

		thread_list = []
		produced_unit_list = []
		for action in Action.list():
			for file_path in self.action_list.active_action_dict[action.keyword]:
				# no need to use multiprocessing module to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				# the is_nested argument is just there to tell that action to not do specific stuff because recursion
				a = action(self.source_dir, self.build_dir, file_path, self.stage, game_name=self.game_name, map_profile=self.map_profile, is_nested=self.is_nested)

				if not self.parallel:
					# explicitely requested (like in recursion)
					produced_unit_list.append(a.run())
				else:
					if not action.parallel:
						# action that can't be multithreaded
						produced_unit_list.append(a.run())
					else:
						# wrapper does: produced_unit_list.append(a.run())
						thread = threading.Thread(target=self.threadAppendRes, args=(a.run, (), produced_unit_list))
						thread_list.append(thread)

						while threading.active_count() > multiprocessing.cpu_count():
							pass

						thread.start()

		# wait for all threads ending, otherwise it will start packaging next
		# package while the building task for the current one is not ended
		# and well, we now have to read that list to purge old files, so we
		# must wait
		for thread in thread_list:
			thread.join()

		# deduplication
		unit_list = []
		for unit in produced_unit_list:
			if unit == {}:
				# because of ignore action
				continue

			logging.debug("unit: " + str(unit))
			head = unit["head"]
			body = unit["body"]

			# if multiple calls produces the same files (like merge_bsp)
			if head in unit:
				continue

			unit_list.append(unit)

		if not self.is_nested:
			is_deps = False

			deps = Repository.Deps()

			if self.since_reference:
				is_deps = True
				git_repo = Repository.Git(self.source_dir)
				previous_version = git_repo.computeVersion(self.since_reference)
				deps.set(self.pak_name, previous_version)

			if deps.read(self.source_dir):
				is_deps = True

			if is_deps:
				deps.translateTest()
				deps.write(self.build_dir)

				unit = {}
				unit["head"] = "DEPS"
				unit["body"] = []
				unit_list.append(unit)

		logging.debug("unit_list:" + str(unit_list))
		return unit_list

	def threadAppendRes(self, func, args, res):
		# magic: only works if res is a mutable object (like a list)
		res.append(func(*args))


class Packer():
	# TODO: reuse paktraces, does not walk for files
	def __init__(self, source_dir, build_dir, pak_file):
		pak_config = Repository.Config(source_dir)
		self.build_dir = build_dir
		self.pak_file = pak_file

	def createSubdirs(self, pak_file):
		pak_subdir = os.path.dirname(pak_file)
		if pak_subdir == "":
			pak_subdir = "."

		if os.path.isdir(pak_subdir):
			logging.debug("found pak subdir: " +  pak_subdir)
		else:
			logging.debug("create pak subdir: " + pak_subdir)
			os.makedirs(pak_subdir, exist_ok=True)

	def pack(self):
		if not os.path.isdir(self.build_dir):
			Ui.error("test pakdir not built")

		Ui.print("Packing " + self.build_dir + " to: " + self.pak_file)
		self.createSubdirs(self.pak_file)
		logging.debug("opening: " + self.pak_file)

		# remove existing file (do not write in place) to force the game engine to reread the file
		if os.path.isfile(self.pak_file):
			logging.debug("remove existing package: " + self.pak_file)
			os.remove(self.pak_file)

		pak = zipfile.ZipFile(self.pak_file, "w", zipfile.ZIP_DEFLATED)

		paktrace_dir = Default.paktrace_dir
		for dir_name, subdir_name_list, file_name_list in os.walk(self.build_dir):
			for file_name in file_name_list:
				rel_dir_name = os.path.relpath(dir_name, self.build_dir)

				full_path = os.path.join(dir_name, file_name)
				file_path = os.path.relpath(full_path, self.build_dir)

				# ignore paktrace files
				if file_path.startswith(paktrace_dir + os.path.sep):
					continue

				# ignore DEPS file, will add it later
				if file_path == "DEPS":
					continue

				Ui.print("add file to package: " + file_path)
				pak.write(full_path, arcname=file_path)

		# translating DEPS file
		deps = Repository.Deps()
		if deps.read(self.build_dir):
			deps.translateRelease()
			# TODO: add itself if partial build
			deps_temp_dir = tempfile.mkdtemp()
			deps_temp_file = deps.write(deps_temp_dir)
			Ui.print("add file to package: DEPS")
			pak.write(deps_temp_file, arcname="DEPS")

		logging.debug("close: " + self.pak_file)
		pak.close()

		Ui.print("Package written: " + self.pak_file)


class Cleaner():
	def __init__(self, source_dir):
		pak_config = Repository.Config(source_dir)
		self.pak_name = pak_config.requireKey("name")


	def cleanTest(self, build_dir):
		for dir_name, subdir_name_list, file_name_list in os.walk(build_dir):
			for file_name in file_name_list:
				that_file = os.path.join(dir_name, file_name)
				Ui.print("clean: " + that_file)
				os.remove(that_file)
				FileSystem.removeEmptyDir(dir_name)
			for dir_name in subdir_name_list:
				that_dir = dir_name + os.path.sep + dir_name
				FileSystem.removeEmptyDir(that_dir)
			FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(build_dir)


	def cleanPak(self, pak_prefix):
		for dir_name, subdir_name_list, file_name_list in os.walk(pak_prefix):
			for file_name in file_name_list:
				if file_name.startswith(self.pak_name) and file_name.endswith(os.path.extsep + "pk3"):
					pak_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + pak_file)
					os.remove(pak_file)
					FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(pak_prefix)


	def cleanMap(self, build_dir):
		# TODO: use paktrace abilities?
		for dir_name, subdir_name_list, file_name_list in os.walk(build_dir):
			for file_name in file_name_list:
				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "bsp"):
					bsp_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + bsp_file)
					os.remove(bsp_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "map"):
					map_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + map_file)
					os.remove(map_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-2:-1] == ["maps"] and file_name.startswith("lm_"):
					lightmap_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + lightmap_file)
					os.remove(lightmap_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "navMesh"):
					navmesh_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + navmesh_file)
					os.remove(navmesh_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["minimaps"]:
					minimap_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + minimap_file)
					os.remove(minimap_file)
					FileSystem.removeEmptyDir(dir_name)

		FileSystem.removeEmptyDir(build_dir)


	def cleanDust(self, build_dir, produced_unit_list, previous_file_list):
		produced_file_list = []
		head_list = []
		for unit in produced_unit_list:
			head_list.append(unit["head"])
			produced_file_list.extend(unit["body"])

		for file_name in previous_file_list:
			if file_name not in produced_file_list:
				dust_file_path = os.path.normpath(os.path.join(build_dir, file_name))
				Ui.print("clean dust file: " + file_name)
				dust_file_fullpath = os.path.realpath(dust_file_path)

				if not os.path.isfile(dust_file_fullpath):
					# if you're there, it's because you are debugging a crash
					continue

				FileSystem.cleanRemoveFile(dust_file_fullpath)
			
		paktrace_dir = Default.paktrace_dir
		paktrace_fulldir = os.path.join(build_dir, paktrace_dir)

		if os.path.isdir(paktrace_fulldir):
			logging.debug("look for dust in directory: " + paktrace_dir)
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_fulldir):
				dir_name = os.path.relpath(dir_name, build_dir)
				logging.debug("found paktrace dir: " + dir_name)

				for file_name in file_name_list:
					file_path = os.path.join(dir_name, file_name)
					file_path = os.path.normpath(file_path)

					head_name = os.path.relpath(file_path, Default.paktrace_dir)[:-len(os.path.extsep + Default.paktrace_file_ext)]
					if head_name not in head_list:
						Ui.print("clean dust paktrace: " + file_path)
						dust_paktrace_path = os.path.normpath(os.path.join(build_dir, file_path))
						dust_paktrace_fullpath = os.path.realpath(dust_paktrace_path)
						FileSystem.cleanRemoveFile(dust_paktrace_fullpath)


def discover(stage):
	prog_name = os.path.basename(m.__file__) + " " + stage
	description = "%(prog)s discover files and write down action lists."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	parser.add_argument("--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	# TODO: find a way to update "prepare" actions too
	file_tree = Repository.Tree(args.source_dir)
	file_list = file_tree.listFiles()

	action_list = Action.List(args.source_dir, "build", game_name=args.game_name)
	action_list.updateActions(action_list)


def prepare(stage):
	prog_name = os.path.basename(m.__file__) + " " + stage
	description = "%(prog)s prepare source pakdir."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	parser.add_argument("--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	parser.add_argument("-n", "--no-auto-actions", dest="no_auto_actions", help="do not compute actions at build time", action="store_true")
	parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	parser.add_argument("-s", "--sequential", dest="sequential_build", help="build sequentially (disable parallel build)", action="store_true")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	action_list = Action.List(args.source_dir, "prepare", game_name=args.game_name)
	action_list.readActions()

	file_tree = Repository.Tree(args.source_dir)
	file_list = file_tree.listFiles()

	if not args.no_auto_actions:
		action_list.computeActions(file_list)

	source_dir = args.source_dir

	paktrace = Repository.Paktrace(source_dir)
	previous_file_list = paktrace.listAll()

	parallel_build = not args.sequential_build
	builder = Builder(source_dir, action_list, "prepare", source_dir, game_name=args.game_name, parallel=parallel_build)
	produced_unit_list = builder.build()

	cleaner = Cleaner(source_dir)

	if not args.keep_dust:
		cleaner.cleanDust(source_dir, produced_unit_list, previous_file_list)


def build(stage):
	prog_name = os.path.basename(m.__file__) + " " + stage
	description = "%(prog)s produces test pakdir."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	parser.add_argument("--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in prefix %(metavar)s, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="build test pakdir in prefix %(metavar)s, example: build/test")
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as directory %(metavar)s")
	parser.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", help="build map with profile %(metavar)s, default: %(default)s")
	parser.add_argument("-n", "--no-auto", dest="no_auto_actions", help="do not compute actions", action="store_true")
	parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	parser.add_argument("-c", "--clean-map", dest="clean_map", help="clean previous map build", action="store_true")
	parser.add_argument("-s", "--sequential", dest="sequential_build", help="build sequentially (disable parallel build)", action="store_true")
	parser.add_argument("-r", "--reference", dest="since_reference", metavar="REFERENCE", help="build partial pakdir since given reference")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	action_list = Action.List(args.source_dir, "build", game_name=args.game_name)
	action_list.readActions()

	if args.since_reference:
		file_repo = Repository.Git(args.source_dir)
		file_list = file_repo.listFilesSinceReference(args.since_reference)
	else:
		file_tree = Repository.Tree(args.source_dir)
		file_list = file_tree.listFiles()

	if not args.no_auto_actions:
		action_list.computeActions(file_list)

	source_dir = args.source_dir

	pak_config = Repository.Config(source_dir)
	test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)

	cleaner = Cleaner(source_dir)

	if args.clean_map:
		cleaner.cleanMap(test_dir)

	paktrace = Repository.Paktrace(test_dir)
	previous_file_list = paktrace.listAll()

	parallel_build = not args.sequential_build
	builder = Builder(source_dir, action_list, "build", test_dir, game_name=args.game_name, map_profile=args.map_profile, since_reference=args.since_reference, parallel=parallel_build)
	produced_unit_list = builder.build()

	if not args.keep_dust:
		cleaner.cleanDust(test_dir, produced_unit_list, previous_file_list)


def package(stage):
	prog_name = os.path.basename(m.__file__) + " " + stage
	description = "%(prog)s produces release pak."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	parser.add_argument("--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in prefix %(metavar)s, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="use test pakdir from prefix %(metavar)s, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="build release pak in prefix %(metavar)s, example: build/pkg")
	parser.add_argument("--test_dir", dest="test_dir", metavar="DIRNAME", help="use directory %(metavar)s as pakdir")
	parser.add_argument("--pak-file", dest="pak_file", metavar="FILENAME", help="build release pak as file %(metavar)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	source_dir = args.source_dir

	pak_config = Repository.Config(source_dir)
	test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
	pak_file = pak_config.getPakFile(build_prefix=args.build_prefix, pak_prefix=args.pak_prefix, pak_file=args.pak_file)

	packer = Packer(source_dir, test_dir, pak_file)
	packer.pack()


def clean(stage):
	prog_name = os.path.basename(m.__file__) + " " + stage
	description = "%(prog)s cleans build directory and previously generated package."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	parser.add_argument("-sd", "--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in prefix %(metavar)s, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="build test pakdir in prefix %(metavar)s, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="build release pak in prefix %(metavar)s, example: build/pkg")
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as directory %(metavar)s")
	parser.add_argument("--pak-file", dest="pak_file", metavar="FILENAME", help="build release pak as file %(metavar)s")
	parser.add_argument("-a", "--all", dest="clean_all", help="clean all (default)", action="store_true")
	parser.add_argument("-s", "--source", dest="clean_source", help="clean previous source preparation", action="store_true")
	parser.add_argument("-m", "--map", dest="clean_map", help="clean previous map build", action="store_true")
	parser.add_argument("-b", "--build", dest="clean_build", help="clean build directory", action="store_true")
	parser.add_argument("-p", "--package", dest="clean_package", help="clean previously generated packages", action="store_true")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	clean_all = args.clean_all

	if not args.clean_map and not args.clean_build and not args.clean_package and not args.clean_all:
		clean_all = True

	source_dir = args.source_dir
	cleaner = Cleaner(source_dir)

	if args.clean_map:
		pak_config = Repository.Config(source_dir)
		test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
		cleaner.cleanMap(test_dir)

	if args.clean_source or clean_all:
		paktrace = Repository.Paktrace(source_dir)
		previous_file_list = paktrace.listAll()
		cleaner.cleanDust(source_dir, [], previous_file_list)

	if args.clean_build or clean_all:
		pak_config = Repository.Config(source_dir)
		test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
		cleaner.cleanTest(test_dir)

	if args.clean_package or clean_all:
		pak_config = Repository.Config(source_dir)
		pak_prefix = pak_config.getPakPrefix(build_prefix=args.build_prefix, pak_prefix=args.pak_prefix)
		cleaner.cleanPak(pak_prefix)


if __name__ == "__main__":
	main()
