#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Action
from Urcheon import FileSystem
from Urcheon import MapCompiler
from Urcheon import Repository
from Urcheon import Ui
import __main__ as m
import argparse
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from collections import OrderedDict


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


class Builder():
	# test_dir is the pk3dir, so it's the build dir here
	def __init__(self, source_dir, action_list, stage, build_prefix=None, test_prefix=None, test_dir=None, game_name=None, map_profile=None, is_nested=False, since_reference=None, parallel=True):
		self.source_dir = source_dir
		self.action_list = action_list
		self.stage = stage
		self.is_nested = is_nested
		self.since_reference = since_reference
		self.parallel = parallel

		# Do not look for pak configuration in temporary directories, do not build temporary stuff in system build directories
		if not is_nested:
			pak_config = Repository.Config(source_dir)
			self.test_dir = pak_config.getTestDir(build_prefix=build_prefix, test_prefix=test_prefix, test_dir=test_dir)
		else:
			self.test_dir = test_dir

		self.pak_name = pak_config.requireKey("name")

		if not game_name:
			game_name = pak_config.requireKey("game")

		self.game_name = game_name

		if not map_profile:
			map_config = MapCompiler.Config(source_dir, game_name=self.game_name)
			map_profile = map_config.requireDefaultProfile()
			self.map_profile = map_profile

		self.map_profile = map_profile


	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.test_dir):
			logging.debug("found build dir: " + self.test_dir)
		else:
			logging.debug("create build dir: " + self.test_dir)
			os.makedirs(self.test_dir, exist_ok=True)

		logging.debug("reading build list from source dir: " + self.source_dir)

		thread_list = []
		produced_unit_list = []
		for action in Action.list():
			for file_path in self.action_list.active_action_dict[action.keyword]:
				# no need to use multiprocessing module to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				# the is_nested argument is just there to tell that action to not do specific stuff because recursion
				a = action(self.source_dir, self.test_dir, file_path, self.stage, game_name=self.game_name, map_profile=self.map_profile, is_nested=self.is_nested)

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
				deps.write(self.test_dir)

				unit = {}
				unit["head"] = "DEPS"
				unit["body"] = ["DEPS"]
				unit_list.append(unit)

		logging.debug("unit_list:" + str(unit_list))
		return unit_list

	def threadAppendRes(self, func, args, res):
		# magic: only works if res is a mutable object (like a list)
		res.append(func(*args))


class Packer():
	def __init__(self, source_dir, build_prefix=None, test_prefix=None, test_dir=None, pak_prefix=None, pak_file=None):
		pak_config = Repository.Config(source_dir)
		self.test_dir = pak_config.getTestDir(build_prefix=build_prefix, test_prefix=test_prefix, test_dir=test_dir)
		self.pak_file = pak_config.getPakFile(build_prefix=build_prefix, pak_prefix=pak_prefix, pak_file=pak_file)

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
		if not os.path.isdir(self.test_dir):
			Ui.error("test pakdir not built")

		Ui.print("Packing " + self.test_dir + " to: " + self.pak_file)
		self.createSubdirs(self.pak_file)
		logging.debug("opening: " + self.pak_file)

		# remove existing file (do not write in place) to force the game engine to reread the file
		if os.path.isfile(self.pak_file):
			logging.debug("remove existing package: " + self.pak_file)
			os.remove(self.pak_file)

		pak = zipfile.ZipFile(self.pak_file, "w", zipfile.ZIP_DEFLATED)

		paktrace_dir = Repository.PakTrace(None).paktrace_dir
		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
			for file_name in file_name_list:
				rel_dir_name = os.path.relpath(dir_name, self.test_dir)

				full_path = os.path.join(dir_name, file_name)
				file_path = os.path.relpath(full_path, self.test_dir)

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
		if deps.read(self.test_dir):
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
	# TODO: remove paktraces files too
	def __init__(self, source_dir, build_prefix=None, test_prefix=None, test_dir=None, pak_prefix=None, pak_file=None):
		pak_config = Repository.Config(source_dir)
		self.test_dir = pak_config.getTestDir(build_prefix=build_prefix, test_prefix=test_prefix, test_dir=test_dir)
		self.pak_prefix = pak_config.getPakPrefix(build_prefix=build_prefix, pak_prefix=pak_prefix)
		self.pak_name = pak_config.requireKey("name")

	def cleanTest(self):
		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
			for file_name in file_name_list:
				that_file = os.path.join(dir_name, file_name)
				Ui.print("clean: " + that_file)
				os.remove(that_file)
				FileSystem.removeEmptyDir(dir_name)
			for dir_name in subdir_name_list:
				that_dir = dir_name + os.path.sep + dir_name
				FileSystem.removeEmptyDir(that_dir)
			FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(self.test_dir)

	def cleanPak(self):
		for dir_name, subdir_name_list, file_name_list in os.walk(self.pak_prefix):
			for file_name in file_name_list:
				if file_name.startswith(self.pak_name) and file_name.endswith(os.path.extsep + "pk3"):
					pak_file = os.path.join(dir_name, file_name)
					Ui.print("clean: " + pak_file)
					os.remove(pak_file)
					FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(self.pak_prefix)

	def cleanMap(self):
		# TODO: use paktrace abilities?
		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
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

	def cleanDust(self, produced_unit_list):

		produced_file_list = []
		for unit in produced_unit_list:
			produced_file_list.extend(unit["body"])

		paktrace_file_list = []
		dust_paktrace_list = []
		dust_file_list = []

		paktrace_dir = Repository.PakTrace(None).paktrace_dir
		paktrace_fulldir = os.path.join(self.test_dir, paktrace_dir)
		if os.path.isdir(paktrace_fulldir):
			logging.debug("look for dust in directory: " + paktrace_dir)
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_fulldir):
				dir_name = os.path.relpath(dir_name, self.test_dir)
				logging.debug("found paktrace dir: " + dir_name)

				for file_name in file_name_list:
					file_path = os.path.join(dir_name, file_name)
					file_path = os.path.normpath(file_path)
					paktrace = Repository.PakTrace(self.test_dir)
					body = paktrace.readByPath(file_path)

					member_found = False
					for member_name in body:
						member_path = os.path.join(self.test_dir, member_name)
						member_path = os.path.normpath(member_path)
						if os.path.isfile(member_path):
							paktrace_file_list.append(member_name)
							member_found = True

					if not member_found:
						dust_paktrace_list.append(file_path)

		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
			dir_name = os.path.relpath(dir_name, self.test_dir)

			# skip paktrace directory
			if dir_name == paktrace_dir or dir_name.startswith(paktrace_dir + os.path.sep):
				continue

			logging.debug("look for dust in directory: " + dir_name)
			logging.debug("found directory: " + dir_name)
			for file_name in file_name_list:
				that_file = os.path.join(dir_name, file_name)
				that_file = os.path.normpath(that_file)
				logging.debug("found file: " + that_file)
				if that_file not in paktrace_file_list and that_file not in produced_file_list:
					logging.debug("found dust file: " + that_file)
					dust_file_list.append(that_file)

		logging.debug("produced file list: " + str(produced_file_list))
		logging.debug("paktrace file list: " + str(paktrace_file_list))
		logging.debug("dust paktrace list: " + str(dust_paktrace_list))
		logging.debug("dust file list: " + str(dust_file_list))

		logging.debug("old file_list: " + str(dust_file_list))
		for dust_file in dust_file_list:
			dust_file_path = os.path.join(self.test_dir, dust_file)
			Ui.print("clean dust file: " + dust_file)
			full_path = os.path.join(self.test_dir, dust_file_path)
			FileSystem.cleanRemoveFile(full_path)

		for dust_paktrace in dust_paktrace_list:
			Ui.print("clean dust paktrace: " + dust_paktrace)
			full_path = os.path.join(self.test_dir, dust_paktrace)
			FileSystem.cleanRemoveFile(full_path)


def main(stage=None):

	if stage:
		prog_name = os.path.basename(m.__file__) + " " + stage
	else:
		prog_name = os.path.basename(m.__file__)

	description = "%(prog)s is a pak builder for my lovely granger."

	args = argparse.ArgumentParser(description=description, prog=prog_name)
	args.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	args.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	args.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game profile %(metavar)s")
	args.add_argument("-sd", "--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	args.add_argument("-bp", "--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in prefix %(metavar)s, example: build")
	args.add_argument("-tp", "--test-prefix", dest="test_prefix", metavar="DIRNAME", help="build test pakdir in prefix %(metavar)s, example: build/test")
	args.add_argument("-pp", "--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="build release pak in prefix %(metavar)s, example: build/pkg")
	args.add_argument("-td", "--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as directory %(metavar)s")
	args.add_argument("-pf", "--pak-file", dest="pak_file", metavar="FILENAME", help="build release pak as file %(metavar)s")
	args.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", help="build map with profile %(metavar)s, default: %(default)s")
	args.add_argument("-u", "--update-actions", dest="update", help="compute actions, write down list", action="store_true")
	args.add_argument("-a", "--auto-actions", dest="auto_actions", help="compute actions at build time and do not store the list", action="store_true")
	args.add_argument("-c", "--clean", dest="clean", metavar="KEYWORD", help="clean previous build, keywords are: map, test, pak, all")
	args.add_argument("-b", "--build", dest="build", help="build source pakdir", action="store_true")
	args.add_argument("-kd", "--keep-dust", dest="keep_dust", help="keep dust from previous build", action="store_true")
	args.add_argument("-sb", "--sequential-build", dest="sequential_build", help="build sequentially (disable parallel build)", action="store_true")
	args.add_argument("-p", "--package", dest="package", help="compress release pak", action="store_true")
	args.add_argument("-sr", "--since-reference", dest="since_reference", metavar="REFERENCE", help="build partial pakdir since given reference")

	args = args.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		Ui.verbosely = True

	if args.clean:
		if args.clean not in ["map", "test", "pak", "all"]:
			Ui.warning("clean keyword must be map, test, pak or all")
			return

		cleaner = Cleaner(args.source_dir, build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir, pak_prefix=args.pak_prefix, pak_file=args.pak_file)

		if args.clean == "map":
			cleaner.cleanMap()

		if args.clean == "test" or args.clean == "all":
			cleaner.cleanTest()

		if args.clean == "pak" or args.clean == "all":
			cleaner.cleanPak()

	action_list = None

	# TODO: find a way to update "prepare" actions too
	if args.update:
		file_tree = Repository.Tree(args.source_dir)
		file_list = file_tree.listFiles()

		action_list = Action.List(args.source_dir, "build", game_name=args.game_name)
		action_list.updateActions(action_list)

	if args.build:
		if not action_list:
			action_list = Action.List(args.source_dir, "build", game_name=args.game_name)
			action_list.readActions()

		if args.since_reference:
			file_repo = Repository.Git(args.source_dir)
			file_list = file_repo.listFilesSinceReference(args.since_reference)
		else:
			file_tree = Repository.Tree(args.source_dir)
			file_list = file_tree.listFiles()

		if args.auto_actions:
			action_list.computeActions(file_list)

		parallel_build = not args.sequential_build
		builder = Builder(args.source_dir, action_list, "build", build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir, game_name=args.game_name, map_profile=args.map_profile, since_reference=args.since_reference, parallel=parallel_build)
		produced_unit_list = builder.build()
		if not args.keep_dust:
			cleaner = Cleaner(args.source_dir)
			cleaner.cleanDust(produced_unit_list)

	if args.package:
		packer = Packer(args.source_dir, build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir, pak_prefix=args.pak_prefix, pak_file=args.pak_file)
		packer.pack()

if __name__ == "__main__":
	main()
