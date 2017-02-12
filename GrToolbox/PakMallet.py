#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import os
import sys
import shutil
import subprocess
import operator
import importlib
import argparse
import logging
import fnmatch
import zipfile
import configparser
import tempfile
import threading
import multiprocessing
from collections import OrderedDict

import GrToolbox.BspCutter

# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files

class Log():
	# This is NOT the runtime logging, it's the package build logging
	def __init__(self):
		self.verbosely = False

	def print(self, message):
		# I duplicate print() because I will add color support and verbose/quiet support in the future
		print(message)

	def verbose(self, message):
		if self.verbosely:
			print(message)

	def warning(self, message):
		print("Warning: " + message)

	def notice(self, message):
		print("Notice: " + message)

	def error(self, message):
		print("Error: " + message)

log = Log()

class PakConfig():
	def __init__(self, game_name):
		self.game = importlib.import_module("pak_profiles." + game_name)
		self.config_file_type_dict = [variable for variable in dir(self.game) if variable.startswith("file_")]
		self.file_type_dict = {}
		self.file_type_weight_dict = {}
		self.expandFileTypes()

	def inheritFileType(self, config_file_type_dict):
		if "inherit" in config_file_type_dict.keys():
			logging.debug("inherit from file type: " + config_file_type_dict["inherit"])
			inherited_file_type, weight = self.inheritFileType(getattr(self.game, config_file_type_dict["inherit"]))
		else:
			inherited_file_type, weight = {}, 0

		inspector = Inspector(None)

		for keyword in list(inspector.inspector_name_dict.keys()) + [
			"description",
			"action",
		]:
			if keyword in config_file_type_dict.keys():
				inherited_file_type[keyword] = config_file_type_dict[keyword]
			elif keyword not in inherited_file_type.keys():
				inherited_file_type[keyword] = None

		for keyword in inspector.inspector_name_dict.keys():
			if isinstance(inherited_file_type[keyword], str):
				inherited_file_type[keyword] = [ inherited_file_type[keyword] ]

		return inherited_file_type, weight + 1

	def expandFileTypes(self):
		for file_type in self.config_file_type_dict:
			logging.debug("expanding file type: " + file_type)
			self.file_type_dict[file_type] = []
			self.file_type_dict[file_type], self.file_type_weight_dict[file_type] = self.inheritFileType(getattr(self.game, file_type))


class Inspector():
	def __init__(self, game_name):
		if game_name:
			self.config = PakConfig(game_name)
		else:
			self.config = None
		self.inspector_name_dict = {
			"file_name":			self.inspectFileName,
			"file_ext":				self.inspectFileExt,
			"file_base":			self.inspectFileBase,
			"file_prefix":			self.inspectFilePrefix,
			"file_suffix":			self.inspectFileSuffix,
			"dir_ancestor_name":	self.inspectDirAncestorName,
			"dir_father_name":		self.inspectDirFatherName,
			"dir_father_ext":		self.inspectDirFatherExt,
			"dir_grandfather_name":	self.inspectDirGrandFatherName,
			"dir_grandfather_ext":	self.inspectDirGrandFatherExt,
		}
		# I want lines printed in this order
		self.action_name_dict = OrderedDict()
		self.action_name_dict["copy"] =						"copy file"
		self.action_name_dict["merge_bsp"] =				"merge into a bsp file"
		self.action_name_dict["compile_bsp"] =				"compile to bsp format"
		self.action_name_dict["compile_iqm"] =				"compile to iqm format"
		self.action_name_dict["convert_crn"] =				"convert to crn format"
		self.action_name_dict["convert_normalized_crn"] =	"convert to normalized crn format"
		self.action_name_dict["convert_jpg"] =				"convert to jpg format"
		self.action_name_dict["convert_png"] =				"convert to png format"
		self.action_name_dict["convert_lossy_webp"] =		"convert to lossy webp format"
		self.action_name_dict["convert_lossless_webp"] =	"convert to lossless format"
		self.action_name_dict["convert_opus"] =				"convert to opus format"
		self.action_name_dict["keep"] =						"keep file"
		self.action_name_dict["ignore"] =				 	"ignore file"

	def inspectFileName(self, file_path, file_name):
		name = os.path.basename(file_path)
		return name in file_name

	def inspectFileExt(self, file_path, file_ext):
		ext = os.path.splitext(file_path)[1][len(os.path.extsep):]
		return ext in file_ext

	def inspectFileBase(self, file_path, file_base):
		base = os.path.splitext(os.path.basename(file_path))[0]
		return base in file_base

	def inspectFilePrefix(self, file_path, file_prefix):
		suffix = os.path.basename(file_path).split('_')[0]
		return suffix in file_prefix

	def inspectFileSuffix(self, file_path, file_suffix):
		suffix = os.path.splitext(os.path.basename(file_path))[0].split('_')[-1]
		return suffix in file_suffix

	def inspectDirAncestorName(self, file_path, dir_name):
		previous = file_path
		while file_path != "":
			previous = file_path
			file_path = os.path.split(file_path)[0]
		return previous in dir_name

	def inspectDirFatherName(self, file_path, dir_name):
		father = os.path.split(file_path)[0]
		return father in dir_name

	def inspectDirFatherExt(self, file_path, dir_ext):
		ext = os.path.splitext(os.path.split(file_path)[0])[1][len(os.path.extsep):]
		return ext in dir_ext

	def inspectDirGrandFatherName(self, file_path, dir_name):
		grandfather = os.path.split(os.path.split(file_path)[0])[0]
		return grandfather in dir_name

	def inspectDirGrandFatherExt(self, file_path, dir_ext):
		ext = os.path.splitext(os.path.split(os.path.split(file_path)[0])[0])[1][len(os.path.extsep):]
		return ext in dir_ext

	def inspect(self, file_path):
		file_type_ordered_list = [x[0] for x in sorted(self.config.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
		logging.debug("looking for file path:" + file_path)
#		logging.debug("will try file types in this order: ", str(file_type_ordered_list))

		action = "keep"
		for file_type_name in file_type_ordered_list:
			logging.debug("trying file type:" + file_type_name)
			criteria_dict = self.config.file_type_dict[file_type_name].copy()
			file_type_action = criteria_dict.pop("action")
			file_type_description = criteria_dict.pop("description")

			matched_file_type = True
			for criteria in criteria_dict.keys():
				logging.debug("trying criteria: " + criteria + ", value: " + str(criteria_dict[criteria]))
				if criteria_dict[criteria] != None:
					matched_criteria = self.inspector_name_dict[criteria](file_path, criteria_dict[criteria])
					logging.debug("matched criteria: " + str(matched_criteria))
					if not matched_criteria:
						matched_file_type = False
						break

			if matched_file_type:
				action = file_type_action
				description  = file_type_description
				break

		if action == "keep":
			log.warning(file_path + ": unknown file found, will " + self.action_name_dict[action] + ".")
		else:
			log.print(file_path + ": " + description + " found, will " + self.action_name_dict[action] + ".")

		return action


class PakList():
	def __init__(self, file_dir, game_name):
		self.file_dir = file_dir
		self.pak_list_file_name = ".pakinfo" + os.path.sep + "paklist"

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
		if os.path.isfile(self.pak_list_file_name):
			pak_list_file = open(self.pak_list_file_name, "r")
			line_list = [line.strip() for line in pak_list_file]
			pak_list_file.close()
			for line in line_list:
				# TODO: regex
				action = line.split(" ")[0]
				file_path = line[len(action) + 1:]
				if action[0] == '#':
					inactive_action = action[1:]
					logging.debug("known inactive action: " + inactive_action + " for file: " + file_path)
					self.inactive_action_dict[inactive_action].append(file_path)
				else:
					if os.path.isfile(file_path):
						logging.debug("known action: " + action + " for file: " + file_path)
						self.active_action_dict[action].append(file_path)
					else:
						log.print("disabling action: " + action + " for missing file: " + file_path)
						self.computed_inactive_action_dict[action].append(file_path)

		else:
			log.print("List not found: " + self.pak_list_file_name)

	def computeActions(self):
		for dir_name, subdir_name_list, file_name_list in os.walk(self.file_dir):
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
							log.print(file_path + ": Known file, will " + self.inspector.action_name_dict[read_action] + ".")
							self.computed_active_action_dict[read_action].append(file_path)
							unknown_file_path = False
						elif file_path in self.inactive_action_dict[read_action]:
							log.print(file_path + ": Disabled known file, will ignore it.")
							self.computed_inactive_action_dict[read_action].append(file_path)
							unknown_file_path = False
					if unknown_file_path:
						action = self.inspector.inspect(file_path)
						self.computed_active_action_dict[action].append(file_path)

				self.active_action_dict = self.computed_active_action_dict
				self.active_inaction_dict = self.computed_inactive_action_dict

	def writeActions(self):
		pak_info_subdir = os.path.dirname(self.pak_list_file_name)
		if os.path.isdir(pak_info_subdir):
			logging.debug("found pakinfo subdir: " +  pak_info_subdir)
		else:
			logging.debug("create pakinfo subdir: " + pak_info_subdir)
			os.makedirs(pak_info_subdir)

		pak_list_file = open(self.pak_list_file_name, "w")
		for action in self.active_action_dict.keys():
			for file_path in sorted(self.active_action_dict[action]):
				line = action + " " + file_path
				pak_list_file.write(line + "\n")
		for action in self.computed_inactive_action_dict.keys():
			for file_path in sorted(self.inactive_action_dict[action]):
				line = "#" + action + " " + file_path
				pak_list_file.write(line + "\n")
		pak_list_file.close()


class BspCompiler():
	def __init__(self, source_dir, game_name, map_profile):
		self.map_config = configparser.ConfigParser()
		self.source_dir = source_dir
		self.map_profile = map_profile
		self.build_stage_dict = OrderedDict()

		# I want compilation in this order:
		self.build_stage_dict["bsp"] = None
		self.build_stage_dict["vis"] = None
		self.build_stage_dict["light"] = None

		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None;
		self.subprocess_stderr = None;

		# TODO: check
		default_ini_file = game_name + os.path.extsep + "ini"
		default_ini_path = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0]))) + os.path.sep + "map_profiles" + os.path.sep + default_ini_file

		self.readIni(default_ini_path)

	def readIni(self, ini_path):
		logging.debug("reading map profile: " + ini_path)
		self.map_config.read(ini_path)

		logging.debug("build profiles: " + str(self.map_config.sections()))
		for map_profile in self.map_config.sections():
			logging.debug("build profile found: " + map_profile)

			if map_profile == self.map_profile:
				logging.debug("will use profile: " + map_profile)

				for build_stage in self.map_config[map_profile].keys():
					if not build_stage in self.build_stage_dict.keys():
						log.warning("unknown stage in " + ini_path + ": " + build_stage)

					else:
						logging.debug("add build param for stage " + build_stage + ": " + self.map_config[map_profile][build_stage])
						self.build_stage_dict[build_stage] = self.map_config[map_profile][build_stage]


	def compileBsp(self, map_path, build_prefix):
		logging.debug("building " + map_path + " to prefix: " + build_prefix)

		map_base = os.path.splitext(os.path.basename(map_path))[0]
		lightmapdir_path = build_prefix + os.path.sep + map_base

		map_profile_path =  self.source_dir + os.path.sep + ".pakinfo" + os.path.sep + "maps" + os.path.sep + map_base + os.path.extsep + "ini"

		os.makedirs(build_prefix, exist_ok=True)

		if not os.path.isfile(map_profile_path):
			logging.debug("map profile not found, will use default: " + map_profile_path)
		else:
			log.print("Customized build profile found: " + map_profile_path)
			self.readIni(map_profile_path)

		prt_handle, prt_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "prt")
		srf_handle, srf_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "srf")
		bsp_path = build_prefix + os.path.sep + map_base + os.path.extsep + "bsp"

		for build_stage in self.build_stage_dict.keys():
			if self.build_stage_dict[build_stage] == None:
				continue

			log.print("Building " + map_path + ", stage: " + build_stage)

			source_path = map_path
			extended_option_list = {}
			if build_stage == "bsp":
				extended_option_list = ["-prtfile", prt_path, "-srffile", srf_path, "-bspfile", bsp_path]
				source_path = map_path
			elif build_stage == "vis":
				extended_option_list = ["-prtfile", prt_path]
				source_path = bsp_path
			elif build_stage == "light":
				extended_option_list = ["-srffile", srf_path, "-bspfile", bsp_path, "-lightmapdir", lightmapdir_path]
				source_path = map_path

			# pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
			pakpath_list = ["-fs_pakpath", self.source_dir]

			pakpath_env = os.getenv("PAKPATH")
			if pakpath_env:
				for pakpath in pakpath_env.split(":"):
					pakpath_list += ["-fs_pakpath", pakpath]

			# TODO: game independant
			call_list = ["q3map2", "-game", "unvanquished"] + ["-" + build_stage] + pakpath_list + extended_option_list + self.build_stage_dict[build_stage].split(" ") + [source_path]
			logging.debug("call list: " + str(call_list))
			# TODO: verbose?
			log.print("Build command: " + " ".join(call_list))
			subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		if os.path.isfile(prt_path):
			os.remove(prt_path)

		if os.path.isfile(srf_path):
			os.remove(srf_path)


class PakBuilder():
	def __init__(self, source_dir, build_dir, game_name, map_profile, compute_actions=False):
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.game_name = game_name
		self.map_profile = map_profile
		self.pak_list = PakList(source_dir, game_name)
		self.pak_list.readActions()
		if compute_actions:
			self.pak_list.computeActions()
		self.bsp_list = []

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
			os.makedirs(build_subdir)

	# TODO: buildpack
	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.build_dir):
			logging.debug("found build dir: " + self.build_dir)
		else:
			logging.debug("create build dir: " + self.build_dir)
			os.makedirs(self.build_dir)

		logging.debug("reading build list from source dir: " + self.source_dir)

		# TODO: if already exist and older
		for action in self.builder_name_dict.keys():
			for file_path in self.pak_list.active_action_dict[action]:

				#TODO: if not source_path
				source_path = self.getSourcePath(file_path)

				# no need to use multiprocessing to manage task contention, since each task will call its own process
				# using threads on one core is faster, and it does not prevent tasks to be able to use other cores

				# threading.Thread's args expect an iterable, hence the comma inside parenthesis otherwise the string is passed as is
				thread = threading.Thread(target = self.builder_name_dict[action], args = (file_path,))
				while threading.active_count() > multiprocessing.cpu_count():
					pass
				thread.start()

		logging.debug("bsp list: " + str(self.bsp_list))
		for bsp_path in self.bsp_list:
			self.createMiniMap(bsp_path)
			self.createNavMeshes(bsp_path)

	def ignoreFile(self, file_path):
		logging.debug("Ignoring: " + file_path)

	def keepFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		log.print("Keep: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

	def copyFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		log.print("Copy: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)
		ext = os.path.splitext(build_path)[1][len(os.path.extsep):]
		if ext == "bsp":
			self.bsp_list.append(file_path)

	def convertJpg(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileJpgNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) in ("jpg", "jpeg"):
			log.print("File already in jpg, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to jpg: " + file_path)
			subprocess.call(["convert", "-verbose", "-quality", "92", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def convertPng(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFilePngNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "png":
			log.print("File already in png, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to png: " + file_path)
			subprocess.call(["convert", "-verbose", "-quality", "100", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def convertLossyWebp(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileWebpNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "webp":
			log.print("File already in webp, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to lossy webp: " + file_path)
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
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "webp":
			log.print("File already in webp, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to lossless webp: " + file_path)
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
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "crn":
			log.print("File already in crn, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to crn: " + file_path)
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
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "crn":
			log.print("File already in crn, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to crn: " + file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(file_path) + "_transient" + os.path.extsep + "tga")
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-dxn", "-renormalize", "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)
		shutil.copystat(source_path, build_path)

	# TODO: convertVorbis
	def convertOpus(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileOpusNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "opus":
			log.print("File already in opus, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to opus: " + file_path)
			subprocess.call(["opusenc", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def compileIqm(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileIqmNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "iqm":
			log.print("File already in iqm, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Compiling to iqm: " + file_path)
			subprocess.call(["iqm", build_path, source_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		shutil.copystat(source_path, build_path)

	def mergeBsp(self, file_path):
		source_path = self.getSourcePath(self.getDirBspDirNewName(file_path))
		build_path = self.getBuildPath(self.getDirBspNewName(file_path))
		self.createSubdirs(build_path)
		bspdir_path = self.getDirBspDirNewName(file_path)
		bsp_path = self.getDirBspNewName(file_path)
		if bspdir_path in self.bsp_list:
			log.warning("Bsp file already there, will do nothing with: " + build_path)
			return
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		logging.debug("looking for file in same bspdir than: " + file_path)
		for sub_path in self.pak_list.active_action_dict["merge_bsp"]:
			if sub_path.startswith(bspdir_path):
				log.print("Merge to bsp: " + sub_path)
				self.pak_list.active_action_dict["merge_bsp"].remove(sub_path)
			else:
				logging.debug("file not from same bspdir: " + sub_path)
		bsp = BspCutter.Bsp()
		bsp.readDir(source_path)
		# TODO: if verbose
		bsp.writeFile(build_path)
		shutil.copystat(source_path, build_path)
		self.bsp_list.append(bsp_path)

	def compileBsp(self, file_path):
		source_path = self.getSourcePath(file_path)
		copy_path = self.getBuildPath(file_path)
		build_path = self.getBuildPath(self.getFileBspNewName(file_path))
		bsp_path = self.getFileBspNewName(file_path)
		self.createSubdirs(build_path)
		if build_path in self.bsp_list:
			log.warning("Bsp file already there, will only copy: " + source_path)
			return
		if not self.isDifferent(source_path, build_path):
			log.verbose("Unmodified file " + build_path + ", will only copy: " + source_path)
			return

		log.print("Compiling to bsp: " + file_path)

		bsp_compiler = BspCompiler(self.source_dir, self.game_name, self.map_profile)
		bsp_compiler.compileBsp(source_path, os.path.dirname(build_path))

		# TODO: for all files created
#		shutil.copystat(source_path, build_path)

		log.print("Copying map: " + file_path)
		shutil.copyfile(source_path, copy_path)
		shutil.copystat(source_path, copy_path)

		self.bsp_list.append(bsp_path)

	def createMiniMap(self, file_path):
		build_path = self.getBuildPath(file_path)
		# TODO: if minimap not newer
		# TODO: put q3map2 profile in game profile
		log.print("Creating MiniMap for: " + file_path)
#		subprocess.call(["q3map2", "-game", "unvanquished", "-minimap", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		q3map2_helper_path = os.path.join(sys.path[0], "tools", "q3map2_helper")
		subprocess.call([q3map2_helper_path, "--minimap", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

	def createNavMeshes(self, file_path):
		build_path = self.getBuildPath(file_path)
		log.print("Creating NavMeshes for: " + file_path)
		subprocess.call(["q3map2", "-game", "unvanquished", "-nav", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

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
			os.makedirs(pack_subdir)

	def pack(self):
		log.print("Packing " + self.pk3dir_path + " to: " + self.pk3_path)
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
				log.print("adding file to archive: " + file_path)
				pk3.write(file_path)

		logging.debug("closing: " + self.pk3_path)
		pk3.close()

		log.print("Package written: " + self.pk3_path)


class PakInfo():
	def __init__(self, source_dir):
		pak_info_path = source_dir + os.path.sep + ".pakinfo" + os.path.sep + "pakinfo"
		logging.debug("reading pakinfo: " + pak_info_path)

		if not os.path.isfile(pak_info_path):
			log.error("Missing pakinfo file")
			raise Exception("pakinfo", "missing")
			return

		pak_info_file = open(pak_info_path, "r")
		line_list = [line.strip() for line in pak_info_file]
		pak_info_file.close()

		self.key_dict = {}
		for line in line_list:
			# TODO: regex
			key, value = line.split(": ")
			self.key_dict[key] = value

	def getKey(self, key_name):
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			log.error("Unknown key in pakinfo file: " + key_name)
			return None


def main():

	args = argparse.ArgumentParser(description="%(prog)s is a pak builder for my lovely granger.")
	args.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	args.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	args.add_argument("-g", "--game-profile", dest="game_profile", metavar="GAMENAME", default="unvanquished", help="use game profile %(metavar)s, default: %(default)s")
	args.add_argument("-sd", "--source-dir", dest="source_dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	args.add_argument("-bp", "--build-prefix", dest="build_prefix", metavar="DIRNAME", default="build", help="build in prefix %(metavar)s, default: %(default)s")
	args.add_argument("-tp", "--test-parent", dest="test_parent", metavar="DIRNAME", default="test", help="build test pk3dir in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-pp", "--pkg-parent", dest="pkg_parent", metavar="DIRNAME", default="pkg", help="build release pk3 in parent directory %(metavar)s, default: %(default)s")
	args.add_argument("-td", "--test-dir", dest="test_dir", metavar="DIRNAME", help="build test pk3dir as directory %(metavar)s")
	args.add_argument("-pf", "--pkg-file", dest="pkg_file", metavar="FILENAME", help="build release pk3 as file %(metavar)s")
	args.add_argument("-mp", "--map-profile", dest="map_profile", metavar="PROFILE", default="fast", help="build map with profile %(metavar)s, default: %(default)s")
	args.add_argument("-ev", "--extra-version", dest="extra_version", metavar="VERSION", help="add %(metavar)s to pk3 version string")
	args.add_argument("-u", "--update", dest="update", help="update paklist", action="store_true")
	args.add_argument("-b", "--build", dest="build", help="build pak", action="store_true")
	args.add_argument("-a", "--auto", dest="compute_actions", help="compute actions at build time", action="store_true")
	args.add_argument("-p", "--package", dest="package", help="compress pak", action="store_true")

	args = args.parse_args()

	env_build_prefix = os.getenv("BUILDPREFIX")
	env_test_parent = os.getenv("TESTPARENT")
	env_pkg_parent = os.getenv("PKGPARENT")

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))

	if args.verbose:
		log.verbosely = True

	if args.update:
		pak_list = PakList(args.source_dir, args.game_profile)
		pak_list.readActions()
		pak_list.computeActions()
		pak_list.writeActions()

	if args.package or args.build:
		if args.build_prefix:
			build_prefix = args.build_prefix

		if env_build_prefix:
			if args.build_prefix:
				log.warning("build dir “" + build_prefix + "” superseded by env BUILDPREFIX: " + env_build_prefix)
			build_prefix = env_build_prefix

		if args.test_parent:
			test_parent = args.test_parent

		if env_test_parent:
			if args.test_parent:
				log.warning("build test dir “" + test_parent + "” superseded by env TESTPARENT: " + env_test_parent)
			test_parent = env_test_parent

		if args.pkg_parent:
			pkg_parent = args.pkg_parent

		if env_pkg_parent:
			if args.pkg_parent:
				log.warning("build pkg dir “" + pkg_parent + "” superseded by env PKGPARENT: " + env_pkg_parent)
			pkg_parent = env_pkg_parent

		if args.test_dir:
			test_dir = args.test_dir
		else:
			try:
				pak_info = PakInfo(args.source_dir)
			except:
				return

			pak_pakname = pak_info.getKey("pakname")
			if not pak_pakname:
				return
			test_dir = build_prefix + os.path.sep + test_parent + os.path.sep + pak_pakname + "_test" + os.path.extsep + "pk3dir"

	if args.build:
		if args.compute_actions:
			builder = PakBuilder(args.source_dir, test_dir, args.game_profile, args.map_profile, compute_actions=True)
		else:
			builder = PakBuilder(args.source_dir, test_dir, args.game_profile, args.map_profile)
		builder.build()

	if args.package:
		if args.pkg_file:
			pkg_file = args.pkg_file
		else:
			pak_info = PakInfo(args.source_dir)
			if not pak_info:
				return
			pak_pakname = pak_info.getKey("pakname")
			pak_version = pak_info.getKey("version")
			if not pak_pakname or not pak_version:
				return
			if args.extra_version:
				pak_version += args.extra_version
			pkg_file = build_prefix + os.path.sep + pkg_parent + os.path.sep + pak_pakname + "_" + pak_version + os.path.extsep + "pk3"

		packer = Packer(test_dir, pkg_file)
		packer.pack()


if __name__ == "__main__":
	main()
