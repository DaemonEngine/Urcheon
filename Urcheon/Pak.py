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
from Urcheon import Game
from Urcheon import MapCompiler
from Urcheon import Parallelism
from Urcheon import Repository
from Urcheon import Ui
import __main__ as m
import argparse
import logging
import os
import sys
import tempfile
import time
import zipfile
from collections import OrderedDict


class MultiRunner():
	def __init__(self, source_dir_list, stage_name, build_prefix=None, test_prefix=None, test_dir=None, game_name=None, map_profile=None, since_reference=None, no_auto_actions=False, clean_map=False, keep_dust=False, pak_prefix=None, pak_file=None, no_compress=False, is_parallel=True):

		# common
		self.source_dir_list = source_dir_list
		self.stage_name = stage_name
		self.game_name = game_name
		self.is_parallel = is_parallel
		# prepare, build, package
		self.build_prefix = build_prefix
		# build
		self.test_prefix = test_prefix
		self.test_dir = test_dir
		# prepare, build
		self.map_profile = map_profile
		self.since_reference = since_reference
		self.no_auto_actions = no_auto_actions
		self.clean_map = clean_map
		self.keep_dust = keep_dust
		# package
		self.pak_prefix = pak_prefix
		self.pak_file = pak_file
		self.no_compress = no_compress

		self.pak_vfs = None

	def run(self):
		cpu_count = Parallelism.countCPU()
		runner_thread_list = []

		for source_dir in self.source_dir_list:
			# FIXME: because of this code Urcheon must run within package set directory
			Ui.notice(self.stage_name + " from: " + source_dir)
			source_dir = os.path.realpath(source_dir)

			source_tree = Repository.Tree(source_dir, game_name=self.game_name)
			if not source_tree.isValid():
				Ui.error("not a supported tree: " + source_dir)

			if self.stage_name in ["prepare"]:
				dest_dir = source_dir
			elif self.stage_name in ["build", "package"]:
				dest_dir = source_tree.pak_config.getTestDir(build_prefix=self.build_prefix, test_prefix=self.test_prefix, test_dir=self.test_dir)

			# FIXME: currently the prepare stage
			# can't be parallel (for example SlothRun task
			# needs all PrevRun tasks to be finished first)
			# btw all packages can be prepared in parallel
			if self.stage_name in ["prepare"]:
				is_parallel_runner = False
			else:
				is_parallel_runner = self.is_parallel

			if self.stage_name in ["build", "package"]:
				if not self.pak_vfs:
					self.pak_vfs = Repository.PakVfs()

			if self.stage_name in ["prepare", "build"]:
				runner = Builder(source_tree, self.pak_vfs, self.stage_name, dest_dir, map_profile=self.map_profile, since_reference=self.since_reference, no_auto_actions=self.no_auto_actions, clean_map=self.clean_map, keep_dust=self.keep_dust, is_parallel=is_parallel_runner)
			elif self.stage_name in ["package"]:
				runner = Packager(source_tree, self.pak_vfs, dest_dir, self.pak_file, build_prefix=self.build_prefix, test_prefix=self.test_prefix, pak_prefix=self.pak_prefix, no_compress=self.no_compress)

			if not self.is_parallel:
				runner.build()
			else:
				runner_thread = Parallelism.Thread(target=runner.run)
				runner_thread_list.append(runner_thread)

				while len(runner_thread_list) > cpu_count:
					# join dead thread early to raise thread exceptions early
					# forget ended threads
					runner_thread_list = Parallelism.joinDeadThreads(runner_thread_list)

				runner_thread.start()

		# wait for all remaining threads ending
		Parallelism.joinThreads(runner_thread_list)


class Builder():
	def __init__(self, source_tree, pak_vfs, stage_name, test_dir, map_profile=None, is_nested=False, since_reference=None, no_auto_actions=False, disabled_action_list=[], file_list=[], clean_map=False, keep_dust=False, is_parallel=True):
		self.run = self.build

		self.pak_vfs = pak_vfs
		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.game_name = source_tree.game_name
		self.stage_name = stage_name
		self.test_dir = test_dir
		self.is_nested = is_nested
		self.since_reference = since_reference
		self.no_auto_actions = no_auto_actions
		self.clean_map = clean_map
		self.keep_dust = keep_dust
		self.is_parallel = is_parallel

		action_list = Action.List(source_tree, stage_name, disabled_action_list=disabled_action_list)

		if not is_nested:
			action_list.readActions()

		# do not look for pak configuration in temporary directories
		# do not build temporary stuff in system build directories
		if not is_nested:
			self.pak_name = self.source_tree.pak_name

		else:
			self.test_dir = test_dir

		if not file_list:
			# FIXME: only if one package?
			# same reference for multiple packages
			# makes sense when using tags

			# NOTE: already prepared file can be seen as source again, but there may be no easy way to solve it
			if since_reference:
				file_repo = Repository.Git(self.source_dir, self.source_tree.pak_config.game_profile.pak_format)
				file_list = file_repo.listFilesSinceReference(since_reference)

				# also look for untracked files
				untracked_file_list = file_repo.listUntrackedFiles()
				for file_name in untracked_file_list:
					if file_name not in file_list:
						logging.debug("found untracked file “" + file_name + "”")
						# FIXME: next loop will look for prepared files for it, which makes no sense,
						# is it harmful?
						file_list.append(file_name)

				# also look for files produced with “prepare” command
				# from files modified since this reference
				paktrace = Repository.Paktrace(source_tree, self.source_dir)
				input_file_dict = paktrace.getFileDict()["input"]
				for file_path in file_list:
					logging.debug("looking for prepared files for “" + str(file_path) + "”")
					logging.debug("looking for prepared files for “" + file_path + "”")
					if file_path in input_file_dict.keys():
						for input_file_path in input_file_dict[file_path]:
							if not os.path.exists(os.path.join(self.source_dir, input_file_path)):
								logging.debug("missing prepared files for “" + file_path + "”: " + input_file_path)
							else:
								logging.debug("found prepared files for “" + file_path + "”: " + input_file_path)
								file_list.append(input_file_path)
			else:
				file_list = source_tree.listFiles()

		if not self.no_auto_actions:
			action_list.computeActions(file_list)
		
		self.action_list = action_list

		self.game_profile = Game.Game(source_tree)

		if not map_profile:
			map_config = MapCompiler.Config(source_tree)
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

		if not self.is_nested and not self.keep_dust:
			clean_dust = True
		else:
			clean_dust = False

		if clean_dust:
			# do not read paktrace from temporary directories
			# do not read paktrace if dust will be kept
			paktrace = Repository.Paktrace(self.source_tree, self.test_dir)
			previous_file_list = paktrace.listAll()

		if self.clean_map or clean_dust:
			cleaner = Cleaner(self.source_tree)

		if self.clean_map:
			cleaner.cleanMap(self.test_dir)

		cpu_count = Parallelism.countCPU()
		action_thread_list = []
		produced_unit_list = []

		main_process = Parallelism.getProcess()

		for action_type in Action.list():
			for file_path in self.action_list.active_action_dict[action_type.keyword]:
				# no need to use multiprocessing module to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				# the is_nested argument is there to tell action to not do specific stuff because of recursion
				action = action_type(self.source_tree, self.test_dir, file_path, self.stage_name, map_profile=self.map_profile, is_nested=self.is_nested)

				# check if task is already done (usually comparing timestamps the make way)
				if action.isDone():
					produced_unit_list.extend(action.getOldProducedUnitList())
					continue

				if not self.is_parallel or not action_type.is_parallel:
					# tasks are run sequentially but they can
					# use multiple threads themselves
					thread_count = cpu_count
				else:
					# this compute is super slow because of process.children()
					child_thread_count = Parallelism.countChildThread(main_process)
					thread_count = max(1, cpu_count - child_thread_count)

				action.thread_count = thread_count

				if not self.is_parallel or not action_type.is_parallel:
					# sequential build explicitely requested (like in recursion)
					# or action that can't be run concurrently to others (like MergeBs)
					produced_unit_list.extend(action.run())
				else:
					# do not use >= in case of there is some extra thread we don't think about
					# it's better to spawn an extra one than looping forever
					while child_thread_count > cpu_count:
						# no need to loop at full cpu speed
						time.sleep(.05)
						child_thread_count = Parallelism.countChildThread(main_process)
						pass

					# join dead thread early to raise thread exceptions early
					# forget ended threads
					action_thread_list = Parallelism.joinDeadThreads(action_thread_list)

					action.thread_count = max(2, cpu_count - child_thread_count)

					# wrapper does: produced_unit_list.append(a.run())
					action_thread = Parallelism.Thread(target=self.threadExtendRes, args=(action.run, (), produced_unit_list))
					action_thread_list.append(action_thread)
					action_thread.start()

				# join dead thread early to raise thread exceptions early
				# forget ended threads
				action_thread_list = Parallelism.joinDeadThreads(action_thread_list)

		# wait for all threads to end, otherwise it will start packaging next
		# package while the building task for the current one is not ended
		# and well, we now have to read that list to purge old files, so we
		# must wait
		Parallelism.joinThreads(action_thread_list)

		# deduplication
		unit_list = []
		for unit in produced_unit_list:
			if unit == {}:
				# because of ignore action
				continue

			logging.debug("unit: " + str(unit))
			head = unit["head"]
			body = unit["body"]

			# if multiple calls produce the same files (like merge_bsp)
			if head in unit:
				continue

			unit_list.append(unit)

		produced_unit_list = unit_list

		if self.stage_name == "build" and not self.is_nested:
			if self.game_profile.pak_format == "dpk":
				is_deps = False

				deps = Repository.Deps()

				# add itself to DEPS if partial build
				if self.since_reference:
					is_deps = True
					git_repo = Repository.Git(self.source_dir, "dpk")
					previous_version = git_repo.computeVersion(self.since_reference)
					deps.set(self.pak_name, previous_version)

				if deps.read(self.source_dir):
					is_deps = True

				if is_deps:
					# translating DEPS file
					deps.translateTest(self.pak_vfs)
					deps.write(self.test_dir)

					unit = {}
					unit["head"] = "DEPS"
					unit["body"] = []
					produced_unit_list.append(unit)
				else:
					# remove DEPS leftover from partial build
					deps.remove(self.test_dir)

		logging.debug("produced unit list:" + str(produced_unit_list))

		# do not clean-up if building from temporary directories
		# or if user asked to not clean-up
		if clean_dust:
			cleaner.cleanDust(self.test_dir, produced_unit_list, previous_file_list)

		return produced_unit_list

	def threadExtendRes(self, func, args, res):
		# magic: only works if res is a mutable object (like a list)
		res.extend(func(*args))


class Packager():
	# TODO: reuse paktraces, do not walk for files
	def __init__(self, source_tree, pak_vfs, test_dir, pak_file, build_prefix=None, test_prefix=None, pak_prefix=None, no_compress=False):
		self.run = self.pack

		self.pak_vfs = pak_vfs

		self.pak_config = source_tree.pak_config
		self.no_compress = no_compress

		self.test_dir = self.pak_config.getTestDir(build_prefix=build_prefix, test_prefix=test_prefix, test_dir=test_dir)
		self.pak_file = self.pak_config.getPakFile(build_prefix=build_prefix, pak_prefix=pak_prefix, pak_file=pak_file)

		self.game_profile = Game.Game(source_tree)


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
			Ui.error("test pakdir not built: " + self.test_dir)

		Ui.print("Packing " + self.test_dir + " to: " + self.pak_file)
		self.createSubdirs(self.pak_file)
		logging.debug("opening: " + self.pak_file)

		# remove existing file (do not write in place) to “”force the game engine to reread the file
		if os.path.isfile(self.pak_file):
			logging.debug("remove existing package: " + self.pak_file)
			os.remove(self.pak_file)

		if self.no_compress:
			# why zlib.Z_NO_COMPRESSION not defined?
			zipfile.zlib.Z_DEFAULT_COMPRESSION = 0
		else:
			# maximum compression
			zipfile.zlib.Z_DEFAULT_COMPRESSION = zipfile.zlib.Z_BEST_COMPRESSION

		paktrace_dir = Default.paktrace_dir

		found_file = False
		paktrace_fulldir = os.path.join(self.test_dir, paktrace_dir)
		for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_fulldir):
			for file_name in file_name_list:
				found_file = True
				break

			if found_file:
				break

		# FIXME: if only the DEPS file is modified, the package will
		# not be created (it should be).
		if not found_file:
			Ui.print("Not writing empty package: " + self.pak_file)
			return

		pak = zipfile.ZipFile(self.pak_file, "w", zipfile.ZIP_DEFLATED)

		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
			for file_name in file_name_list:
				rel_dir_name = os.path.relpath(dir_name, self.test_dir)

				full_path = os.path.join(dir_name, file_name)
				file_path = os.path.relpath(full_path, self.test_dir)

				# ignore paktrace files
				if file_path.startswith(paktrace_dir + os.path.sep):
					continue

				# ignore DEPS file, will add it later
				if file_path == "DEPS" and self.game_profile.pak_format == "dpk":
					continue

				found_file = True

				Ui.print("add file to package " + os.path.basename(self.pak_file) + ": " + file_path)
				pak.write(full_path, arcname=file_path)

		if self.game_profile.pak_format == "dpk":
			# translating DEPS file
			deps = Repository.Deps()
			if deps.read(self.test_dir):
				deps.translateRelease(self.pak_vfs)

				deps_temp_dir = tempfile.mkdtemp()
				deps_temp_file = deps.write(deps_temp_dir)
				Ui.print("add file to package " + os.path.basename(self.pak_file) + ": DEPS")
				pak.write(deps_temp_file, arcname="DEPS")

		logging.debug("close: " + self.pak_file)
		pak.close()

		Ui.laconic("Package written: " + self.pak_file)


class Cleaner():
	def __init__(self, source_tree):

		self.pak_name = source_tree.pak_name

		self.game_profile = Game.Game(source_tree)


	def cleanTest(self, test_dir):
		for dir_name, subdir_name_list, file_name_list in os.walk(test_dir):
			for file_name in file_name_list:
				that_file = os.path.join(dir_name, file_name)
				Ui.laconic("clean: " + that_file)
				os.remove(that_file)
				FileSystem.removeEmptyDir(dir_name)
			for dir_name in subdir_name_list:
				that_dir = dir_name + os.path.sep + dir_name
				FileSystem.removeEmptyDir(that_dir)
			FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(test_dir)


	def cleanPak(self, pak_prefix):
		for dir_name, subdir_name_list, file_name_list in os.walk(pak_prefix):
			for file_name in file_name_list:
				if file_name.startswith(self.pak_name) and file_name.endswith(self.game_profile.pak_ext):
					pak_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + pak_file)
					os.remove(pak_file)
					FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(pak_prefix)


	def cleanMap(self, test_dir):
		# TODO: use paktrace abilities?
		for dir_name, subdir_name_list, file_name_list in os.walk(test_dir):
			for file_name in file_name_list:
				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "bsp"):
					bsp_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + bsp_file)
					os.remove(bsp_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "map"):
					map_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + map_file)
					os.remove(map_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-2:-1] == ["maps"] and file_name.startswith("lm_"):
					lightmap_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + lightmap_file)
					os.remove(lightmap_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["maps"] and file_name.endswith(os.path.extsep + "navMesh"):
					navmesh_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + navmesh_file)
					os.remove(navmesh_file)
					FileSystem.removeEmptyDir(dir_name)

				if dir_name.split("/")[-1:] == ["minimaps"]:
					minimap_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + minimap_file)
					os.remove(minimap_file)
					FileSystem.removeEmptyDir(dir_name)

		FileSystem.removeEmptyDir(test_dir)


	def cleanDust(self, test_dir, produced_unit_list, previous_file_list):
		# TODO: remove extra files that are not tracked in paktraces?
		produced_file_list = []
		head_list = []
		for unit in produced_unit_list:
			head_list.append(unit["head"])
			produced_file_list.extend(unit["body"])

		for file_name in previous_file_list:
			if file_name not in produced_file_list:
				dust_file_path = os.path.normpath(os.path.join(test_dir, file_name))
				Ui.laconic("clean dust file: " + file_name)
				dust_file_fullpath = os.path.realpath(dust_file_path)

				if not os.path.isfile(dust_file_fullpath):
					# if you're there, it's because you are debugging a crash
					continue

				FileSystem.cleanRemoveFile(dust_file_fullpath)
			
		paktrace_dir = Default.paktrace_dir
		paktrace_fulldir = os.path.join(test_dir, paktrace_dir)

		if os.path.isdir(paktrace_fulldir):
			logging.debug("look for dust in directory: " + paktrace_dir)
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_fulldir):
				dir_name = os.path.relpath(dir_name, test_dir)
				logging.debug("found paktrace dir: " + dir_name)

				for file_name in file_name_list:
					file_path = os.path.join(dir_name, file_name)
					file_path = os.path.normpath(file_path)

					head_name = os.path.relpath(file_path, Default.paktrace_dir)[:-len(Default.paktrace_file_ext)]
					if head_name not in head_list:
						Ui.print("clean dust paktrace: " + file_path)
						dust_paktrace_path = os.path.normpath(os.path.join(test_dir, file_path))
						dust_paktrace_fullpath = os.path.realpath(dust_paktrace_path)
						FileSystem.cleanRemoveFile(dust_paktrace_fullpath)


def discover(stage_name):
	prog_name = os.path.basename(m.__file__) + " " + stage_name
	description = "%(prog)s discover files and write down action lists."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game %(metavar)s game profile, example: unvanquished")
	parser.add_argument("--build-prefix", dest="build_prefix", help=argparse.SUPPRESS)
	parser.add_argument("--test-prefix", dest="test_prefix", help=argparse.SUPPRESS)
	parser.add_argument("--pak-prefix", dest="pak_prefix", help=argparse.SUPPRESS)
	parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="build %(metavar)s directory, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	if args.source_dir == ".":
		# default
		source_dir_list = [ "." ]
	else:
		source_dir_list = args.source_dir

	for source_dir in source_dir_list:
		Ui.notice("discover from: " + source_dir)
		source_dir = os.path.realpath(args.source_dir[0])

		source_tree = Repository.Tree(source_dir, game_name=args.game_name)
		if not source_tree.isValid():
			Ui.error("not a supported tree, not going further", silent=True)

		# TODO: find a way to update "prepare" actions too
		file_list = source_tree.listFiles()

		action_list = Action.List(source_tree, "build")
		action_list.updateActions(action_list)


def prepare(stage_name):
	prog_name = os.path.basename(m.__file__) + " " + stage_name
	description = "%(prog)s prepare source pakdir."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game %(metavar)s game profile, example: unvanquished")
	parser.add_argument("--build-prefix", dest="build_prefix", help=argparse.SUPPRESS)
	parser.add_argument("--test-prefix", dest="test_prefix", help=argparse.SUPPRESS)
	parser.add_argument("--pak-prefix", dest="pak_prefix", help=argparse.SUPPRESS)
	parser.add_argument("-n", "--no-auto-actions", dest="no_auto_actions", help="do not compute actions at build time", action="store_true")
	parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	parser.add_argument("-np", "--no-parallel", dest="no_parallel", help="build sequentially (disable parallel build)", action="store_true")
	parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="build %(metavar)s directory, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	if args.source_dir == ".":
		# default
		source_dir_list = [ "." ]
	else:
		source_dir_list = args.source_dir

	is_parallel = not args.no_parallel
	multi_runner = MultiRunner(source_dir_list, stage_name, game_name=args.game_name, no_auto_actions=args.no_auto_actions, keep_dust=args.keep_dust, is_parallel=is_parallel)
	multi_runner.run()


def build(stage_name):
	prog_name = os.path.basename(m.__file__) + " " + stage_name
	description = "%(prog)s produces test pakdir."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game %(metavar)s game profile, example: unvanquished")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in %(metavar)s prefix, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="build test pakdir in %(metavar)s prefix, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", help=argparse.SUPPRESS)
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as %(metavar)s directory")
	parser.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", help="build map with %(metavar)s profile, default: %(default)s")
	parser.add_argument("-n", "--no-auto", dest="no_auto_actions", help="do not compute actions", action="store_true")
	parser.add_argument("-k", "--keep", dest="keep_dust", help="keep dust from previous build", action="store_true")
	parser.add_argument("-cm", "--clean-map", dest="clean_map", help="clean previous map build", action="store_true")
	parser.add_argument("-np", "--no-parallel", dest="no_parallel", help="build sequentially (disable parallel build)", action="store_true")
	parser.add_argument("-r", "--reference", dest="since_reference", metavar="REFERENCE", help="build partial pakdir since given reference")
	parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="build from %(metavar)s directory, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	if args.source_dir == ".":
		# default
		source_dir_list = [ "." ]
	else:
		source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while building more than one source directory", silent=True)

	is_parallel = not args.no_parallel
	multi_runner = MultiRunner(source_dir_list, stage_name, build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir, game_name=args.game_name, map_profile=args.map_profile, since_reference=args.since_reference, no_auto_actions=args.no_auto_actions, clean_map=args.clean_map, keep_dust=args.keep_dust, is_parallel=is_parallel)
	multi_runner.run()


def package(stage_name):
	prog_name = os.path.basename(m.__file__) + " " + stage_name
	description = "%(prog)s produces release pak."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use %(metavar)s game profile, example: unvanquished")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="build in %(metavar)s prefix, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="use test pakdir from %(metavar)s prefix, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="build release pak in %(metavar)s prefix, example: build/pkg")
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="use directory %(metavar)s as pakdir")
	parser.add_argument("--pak-file", dest="pak_file", metavar="FILENAME", help="build release pak as %(metavar)s file")
	parser.add_argument("-np", "--no-parallel", dest="no_parallel", help="package sequentially (disable parallel package)", action="store_true")
	parser.add_argument("-nc", "--no-compress", dest="no_compress", help="package without compression", action="store_true")
	parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="build from %(metavar)s directory, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	if args.source_dir == ".":
		# default
		source_dir_list = [ "." ]
	else:
		source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while packaging more than one source directory", silent=True)

	if args.pak_file and len(source_dir_list) > 1:
		Ui.error("--pak-file can't be used while packaging more than one source directory", silent=True)

	is_parallel = not args.no_parallel
	multi_runner = MultiRunner(source_dir_list, stage_name, build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir, pak_prefix=args.pak_prefix, pak_file=args.pak_file, game_name=args.game_name, no_compress=args.no_compress, is_parallel=is_parallel)
	multi_runner.run()


def clean(stage_name):
	prog_name = os.path.basename(m.__file__) + " " + stage_name
	description = "%(prog)s cleans build directory and previously generated package."

	parser = argparse.ArgumentParser(description=description, prog=prog_name)

	parser.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	parser.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	parser.add_argument("-l", "--laconic", dest="laconic", help="print laconic information", action="store_true")
	parser.add_argument("-g", "--game", dest="game_name", metavar="GAMENAME", help="use game %(metavar)s game profile, example: unvanquished")
	parser.add_argument("--build-prefix", dest="build_prefix", metavar="DIRNAME", help="clean in %(metavar)s prefix, example: build")
	parser.add_argument("--test-prefix", dest="test_prefix", metavar="DIRNAME", help="clean test pakdir in %(metavar)s prefix, example: build/test")
	parser.add_argument("--pak-prefix", dest="pak_prefix", metavar="DIRNAME", help="clean release pak in %(metavar)s prefix, example: build/pkg")
	parser.add_argument("--test-dir", dest="test_dir", metavar="DIRNAME", help="clean test pakdir as %(metavar)s directory")
	parser.add_argument("-a", "--all", dest="clean_all", help="clean all (default)", action="store_true")
	parser.add_argument("-s", "--source", dest="clean_source", help="clean previous source preparation", action="store_true")
	parser.add_argument("-m", "--map", dest="clean_map", help="clean previous map build", action="store_true")
	parser.add_argument("-b", "--build", dest="clean_build", help="clean build directory", action="store_true")
	parser.add_argument("-p", "--package", dest="clean_package", help="clean previously generated packages", action="store_true")
	parser.add_argument("source_dir", nargs="*", metavar="DIRNAME", default=".", help="clean %(metavar)s directory, default: %(default)s")

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.laconic:
		Ui.verbosity = "laconic"
	elif args.verbose:
		Ui.verbosity = "verbose"

	clean_all = args.clean_all

	if not args.clean_map and not args.clean_build and not args.clean_package and not args.clean_all:
		clean_all = True

	if args.source_dir == ".":
		# default
		source_dir_list = [ "." ]
	else:
		source_dir_list = args.source_dir

	if args.test_dir and len(source_dir_list) > 1:
		Ui.error("--test-dir can't be used while cleaning more than one source directory", silent=True)

	for source_dir in source_dir_list:
		Ui.notice("clean from: " + source_dir)
		source_dir = os.path.realpath(source_dir)

		source_tree = Repository.Tree(source_dir, game_name=args.game_name)
		if not source_tree.isValid():
			Ui.error("not a supported tree, not going further", silent=True)

		cleaner = Cleaner(source_tree)

		if args.clean_map:
			pak_config = Repository.Config(source_tree)
			test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
			cleaner.cleanMap(test_dir)

		if args.clean_source or clean_all:
			paktrace = Repository.Paktrace(source_tree, source_dir)
			previous_file_list = paktrace.listAll()
			cleaner.cleanDust(source_dir, [], previous_file_list)

		if args.clean_build or clean_all:
			pak_config = Repository.Config(source_tree)
			test_dir = pak_config.getTestDir(build_prefix=args.build_prefix, test_prefix=args.test_prefix, test_dir=args.test_dir)
			cleaner.cleanTest(test_dir)

		if args.clean_package or clean_all:
			pak_config = Repository.Config(source_tree)
			pak_prefix = pak_config.getPakPrefix(build_prefix=args.build_prefix, pak_prefix=args.pak_prefix)
			cleaner.cleanPak(pak_prefix)
