#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

from Urcheon import MapCompiler
from Urcheon import SourceTree
from Urcheon import Ui
from Urcheon.Bsp import Bsp
import fnmatch
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


class List():
	def __init__(self, source_dir, game_name):
		self.source_dir = source_dir
		self.action_list_file_name = ".pakinfo" + os.path.sep + "actions.txt"
		self.action_list_file = self.source_dir + os.path.sep + self.action_list_file_name

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

		self.inspector = SourceTree.Inspector(game_name)
		self.active_action_dict = OrderedDict()
		self.disabled_action_dict = OrderedDict()
		self.computed_active_action_dict = OrderedDict()
		self.computed_disabled_action_dict = OrderedDict()

		# I want lines printed in this order
		for action_name in self.inspector.action_name_dict.keys():
			self.active_action_dict[action_name] = []
			self.disabled_action_dict[action_name] = []
			self.computed_active_action_dict[action_name] = []
			self.computed_disabled_action_dict[action_name] = []

	def readActions(self):
		if os.path.isfile(self.action_list_file):
			action_list_file = open(self.action_list_file, "r")
			line_list = [line.strip() for line in action_list_file]
			action_list_file.close()
			action_line_pattern = re.compile(r"^[ \t]*(?P<action_name>[^ \t]*)[ \t]*(?P<file_path>.*)$")
			quoted_path_pattern = re.compile(r"^\"(?P<file_path>.*)\"[ \t]*$")
			disabled_action_pattern = re.compile(r"^#[ \t]*(?P<action_name>.*)$")

			for line in line_list:
				line_match = action_line_pattern.match(line)
				if line_match:
					action_name = line_match.group("action_name")
					file_path = line_match.group("file_path")

					file_match = quoted_path_pattern.match(file_path)
					if file_match:
						file_path = file_match.group("file_path")

				disabled_action_match = disabled_action_pattern.match(action_name)
				if disabled_action_match:
					disabled_action = disabled_action_match.group("action_name")
					Ui.print(file_path + ": Known rule, will not " + disabled_action + " (disabled action).")
					self.disabled_action_dict[disabled_action].append(file_path)
				else:
					if os.path.isfile(file_path):
						Ui.print(file_path + ": Known rule, will " + self.inspector.action_name_dict[action_name] + " (predefined action).")
						self.active_action_dict[action_name].append(file_path)
					else:
						Ui.print(file_path + ": Known rule, will not " + self.inspector.action_name_dict[action_name] + " (missing file).")
						self.computed_disabled_action_dict[action_name].append(file_path)

		else:
			Ui.print("List not found: " + self.action_list_file_name)

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
					logging.debug("inactive actions:" + str(self.disabled_action_dict))
					for read_action in self.active_action_dict.keys():
						if file_path in self.active_action_dict[read_action]:
							Ui.print(file_path + ": Known file, will " + self.inspector.action_name_dict[read_action] + ".")
							self.computed_active_action_dict[read_action].append(file_path)
							unknown_file_path = False
						elif file_path in self.disabled_action_dict[read_action]:
							Ui.print(file_path + ": Disabled known file, will ignore it.")
							self.computed_disabled_action_dict[read_action].append(file_path)
							unknown_file_path = False
					if unknown_file_path:
						computed_action = self.inspector.inspect(file_path)
						self.computed_active_action_dict[computed_action].append(file_path)

		self.active_action_dict = self.computed_active_action_dict
		self.active_inaction_dict = self.computed_disabled_action_dict

	def writeActions(self):
		pak_config_subdir = os.path.dirname(self.action_list_file)
		if os.path.isdir(pak_config_subdir):
			logging.debug("found pakinfo subdir: " +  pak_config_subdir)
		else:
			logging.debug("create pakinfo subdir: " + pak_config_subdir)
			os.makedirs(pak_config_subdir, exist_ok=True)

		action_list_file = open(self.action_list_file, "w")
		for action in self.active_action_dict.keys():
			for file_path in sorted(self.active_action_dict[action]):
				line = action + " " + file_path
				action_list_file.write(line + "\n")
		for action in self.computed_disabled_action_dict.keys():
			for file_path in sorted(self.disabled_action_dict[action]):
				line = "#" + action + " " + file_path
				action_list_file.write(line + "\n")
		action_list_file.close()

	def updateActions(self):
		self.readActions()
		self.computeActions()
		self.writeActions()


class Directory():
	def __init__(self):

		# I want actions printed and executed in this order
		self.directory = [
			Copy,
			ConvertJpg,
			ConvertPng,
			ConvertCrn,
			ConvertNormalCrn,
			ConvertLossyWebp,
			ConvertLosslessWebp,
			ConvertVorbis,
			ConvertOpus,
			CompileIqm,
			MergeBsp,
			CompileBsp,
			Keep,
			Ignore,
		]


class Action():
	keyword = "dumb"
	description = "dumb action"
	parallel = True

	# TODO: set something else in verbose mode
	subprocess_stdout = subprocess.DEVNULL;
	subprocess_stderr = subprocess.DEVNULL;

	def __init__(self, source_dir, build_dir, file_path, game_name=None, map_profile=None):
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.file_path = file_path
		self.game_name = game_name
		self.map_profile = map_profile

	def run(self):
		Ui.print("Dumb action: " + self.file_path)

	def getFileNewName(self):
		return self.file_path

	def getSourcePath(self):
		return self.source_dir + os.path.sep + self.file_path

	def getBuildPath(self):
		return self.build_dir + os.path.sep + self.getFileNewName()

	def getExt(self):
		return os.path.splitext(self.file_path)[1][len(os.path.extsep):].lower()
	
	def isDifferent(self, source_path, build_path):
		if not os.path.isfile(build_path):
			logging.debug("build file not found: " + build_path)
			return True
		if os.stat(build_path).st_mtime != os.stat(source_path).st_mtime:
			logging.debug("build file has a different modification time than source file: " + build_path)
			return True
		logging.debug("build file has same modification time than source file: " + build_path)
		return False

	def createSubdirs(self):
		build_subdir = os.path.dirname(self.getBuildPath())
		if os.path.isdir(build_subdir):
			logging.debug("found build subdir: " +  build_subdir)
		else:
			logging.debug("create build subdir: " + build_subdir)
			os.makedirs(build_subdir, exist_ok=True)


class Ignore(Action):
	keyword = "ignore"
	description = "ignore file"
	parallel = True

	def run(self):
		Ui.print("Ignoring: " + self.file_path)

	def getFileNewName(self):
		return self.file_path


class Keep(Action):
	keyword = "keep"
	description = "keep file"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		Ui.print("Keep: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return self.file_path

class Copy(Action):
	keyword = "copy"
	description = "copy file"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		Ui.print("Copy: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

		# TODO: add specific rule for that
		ext = os.path.splitext(build_path)[1][len(os.path.extsep):]
		if ext == "bsp":
			bsp_compiler = MapCompiler.Bsp(self.source_dir, self.game_name, self.map_profile)
			bsp_compiler.compileBsp(build_path, os.path.dirname(build_path), stage_list=['nav', 'minimap'])

	def getFileNewName(self):
		return self.file_path


class ConvertJpg(Action):
	keyword = "convert_jpg"
	description = "convert to jpg format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() in ("jpg", "jpeg"):
			Ui.print("File already in jpg, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to jpg: " + self.file_path)
			subprocess.call(["convert", "-verbose", "-quality", "92", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "jpg"


class ConvertPng(Action):
	keyword = "convert_png"
	description = "convert to png format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "png":
			Ui.print("File already in png, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to png: " + self.file_path)
			subprocess.call(["convert", "-verbose", "-quality", "100", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "png"


class ConvertLossyWebp(Action):
	keyword = "convert_lossy_webp"
	description = "convert to lossy webp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath(self.geteNewName(self.file_path))
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "webp":
			Ui.print("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to lossy webp: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(self.file_path) + "_transient" + os.path.extsep + "png")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-q", "95", "-pass", "10", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "webp"

class ConvertLosslessWebp(Action):
	keyword = "convert_lossless_webp"
	description = "convert to lossless webp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "webp":
			Ui.print("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to lossless webp: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(self.file_path) + "_transient" + os.path.extsep + "png")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-lossless", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "webp"



# TODO: convertDDS
class ConvertCrn(Action):
	keyword = "convert_crn"
	description = "convert to crn format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "crn":
			Ui.print("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to crn: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(self.file_path) + "_transient" + os.path.extsep + "tga")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "crn"


class ConvertNormalCrn(Action):
	keyword = "convert_normalized_crn"
	description = "convert to normalized crn format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "crn":
			Ui.print("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to normalized crn: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(self.file_path) + "_transient" + os.path.extsep + "tga")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-dxn", "-renormalize", "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "crn"


class ConvertVorbis(Action):
	keyword = "convert_vorbis"
	description = "convert to vorbis format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "ogg":
			Ui.print("File already in vorbis, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to vorbis: " + self.file_path)
			subprocess.call(["ffmpeg", "-acodec", "libvorbis", "-i", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "ogg"


class ConvertOpus(Action):
	keyword = "convert_opus"
	description = "convert to opus format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "opus":
			Ui.print("File already in opus, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to opus: " + self.file_path)
			subprocess.call(["opusenc", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "opus"


class CompileIqm(Action):
	keyword = "complile_iqm"
	description = "compile to iqm format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getBuildPath()
		self.createSubdirs()
		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		if self.getExt() == "iqm":
			Ui.print("File already in iqm, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Compile to iqm: " + self.file_path)
			subprocess.call(["iqm", build_path, source_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "iqm"


class MergeBsp(Action):
	keyword = "merge_bsp"
	description = "merge into a bsp file"
	parallel = True

	def run(self):
		# TODO: ensure bsp is already copied/compiled if modifying copied/compiled bsp

		source_path = self.getSourcePath()
		build_path = self.getBuildPath()

		self.createSubdirs()
		bspdir_path = self.getBspDirNewName(self.file_path)
		bsp_path = self.getFileNewName(self.file_path)

		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file, do nothing: " + self.file_path)
			return
		logging.debug("looking for file in same bspdir than: " + self.file_path)
		for sub_path in self.action_list.active_action_dict["merge_bsp"]:
			if sub_path.startswith(bspdir_path):
				Ui.print("Merge to bsp: " + sub_path)
				self.action_list.active_action_dict["merge_bsp"].remove(sub_path)
			else:
				logging.debug("file not from same bspdir: " + sub_path)
		bsp = Bsp()
		bsp.readDir(source_path)
		# TODO: if verbose
		bsp.writeFile(build_path)
		shutil.copystat(source_path, build_path)

		bsp_compiler = MapCompiler.Bsp(self.source_dir, self.game_name, self.map_profile)
		bsp_compiler.compileBsp(build_path, os.path.dirname(build_path), stage_list=['nav', 'minimap'])

	def getSourcePath(self):
		return self.source_dir + os.path.sep + self.getBspDirNewName()

	def getBspDirNewName(self):
		return self.file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bspdir"

	def getFileNewName(self):
		return self.file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bsp"


class CompileBsp(Action):
	keyword = "compile_bsp"
	description = "compile to bsp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		copy_path = self.getBuildPath()
		build_path = self.getBuildPath()
		bsp_path = self.getFileNewName()
		self.createSubdirs()

		# TODO if file already there
		#   you must ensure merge bsp and copy bsp are made before
		#   beware of multithreading
		#	Ui.warning("Bsp file already there, will reuse: " + source_path)
		#	return

		if not self.isDifferent(source_path, build_path):
			Ui.verbose("Unmodified file " + build_path + ", will reuse: " + source_path)
			return

		Ui.print("Compiling to bsp: " + self.file_path)

		bsp_compiler = MapCompiler.Bsp(self.source_dir, self.game_name, self.map_profile)
		bsp_compiler.compileBsp(source_path, os.path.dirname(build_path))

	def getFileNewName(self):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + "bsp"

