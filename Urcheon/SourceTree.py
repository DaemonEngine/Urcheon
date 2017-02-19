#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon import Action
from Urcheon import Ui
from collections import OrderedDict
import configparser
import fnmatch
import importlib
import logging
import operator
import os
import subprocess


class Config():
	def __init__(self, source_dir):
		# TODO: check absolute path (check in map ini too)
		config_pak_path = source_dir + os.path.sep + ".pakinfo" + os.path.sep + "pak" + os.path.extsep +  "ini"
		self.pak_config = configparser.ConfigParser()
		self.key_dict = None
		self.loaded = False
		self.source_dir = source_dir

		if os.path.isfile(config_pak_path):
			self.readConfig(config_pak_path)
		else:
			Ui.error("pak config file not found: " + config_pak_path)

	def readConfig(self, config_pak_path):
		logging.debug("reading pak config file " + config_pak_path)

		if not self.pak_config.read(config_pak_path):
			Ui.error("error reading pak config file: " + config_pak_path)

		logging.debug("config sections: " + str(self.pak_config.sections()))

		if not "config" in self.pak_config.sections():
			Ui.error("can't find config section in pak config file: " + config_pak_path)

		logging.debug("config found in pak config file: " + config_pak_path)

		self.key_dict = self.pak_config["config"]

	def requireKey(self, key_name):
		# TODO: strip quotes
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			Ui.error("key not found in pak config: " + key_name)

	def getKey(self, key_name):
		# TODO: strip quotes
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			return None

	def getBuildPrefix(self, build_prefix=None):
		if not build_prefix:
			env_build_prefix = os.getenv("BUILDPREFIX")
			if env_build_prefix:
				Ui.notice("BUILDPREFIX set, will use: " + env_build_prefix)
				build_prefix = env_build_prefix
			else:
				build_prefix = self.source_dir + os.path.sep + "build"

		return os.path.abspath(build_prefix)

	def getTestPrefix(self, build_prefix=None, test_prefix=None):
		if not test_prefix:
			env_test_prefix= os.getenv("TESTPREFIX")
			if env_test_prefix:
				Ui.notice("TESTPREFIX set, will use: " + env_test_prefix)
				test_prefix = env_test_prefix
			else:
				build_prefix = self.getBuildPrefix(build_prefix=build_prefix)
				test_prefix = build_prefix + os.path.sep + "test"

		return os.path.abspath(test_prefix)

	def getPakPrefix(self, build_prefix=None, pak_prefix=None):
		if not pak_prefix:
			env_pak_prefix = os.getenv("PAKPREFIX")
			if env_pak_prefix:
				Ui.notice("PAKPREFIX set, will use: " + env_pak_prefix)
				pak_prefix = env_pak_prefix
			else:
				build_prefix = self.getBuildPrefix(build_prefix=build_prefix)
				pak_prefix = build_prefix + os.path.sep + "pkg"

		return os.path.abspath(pak_prefix)


	def getTestDir(self, build_prefix=None, test_prefix=None, test_dir=None, pak_name=None):
		if not test_dir:
			if not test_prefix:
				test_prefix = self.getTestPrefix(build_prefix=build_prefix)
			pak_name = self.requireKey("name")
			test_dir = test_prefix + os.path.sep + pak_name + "_test" + os.path.extsep + "pk3dir"

		return os.path.abspath(test_dir)

	def getPakFile(self, build_prefix=None, pak_prefix=None, pak_file=None, pak_name=None):
		if not pak_file:
			if not pak_prefix:
				pak_prefix = self.getPakPrefix(build_prefix=build_prefix)
			pak_name = self.requireKey("name")
			pak_version = self.requireKey("version")
			pak_file = pak_prefix + os.path.sep + pak_name + "_" + pak_version + os.path.extsep + "pk3"

		return os.path.abspath(pak_file)

class FileProfile():
	def __init__(self, game_name):
		self.file_profile = importlib.import_module("profiles.files." + game_name)
		self.file_profile_file_type_dict = [variable for variable in dir(self.file_profile) if variable.startswith("file_")]
		self.file_type_dict = {}
		self.file_type_weight_dict = {}
		self.expandFileTypes()

	def inheritFileType(self, config_file_type_dict):
		if "inherit" in config_file_type_dict.keys():
			logging.debug("inherit from file type: " + config_file_type_dict["inherit"])
			inherited_file_type, weight = self.inheritFileType(getattr(self.file_profile, config_file_type_dict["inherit"]))
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
		for file_type in self.file_profile_file_type_dict:
			logging.debug("expanding file type: " + file_type)
			self.file_type_dict[file_type] = []
			self.file_type_dict[file_type], self.file_type_weight_dict[file_type] = self.inheritFileType(getattr(self.file_profile, file_type))


class Inspector():
	def __init__(self, game_name):
		if game_name:
			self.file_profile = FileProfile(game_name)
		else:
			self.file_profile = None
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

		self.action_name_dict = OrderedDict()
		for action in Action.Directory().directory:
			self.action_name_dict[action.keyword] = action.description

		# TODO read from config
		self.default_action = "keep"

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
		file_type_ordered_list = [x[0] for x in sorted(self.file_profile.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
		logging.debug("looking for file path:" + file_path)
#		logging.debug("will try file types in this order: ", str(file_type_ordered_list))

		action = self.default_action
		for file_type_name in file_type_ordered_list:
			logging.debug("trying file type:" + file_type_name)
			criteria_dict = self.file_profile.file_type_dict[file_type_name].copy()
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

		# TODO read from config
		if action == self.default_action:
			Ui.warning(file_path + ": unknown file found, will " + self.action_name_dict[action] + ".")
		else:
			Ui.print(file_path + ": " + description + " found, will " + self.action_name_dict[action] + ".")

		return action


class BlackList():
	def __init__(self, source_dir):
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
		pass

		pakignore_path = os.path.join(".pakinfo", "pakignore")
		pakignore_path = os.path.join(source_dir, pakignore_path)

		if os.path.isfile(pakignore_path):
			pakignore_file = open(pakignore_path, "r")
			line_list = [line.strip() for line in pakignore_file]
			pakignore_file.close()

			for pattern in line_list:
				self.blacklist.append(pattern)

		logging.debug("blacklist: " + str(self.blacklist))

	def filter(self, file_list):
		filtered_list = []
		for file_path in file_list:
			path_list = self.splitPath(file_path)

			logging.debug("checking file path for blacklist: " + file_path)
			blacklisted_file = False
			for path_part in path_list:
				for pattern in self.blacklist:
					logging.debug("comparing path part “" + path_part + "” with blacklist pattern: " + pattern)
					if fnmatch.fnmatch(path_part, pattern):
						logging.debug("found blacklisted file because of pattern “" + pattern +  "”: " + file_path)
						blacklisted_file = True
						break

			if not blacklisted_file:
				filtered_list.append(file_path)

		return filtered_list

	def splitPath(self, path):
		path_list = []
		while True:
			pair = os.path.split(path)
			if pair[0] == path:
				# if absolute
				path_list.insert(0, pair[0])
				break
			elif pair[1] == path:
				# if relative
				path_list.insert(0, pair[1])
				break
			else:
				path = pair[0]
				path_list.insert(0, pair[1])
		return path_list

class Tree():
	def __init__(self, source_dir):
		self.source_dir = source_dir

	def listFiles(self):
		file_list = []
		for dir_name, subdir_name_list, file_name_list in os.walk(self.source_dir):
			dir_name = os.path.relpath(dir_name, self.source_dir)

			logging.debug("dir_name: " + str(dir_name) + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

			for file_name in file_name_list:
				file_path = os.path.join(dir_name, file_name)
				file_list.append(file_path)

		blacklist = BlackList(self.source_dir)
		file_list = blacklist.filter(file_list)

		return file_list

class Git():
	def __init__(self, source_dir):
		self.source_dir = source_dir
		self.git = ["git", "-C", self.source_dir]
		self.subprocess_stdout = subprocess.DEVNULL
		self.subprocess_stderr = subprocess.DEVNULL

	def check(self):
		proc = subprocess.call(self.git + ["rev-parse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		if proc.numerator == 0:
			return True
		else:
			return False

	def getLastTag(self):
		tag = ""
		proc = subprocess.Popen(self.git + ["describe", "--abbrev=0", "--tags"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for tag in stdout:
				tag = tag.decode()
				if tag.endswith("\n"):
					tag = tag[:-1]
		return tag

	def listFiles(self):
		file_list = []
		proc = subprocess.Popen(self.git + ["ls-files"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for file_path in stdout:
				file_path = file_path.decode()
				if file_path.endswith("\n"):
					file_path = file_path[:-1]
				file_list.append(file_path)

		blacklist = BlackList(self.source_dir)
		file_list = blacklist.filter(file_list)

		return file_list

	def listFilesSinceReference(self, reference):
		file_list = []
		proc = subprocess.Popen(self.git + ["diff", "--name-only", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for file_path in stdout:
				file_path = file_path.decode()
				if file_path.endswith("\n"):
					file_path = file_path[:-1]

				full_path = os.path.join(self.source_dir, file_path)

				# if file still in history
				if os.path.isfile(file_path):
					logging.debug("file still in repository: " + file_path)
					file_list.append(file_path)
				else:
					logging.debug("file not there anymore: " + file_path)

		blacklist = BlackList(self.source_dir)
		file_list = blacklist.filter(file_list)

		return file_list
