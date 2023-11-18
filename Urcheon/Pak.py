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
from datetime import datetime
from operator import attrgetter


class MultiRunner():
	def __init__(self, source_dir_list, args):
		self.source_dir_list = source_dir_list
		self.args = args

		self.runner_dict = {
			"prepare": Builder,
			"build": Builder,
			"package": Packager,
		}

	def run(self):
		cpu_count = Parallelism.countCPU()
		runner_thread_list = []

		for source_dir in self.source_dir_list:
			# FIXME: because of this code Urcheon must run within package set directory
			Ui.notice(self.args.stage_name + " from: " + source_dir)
			source_dir = os.path.realpath(source_dir)

			source_tree = Repository.Tree(source_dir, game_name=self.args.game_name)

			runner = self.runner_dict[self.args.stage_name](source_tree, self.args)

			if self.args.no_parallel:
				runner.run()
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
	def __init__(self, source_tree, args, is_nested=False, disabled_action_list=[], file_list=[]):

		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.pak_name = source_tree.pak_name
		self.pak_format = source_tree.pak_format
		self.game_name = source_tree.game_name
		self.is_nested = is_nested

		self.stage_name = args.stage_name

		if is_nested:
			self.keep_dust = False
		else:
			self.keep_dust = args.keep_dust

		action_list = Action.List(source_tree, self.stage_name, disabled_action_list=disabled_action_list)

		if self.stage_name == "prepare":
			self.test_dir = self.source_dir

			self.since_reference = None
			self.no_auto_actions = False
			self.clean_map = False
			self.map_profile = None

			# FIXME: currently the prepare stage
			# can't be parallel (for example SlothRun task
			# needs all PrevRun tasks to be finished first)
			# btw all packages can be prepared in parallel
			self.is_parallel = False
		else:
			if is_nested:
				self.test_dir = args.test_dir
			else:
				self.test_dir = source_tree.pak_config.getTestDir(args)

			if is_nested:
				self.since_reference = False
				self.no_auto_actions = False
				self.clean_map = False
				self.map_profile = None

				self.is_parallel = not args.no_parallel
			else:
				self.since_reference = args.since_reference
				self.no_auto_actions = args.no_auto_actions
				self.clean_map = args.clean_map
				self.map_profile = args.map_profile
				self.is_parallel = not args.no_parallel

		if self.pak_format == "dpk":
			self.deleted = Repository.Deleted(self.source_tree, self.test_dir, self.stage_name)
			self.deps = Repository.Deps(self.source_tree, self.test_dir)

		if not is_nested:
			if self.pak_format == "dpk":
				deleted_action_list = self.deleted.getActions()
				action_list.readActions(action_list=deleted_action_list)

			action_list.readActions()

		if not file_list:
			# FIXME: only if one package?
			# same reference for multiple packages
			# makes sense when using tags

			# NOTE: already prepared file can be seen as source again, but there may be no easy way to solve it
			if self.since_reference:
				file_repo = Repository.Git(self.source_dir, self.pak_format)
				file_list = file_repo.listFilesSinceReference(self.since_reference)

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

		if not self.map_profile:
			map_config = MapCompiler.Config(source_tree)
			self.map_profile = map_config.requireDefaultProfile()


	def run(self):
		if self.source_dir == self.test_dir:
			Ui.print("Preparing: " + self.source_dir)
		else:
			Ui.print("Building “" + self.source_dir + "” as: " + self.test_dir)

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
					# or action that can't be run concurrently to others (like MergeBsp)
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

					# wrapper does: produced_unit_list.extend(action.run())
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

		# Handle symbolic links.
		for action_type in Action.list():
			for file_path in self.action_list.active_action_dict[action_type.keyword]:
				action = action_type(self.source_tree, self.test_dir, file_path, self.stage_name, action_list=self.action_list, map_profile=self.map_profile, is_nested=self.is_nested)

				# TODO: check for symbolic link to missing or deleted files.
				produced_unit_list.extend(action.symlink())

		# deduplication
		unit_list = []
		deleted_file_list = []
		produced_file_list = []
		for unit in produced_unit_list:
			if unit == []:
				continue

			logging.debug("unit: " + str(unit))
			head = unit["head"]
			body = unit["body"]
			action = unit["action"]

			if action == "ignore":
				continue

			if action == "delete":
				deleted_file_list.append( head )

			if head not in produced_file_list:
				produced_file_list.append(head)

				for part in body:
					if part not in produced_file_list:
						# FIXME: only if action was not “ignore”
						produced_file_list.append(part)

			# if multiple calls produce the same files (like merge_bsp)
			# FIXME: that can't work, this is probably a leftover
			# or we may have to do “if head in body” instead.
			# See https://github.com/DaemonEngine/Urcheon/issues/48
			if head in unit:
				continue

			unit_list.append(unit)

		produced_unit_list = unit_list

		if self.stage_name == "build" and not self.is_nested:
			if self.pak_format == "dpk":
				is_deleted = False

				if self.since_reference:
					Ui.laconic("looking for deleted files")
					# Unvanquished game did not support DELETED file until after 0.52.1.
					workaround_no_delete = self.source_tree.game_name == "unvanquished" and self.since_reference in ["unvanquished/0.52.1", "v0.52.1"]

					git_repo = Repository.Git(self.source_dir, "dpk", workaround_no_delete=workaround_no_delete)

					previous_version = git_repo.computeVersion(self.since_reference, named_reference=True)
					self.deps.set(self.pak_name, previous_version)

					for deleted_file in git_repo.getDeletedFileList(self.since_reference):
						if deleted_file not in deleted_file_list:
							is_deleted = True
							deleted_file_list.append(deleted_file)

				if deleted_file_list:
					is_deleted = True
					for deleted_file in deleted_file_list:
						self.deleted.set(self.pak_name, deleted_file)

				if self.deleted.read():
					is_deleted = True

				if is_deleted:
					deleted_part_list = self.deleted.translate()

					# TODO: No need to mark as DELETED a file from the same
					# package if it does not depend on itself.
					# TODO: A way to not translate DELETED files may be needed
					# in some cases.

					# If flamer.jpg producing flamer.crn was replaced
					# by flamer.png also producing flamer.crn, the
					# flamer.crn file will be listed as deleted
					# while it will be shipped, but built from another
					# source file, so we must check deleted files
					# aren't built in other way to avoid listing
					# as deleted a file that is actually shipped.
					for deleted_part_dict in deleted_part_list:
						deleted_part = deleted_part_dict["file_path"]

						is_built = False

						if deleted_part_dict["pak_name"] == self.pak_name:
							if deleted_part.startswith(Default.repository_config_dir + os.path.sep):
								continue

							if deleted_part.startswith(Default.legacy_pakinfo_dir + os.path.sep):
								continue

							if deleted_part in produced_file_list:
								is_built = True
								Ui.laconic(deleted_part + ": do nothing because it is produced by another source file.")
								self.deleted.removePart(self.pak_name, deleted_part)

						if not is_built:
							Ui.laconic(deleted_part + ": will mark as deleted.")

					# Writing DELETED file.
					for deleted_part in deleted_part_list:
						self.deleted.set(self.source_tree.pak_name, deleted_part)

					is_deleted = self.deleted.write()

				if is_deleted:
					unit = {
						"head": "DELETED",
						"body": [ "DELETED" ],
					}

					produced_unit_list.append(unit)
				else:
					# Remove DELETED leftover from partial build.
					self.deps.remove(self.test_dir)

				is_deps = False

				# add itself to DEPS if partial build,
				# also look for deleted files
				if self.since_reference:
					is_deps = True

				if self.deps.read():
					is_deps = True

				if is_deps:
					# translating DEPS file
					self.deps.translateTest()
					self.deps.write()

					unit = {
						"head": "DEPS",
						"body": [ "DEPS" ],
					}

					produced_unit_list.append(unit)
				else:
					# Remove DEPS leftover from partial build.
					self.deps.remove(self.test_dir)

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
	# TODO: reuse paktraces, do not walk for file,s
	def __init__(self, source_tree, args):
		self.source_tree = source_tree

		self.source_dir = source_tree.dir
		self.pak_vfs = source_tree.pak_vfs
		self.pak_config = source_tree.pak_config
		self.pak_format = source_tree.pak_format

		self.allow_dirty = args.allow_dirty
		self.no_compress = args.no_compress
		self.merge_dir = args.merge_dir

		self.test_dir = self.pak_config.getTestDir(args)
		self.pak_file = self.pak_config.getPakFile(args)

		self.game_profile = Game.Game(source_tree)

		if self.pak_format == "dpk":
			self.deleted = Repository.Deleted(source_tree, self.test_dir, None)
			self.deps = Repository.Deps(source_tree, self.test_dir)

	def createSubdirs(self, pak_file):
		pak_subdir = os.path.dirname(pak_file)
		if pak_subdir == "":
			pak_subdir = "."

		if os.path.isdir(pak_subdir):
			logging.debug("found pak subdir: " +  pak_subdir)
		else:
			logging.debug("create pak subdir: " + pak_subdir)
			os.makedirs(pak_subdir, exist_ok=True)

	def addToPak(self, pak_zipfile, full_path, file_path):
		# TODO: add a mechanism to know if VFS supports
		# symbolic links in packages or not.
		# Dæmon's DPK VFS is supporting symbolic links.
		# DarkPlaces' PK3 VFS is supporting symbolic links.
		# Others may not.
		is_symlink_supported = True
		if is_symlink_supported and os.path.islink(full_path):
			Ui.print("add symlink to package " + os.path.basename(self.pak_file) + ": " + file_path)

			# TODO: Remove this test when Urcheon deletes extra
			# files in build directory. Currently a deleted but not
			# committed file is kept.
			if os.path.exists(full_path):
				# FIXME: getmtime reads realpath datetime, not symbolic link datetime.
				file_date_time = (datetime.fromtimestamp(os.path.getmtime(full_path)))

			# See https://stackoverflow.com/a/61795576/9131399
			attrs = ('year', 'month', 'day', 'hour', 'minute', 'second')
			file_date_time_tuple = attrgetter(*attrs)(file_date_time)

			# See https://stackoverflow.com/a/60691331/9131399
			zip_info = zipfile.ZipInfo(file_path, date_time=file_date_time_tuple)
			zip_info.create_system = 3

			file_permissions = 0o777
			file_permissions |= 0xA000
			zip_info.external_attr = file_permissions << 16

			target_path = os.readlink(full_path)
			pak_zipfile.writestr(zip_info, target_path)
		else:
			Ui.print("add file to package " + os.path.basename(self.pak_file) + ": " + file_path)
			pak_zipfile.write(full_path, arcname=file_path)

	def run(self):
		if not os.path.isdir(self.test_dir):
			Ui.error("test pakdir not built: " + self.test_dir)

		source_repository = Repository.Git(self.source_dir, self.pak_format)
		if source_repository.isGit() and source_repository.isDirty():
			if self.allow_dirty:
				Ui.warning("Dirty repository: " + self.source_dir)
			else:
				Ui.error("Dirty repository isn't allowed to be packaged (use --allow-dirty to override): " + self.source_dir)

		Ui.print("Packaging “" + self.test_dir + "” as: " + self.pak_file)

		self.createSubdirs(self.pak_file)
		logging.debug("opening: " + self.pak_file)

		# remove existing file (do not write in place) to force the game engine to reread the file
		if os.path.isfile(self.pak_file):
			logging.debug("remove existing package: " + self.pak_file)
			os.remove(self.pak_file)

		if self.no_compress:
			# why zlib.Z_NO_COMPRESSION not defined?
			zipfile.zlib.Z_DEFAULT_COMPRESSION = 0
		else:
			# maximum compression
			zipfile.zlib.Z_DEFAULT_COMPRESSION = zipfile.zlib.Z_BEST_COMPRESSION

		paktrace_dir = Default.getPakTraceDir(self.test_dir)
		relative_paktrace_dir = os.path.relpath(paktrace_dir, self.test_dir)

		paktrace = Repository.Paktrace(self.source_tree, self.test_dir)
		built_file_list = paktrace.listAll()

		for dir_name, subdir_name_list, file_name_list in os.walk(self.test_dir):
			for file_name in file_name_list:
				rel_dir_name = os.path.relpath(dir_name, self.test_dir)

				full_path = os.path.join(dir_name, file_name)
				file_path = os.path.relpath(full_path, self.test_dir)

				# ignore paktrace files
				if file_path.startswith(relative_paktrace_dir + os.path.sep):
					continue

				# ignore DELETED and DEPS file, will add it later
				if self.pak_format == "dpk" and file_path in Repository.dpk_special_files:
					continue

				if file_path not in built_file_list:
					Ui.warning("extraneous file, will not package: " + file_path)

		test_file_list = []

		for file_path in built_file_list:
			full_path = os.path.join(self.test_dir, file_path)

			if not os.path.exists(full_path):
				Ui.error("Missing " + full_path)

			file_dict = {
				"full_path": full_path,
				"file_path": file_path,
			}

			test_file_list.append(file_dict)

		merge_file_list = []

		if self.merge_dir:
			for dir_name, subdir_name_list, file_name_list in os.walk(self.merge_dir):
				for file_name in file_name_list:
					full_path = os.path.join(dir_name, file_name)
					file_path = os.path.relpath(full_path, self.merge_dir)

					# unsupported paktrace files
					if file_path.startswith(relative_paktrace_dir + os.path.sep):
						Ui.error("Merging urcheon-built dpkdir is not supported", silent=True)

					# unsupported DELETED and DEPS file
					if self.pak_format == "dpk" and file_path in Repository.dpk_special_files:
						Ui.error("Merging urcheon-built dpkdir is not supported", silent=True)

					file_dict = {
						"full_path": full_path,
						"file_path": file_path,
					}

					merge_file_list.append(file_dict)

		# FIXME: if only the DEPS file is modified, the package will
		# not be created (it should be).
		if not test_file_list and not merge_file_list:
			Ui.print("Not writing empty package: " + self.pak_file)
			return

		pak_zipfile = zipfile.ZipFile(self.pak_file, "w", zipfile.ZIP_DEFLATED)

		for file_dict in test_file_list:
			self.addToPak(pak_zipfile, file_dict["full_path"], file_dict["file_path"])

		if self.merge_dir:
			Ui.print("Merging " + self.merge_dir + " directory")
			for file_dict in merge_file_list:
				self.addToPak(pak_zipfile, file_dict["full_path"], file_dict["file_path"])

		if self.pak_format == "dpk":
			# Writing DELETED file.
			deleted_file_path = self.deleted.get_test_path()
			if os.path.isfile(deleted_file_path):
					pak_zipfile.write(deleted_file_path, arcname="DELETED")

			# Translating DEPS file.
			if self.deps.read(deps_dir=self.test_dir):
				self.deps.translateRelease(self.pak_vfs)

				deps_temp_dir = tempfile.mkdtemp()
				deps_temp_file = self.deps.write(deps_dir=deps_temp_dir)
				Ui.print("add file to package " + os.path.basename(self.pak_file) + ": DEPS")
				pak_zipfile.write(deps_temp_file, arcname="DEPS")

		logging.debug("close: " + self.pak_file)
		pak_zipfile.close()

		if source_repository.isGit():
			repo_date = int(source_repository.getDate("HEAD"))
			os.utime(self.pak_file, (repo_date, repo_date))

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


	def cleanPak(self, install_dir):
		for dir_name, subdir_name_list, file_name_list in os.walk(install_dir):
			for file_name in file_name_list:
				if file_name.startswith(self.pak_name) and file_name.endswith(self.game_profile.pak_ext):
					pak_file = os.path.join(dir_name, file_name)
					Ui.laconic("clean: " + pak_file)
					os.remove(pak_file)
					FileSystem.removeEmptyDir(dir_name)
		FileSystem.removeEmptyDir(install_dir)


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
		# FIXME: reuse produced_file_list from build()
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

		paktrace_dir = Default.getPakTraceDir(test_dir)

		if os.path.isdir(paktrace_dir):
			logging.debug("look for dust in directory: " + paktrace_dir)
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_dir):
				dir_name = os.path.relpath(dir_name, test_dir)
				logging.debug("found paktrace dir: " + dir_name)

				for file_name in file_name_list:
					file_path = os.path.join(dir_name, file_name)
					file_path = os.path.normpath(file_path)

					relative_paktrace_dir = os.path.relpath(paktrace_dir, test_dir)
					trace_file = os.path.relpath(file_path, relative_paktrace_dir)
					head_name=trace_file[:-len(Default.paktrace_file_ext)]

					if head_name not in head_list:
						Ui.print("clean dust paktrace: " + file_path)
						dust_paktrace_path = os.path.normpath(os.path.join(test_dir, file_path))
						dust_paktrace_fullpath = os.path.realpath(dust_paktrace_path)
						FileSystem.cleanRemoveFile(dust_paktrace_fullpath)
