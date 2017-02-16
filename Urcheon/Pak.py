#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

from Urcheon.Ui import Ui
from Urcheon.Bsp import Bsp
from Urcheon.SourceTree import Inspector
from Urcheon.SourceTree import PakConfig
from Urcheon.MapCompiler import BspCompiler
import __main__ as m
import os
import sys
import shutil
import subprocess
import argparse
import logging
import fnmatch
import zipfile
import configparser
import tempfile
import threading
import multiprocessing
from collections import OrderedDict


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


ui = Ui()


class BuildList():
	def __init__(self, source_dir, game_name):
		self.source_dir = source_dir
		self.pak_list_file_name = ".pakinfo" + os.path.sep + "build.tsv"
		self.pak_list_file = self.source_dir + os.path.sep + self.pak_list_file_name

		self.blacklist = [
			"Thumbs.db",
			"Makefile",
			"CMakeLists.txt",
			"__MACOSX",
			"*.DS_Store",
			"*.autosave",
			"*.bak",
			"*~",
			".*.swp",
			".git*",
			".pakinfo",
			"build",
		]

		pak_ignore_list_file_name = ".pakinfo" + os.path.sep + "pakignore"
		if os.path.isfile(pak_ignore_list_file_name):
			pak_ignore_list_file = open(pak_ignore_list_file_name, "r")
			line_list = [line.strip() for line in pak_ignore_list_file]
			pak_ignore_list_file.close()
			for pattern in line_list:
				self.blacklist.append(pattern)

		logging.debug("blacklist: " + str(self.blacklist))

		self.inspector = Inspector(game_name)
		self.active_action_dict = OrderedDict()
		self.inactive_action_dict = OrderedDict()
		self.computed_active_action_dict = OrderedDict()
		self.computed_inactive_action_dict = OrderedDict()

		# I want lines printed in this order
		for action_name in self.inspector.action_name_dict.keys():
			self.active_action_dict[action_name] = []
			self.inactive_action_dict[action_name] = []
			self.computed_active_action_dict[action_name] = []
			self.computed_inactive_action_dict[action_name] = []

	def readActions(self):
		if os.path.isfile(self.pak_list_file):
			pak_list_file = open(self.pak_list_file, "r")
			line_list = [line.strip() for line in pak_list_file]
			pak_list_file.close()
			for line in line_list:
				# TODO: regex
				read_action = line.split('\t')[0]
				file_path = line[len(read_action) + 1:]

				if read_action[0] == '#':
					inactive_action = read_action[1:]
					ui.print(file_path + ": Known rule, will not " + self.inspector.action_name_dict[read_action] + " (inactive).")
					self.inactive_action_dict[inactive_action].append(file_path)
				else:
					if os.path.isfile(file_path):
						ui.print(file_path + ": Known rule, will " + self.inspector.action_name_dict[read_action] + " (predefined).")
						self.active_action_dict[read_action].append(file_path)
					else:
						ui.print(file_path + ": Known rule, will not " + self.inspector.action_name_dict[read_action] + " (missing).")
						self.computed_inactive_action_dict[read_action].append(file_path)

		else:
			ui.print("List not found: " + self.pak_list_file_name)

	def computeActions(self):
		for dir_name, subdir_name_list, file_name_list in os.walk(self.source_dir):
			dir_name = dir_name[len(os.path.curdir + os.path.sep):]

			logging.debug("dir_name: " + str(dir_name) + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

			blacklisted_dir = False
			for subdir_name in dir_name.split(os.path.sep):
				for pattern in self.blacklist:
					logging.debug("comparing subdir path: " + subdir_name + " from dir path: " + dir_name + " with blacklist pattern: " + pattern)
					if fnmatch.fnmatch(subdir_name, pattern):
						logging.debug("found blacklisted directory: " + subdir_name)
						blacklisted_dir = True
						break
				if blacklisted_dir == True:
					break

			if blacklisted_dir == True:
				continue

			for file_name in file_name_list:
				file_path = os.path.join(dir_name, file_name)

				blacklisted_file = False
				for pattern in self.blacklist:
					base_path = os.path.basename(file_path)
					logging.debug("comparing file path: " + base_path + " with blacklist pattern: " + pattern)
					if fnmatch.fnmatch(base_path, pattern):
						logging.debug("found blacklisted file: " + file_path)
						blacklisted_file = True
						break

				if not blacklisted_file:
					unknown_file_path = True
					logging.debug("active actions: " + str(self.active_action_dict))
					logging.debug("inactive actions:" + str(self.inactive_action_dict))
					for read_action in self.active_action_dict.keys():
						if file_path in self.active_action_dict[read_action]:
							ui.print(file_path + ": Known file, will " + self.inspector.action_name_dict[read_action] + ".")
							self.computed_active_action_dict[read_action].append(file_path)
							unknown_file_path = False
						elif file_path in self.inactive_action_dict[read_action]:
							ui.print(file_path + ": Disabled known file, will ignore it.")
							self.computed_inactive_action_dict[read_action].append(file_path)
							unknown_file_path = False
					if unknown_file_path:
						computed_action = self.inspector.inspect(file_path)
						self.computed_active_action_dict[computed_action].append(file_path)

		self.active_action_dict = self.computed_active_action_dict
		self.active_inaction_dict = self.computed_inactive_action_dict

	def writeActions(self):
		pak_config_subdir = os.path.dirname(self.pak_list_file)
		if os.path.isdir(pak_config_subdir):
			logging.debug("found pakinfo subdir: " +  pak_config_subdir)
		else:
			logging.debug("create pakinfo subdir: " + pak_config_subdir)
			os.makedirs(pak_config_subdir, exist_ok=True)

		pak_list_file = open(self.pak_list_file, "w")
		for action in self.active_action_dict.keys():
			for file_path in sorted(self.active_action_dict[action]):
				line = action + "\t" + file_path
				pak_list_file.write(line + "\n")
		for action in self.computed_inactive_action_dict.keys():
			for file_path in sorted(self.inactive_action_dict[action]):
				line = "#" + action + "\t" + file_path
				pak_list_file.write(line + "\n")
		pak_list_file.close()

	def updateActions(self):
		self.readActions()
		self.computeActions()
		self.writeActions()


class Builder():
	def __init__(self, source_dir, build_dir, game_name, map_profile, compute_actions=False):
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.game_name = game_name
		self.map_profile = map_profile
		self.pak_list = BuildList(source_dir, game_name)

		# read predefined actions first
		self.pak_list.readActions()

		# implicit action list
		if compute_actions:
			self.pak_list.computeActions()

		# I want actions executed in this order
		self.builder_name_dict = OrderedDict()
		self.builder_name_dict["copy"] =					self.copyFile
		self.builder_name_dict["merge_bsp"] =				self.mergeBsp
		self.builder_name_dict["compile_bsp"] =				self.compileBsp
		self.builder_name_dict["compile_iqm"] =				self.compileIqm
		self.builder_name_dict["convert_jpg"] =				self.convertJpg
		self.builder_name_dict["convert_png"] =				self.convertPng
		self.builder_name_dict["convert_lossy_webp"] =		self.convertLossyWebp
		self.builder_name_dict["convert_lossless_webp"] =	self.convertLosslessWebp
		self.builder_name_dict["convert_crn"] =				self.convertCrn
		self.builder_name_dict["convert_normalized_crn"] =	self.convertNormalCrn
		self.builder_name_dict["convert_opus"] =			self.convertOpus
		self.builder_name_dict["keep"] =					self.keepFile
		self.builder_name_dict["ignore"] =					self.ignoreFile

		# TODO: set something else in verbose mode
		self.subprocess_stdout = subprocess.DEVNULL;
		self.subprocess_stderr = subprocess.DEVNULL;

	def getSourcePath(self, file_path):
		return self.source_dir + os.path.sep + file_path

	def getBuildPath(self, file_path):
		return self.build_dir + os.path.sep + file_path

	def isDifferent(self, source_path, build_path):
		if not os.path.isfile(build_path):
			logging.debug("build file not found: " + build_path)
			return True
		if os.stat(build_path).st_mtime != os.stat(source_path).st_mtime:
			logging.debug("build file has a different modification time than source file: " + build_path)
			return True
		logging.debug("build file has same modification time than source file: " + build_path)
		return False

	def createSubdirs(self, build_path):
		build_subdir = os.path.dirname(build_path)
		if os.path.isdir(build_subdir):
			logging.debug("found build subdir: " +  build_subdir)
		else:
			logging.debug("create build subdir: " + build_subdir)
			os.makedirs(build_subdir, exist_ok=True)

	# TODO: buildpack
	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.build_dir):
			logging.debug("found build dir: " + self.build_dir)
		else:
			logging.debug("create build dir: " + self.build_dir)
			os.makedirs(self.build_dir, exist_ok=True)

		logging.debug("reading build list from source dir: " + self.source_dir)

		# TODO: if already exist and older
		for action in self.builder_name_dict.keys():
			for file_path in self.pak_list.active_action_dict[action]:

				#TODO: if not source_path
				source_path = self.getSourcePath(file_path)

				# no need to use multiprocessing module to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				if action in ["merge_bsp"]:
					# action that can't be multithreaded
					# otherwise merge_bsp is called for every file part but must be called once for all files
					self.builder_name_dict[action](file_path)
				else:
					# threading.Thread's args expect an iterable, hence the comma inside parenthesis otherwise the string is passed as is
					thread = threading.Thread(target = self.builder_name_dict[action], args = (file_path,))

					while threading.active_count() > multiprocessing.cpu_count():
						pass

					thread.start()

	def ignoreFile(self, file_path):
		logging.debug("Ignoring: " + file_path)

	def keepFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		ui.print("Keep: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

	def copyFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		ui.print("Copy: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

		ext = os.path.splitext(build_path)[1][len(os.path.extsep):]
		if ext == "bsp":
			bsp_compiler = BspCompiler(self.source_dir, self.game_name, self.map_profile)
			bsp_compiler.compileBsp(build_path, os.path.dirname(build_path), stage_list=['nav', 'minimap'])

	def convertJpg(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileJpgNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) in ("jpg", "jpeg"):
			ui.print("File already in jpg, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to jpg: " + file_path)
			subprocess.call(["convert", "-verbose", "-quality", "92", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def convertPng(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFilePngNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "png":
			ui.print("File already in png, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to png: " + file_path)
			subprocess.call(["convert", "-verbose", "-quality", "100", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def convertLossyWebp(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileWebpNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "webp":
			ui.print("File already in webp, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to lossy webp: " + file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(file_path) + "_transient" + os.path.extsep + "png")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-q", "95", "-pass", "10", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def convertLosslessWebp(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileWebpNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "webp":
			ui.print("File already in webp, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to lossless webp: " + file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(file_path) + "_transient" + os.path.extsep + "png")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-lossless", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	# TODO: convertDDS
	def convertCrn(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileCrnNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "crn":
			ui.print("File already in crn, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to crn: " + file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(file_path) + "_transient" + os.path.extsep + "tga")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def convertNormalCrn(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileCrnNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "crn":
			ui.print("File already in crn, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to normalized crn: " + file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(file_path) + "_transient" + os.path.extsep + "tga")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-dxn", "-renormalize", "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def convertVorbis(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileOpusNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "ogg":
			ui.print("File already in vorbis, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to vorbis: " + file_path)
			subprocess.call(["ffmpeg", "-acodec", "libvorbis", "-i", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def convertOpus(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileOpusNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "opus":
			ui.print("File already in opus, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Convert to opus: " + file_path)
			subprocess.call(["opusenc", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def compileIqm(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileIqmNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "iqm":
			ui.print("File already in iqm, copy: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			ui.print("Compile to iqm: " + file_path)
			subprocess.call(["iqm", build_path, source_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def mergeBsp(self, file_path):
		source_path = self.getSourcePath(self.getDirBspDirNewName(file_path))
		build_path = self.getBuildPath(self.getDirBspNewName(file_path))

		self.createSubdirs(build_path)
		bspdir_path = self.getDirBspDirNewName(file_path)
		bsp_path = self.getDirBspNewName(file_path)

		# TODO if file already there
		#   see below for multithreading issues
		#	ui.warning("Bsp file already there, will do nothing with: " + build_path)
		#	return

		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file, do nothing: " + file_path)
			return
		logging.debug("looking for file in same bspdir than: " + file_path)
		for sub_path in self.pak_list.active_action_dict["merge_bsp"]:
			if sub_path.startswith(bspdir_path):
				ui.print("Merge to bsp: " + sub_path)
				self.pak_list.active_action_dict["merge_bsp"].remove(sub_path)
			else:
				logging.debug("file not from same bspdir: " + sub_path)
		bsp = Bsp()
		bsp.readDir(source_path)
		# TODO: if verbose
		bsp.writeFile(build_path)
		shutil.copystat(source_path, build_path)

		bsp_compiler = BspCompiler(self.source_dir, self.game_name, self.map_profile)
		bsp_compiler.compileBsp(build_path, os.path.dirname(build_path), stage_list=['nav', 'minimap'])

	def compileBsp(self, file_path):
		source_path = self.getSourcePath(file_path)
		copy_path = self.getBuildPath(file_path)
		build_path = self.getBuildPath(self.getFileBspNewName(file_path))
		bsp_path = self.getFileBspNewName(file_path)
		self.createSubdirs(build_path)

		# TODO if file already there
		#   you must ensure merge bsp and copy bsp are made before,
		#   beware of multithreading
		#	ui.warning("Bsp file already there, will only copy: " + source_path)
		#	return

		if not self.isDifferent(source_path, build_path):
			ui.verbose("Unmodified file " + build_path + ", will only copy: " + source_path)
			return

		ui.print("Compiling to bsp: " + file_path)

		bsp_compiler = BspCompiler(self.source_dir, self.game_name, self.map_profile)
		bsp_compiler.compileBsp(source_path, os.path.dirname(build_path))

	def getExt(self, file_path):
		return os.path.splitext(file_path)[1][len(os.path.extsep):].lower()

	def getFileJpgNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "jpg"

	def getFilePngNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "png"

	def getFileWebpNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "webp"

	def getFileCrnNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "crn"

	def getFileOpusNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "opus"

	def getFileIqmNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "iqm"

	def getFileBspNewName(self, file_path):
		return os.path.splitext(file_path)[0] + os.path.extsep + "bsp"

	def getDirBspDirNewName(self, file_path):
		return file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bspdir"

	def getDirBspNewName(self, file_path):
		return file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bsp"


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
		ui.print("Packing " + self.pk3dir_path + " to: " + self.pk3_path)
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
				ui.print("adding file to archive: " + file_path)
				pk3.write(file_path)

		logging.debug("closing: " + self.pk3_path)
		pk3.close()

		ui.print("Package written: " + self.pk3_path)


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
	args.add_argument("-g", "--game-profile", dest="game_profile", metavar="GAMENAME", default="unvanquished", help="use game profile %(metavar)s, default: %(default)s")
	args.add_argument("-sd", "--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	args.add_argument("-bp", "--build-prefix", dest="build_prefix", metavar="DIRNAME", default="build", help="build in prefix %(metavar)s, default: %(default)s")
	args.add_argument("-tp", "--test-parent", dest="test_parent_dir", metavar="DIRNAME", default="test", help="build test pakdir in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-pp", "--pkg-parent", dest="release_parent_dir", metavar="DIRNAME", default="pkg", help="build release pak in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-td", "--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pakdir as directory %(metavar)s")
	args.add_argument("-pf", "--pkg-file", dest="pkg_file", metavar="FILENAME", help="build release pak as file %(metavar)s")
	args.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", default="fast", help="build map with profile %(metavar)s, default: %(default)s")
	args.add_argument("-ev", "--extra-version", dest="extra_version", metavar="VERSION", help="add %(metavar)s to pak version string")
	args.add_argument("-u", "--update", dest="update", help="update paklist, compute actions", action="store_true")
	args.add_argument("-b", "--build", dest="build", help="build source pakdir", action="store_true")
	args.add_argument("-a", "--auto", dest="compute_actions", help="compute actions at build time and do not store paklist", action="store_true")
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
		ui.verbosely = True

	if args.update:
		pak_list = BuildList(args.source_dir, args.game_profile)
		pak_list.updateActions()

	if args.package or args.build or args.clean:
		if args.build_prefix:
			build_prefix = args.build_prefix

		if env_build_prefix:
			if args.build_prefix:
				ui.warning("build dir “" + build_prefix + "” superseded by env BUILDPREFIX: " + env_build_prefix)
			build_prefix = env_build_prefix

		if args.test_parent_dir:
			test_parent_dir = args.test_parent_dir

		if env_test_parent_dir:
			if args.test_parent_dir:
				ui.warning("build test dir “" + test_parent_dir + "” superseded by env TESTPARENT: " + env_test_parent_dir)
			test_parent_dir = env_test_parent_dir

		if args.release_parent_dir:
			release_parent_dir = args.release_parent_dir

		if env_release_parent_dir:
			if args.release_parent_dir:
				ui.warning("build pkg dir “" + release_parent_dir + "” superseded by env PKGPARENT: " + env_release_parent_dir)
			release_parent_dir = env_release_parent_dir

		if args.test_dir:
			test_dir = args.test_dir
		else:
			pak_config = PakConfig(args.source_dir)
			if not pak_config:
				ui.error("can't find pak configuration")
				return

			pak_name = pak_config.getKey("name")
			if not pak_name:
				# TODO: error msg
				return
			test_dir = build_prefix + os.path.sep + test_parent_dir + os.path.sep + pak_name + "_test" + os.path.extsep + "pk3dir"

	if args.build:
		if args.compute_actions:
			builder = Builder(args.source_dir, test_dir, args.game_profile, args.map_profile, compute_actions=True)
		else:
			builder = Builder(args.source_dir, test_dir, args.game_profile, args.map_profile)

		builder.build()

	if args.package:
		if args.pkg_file:
			pkg_file = args.pkg_file
		else:
			pak_config = PakConfig(args.source_dir)
			if not pak_config:
				ui.error("can't find pak configuration")
				return

			pak_name = pak_config.getKey("name")
			pak_version = pak_config.getKey("version")
			if not pak_name or not pak_version:
				# TODO: error msg
				return
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
