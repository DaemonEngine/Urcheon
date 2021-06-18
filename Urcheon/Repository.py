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
from Urcheon import Profile
from Urcheon import Ui
from collections import OrderedDict
from datetime import datetime
import fnmatch
import hashlib
import json
import logging
import operator
import os
import toml
import re
import shutil
import subprocess
import time

# FIXME: do we need OrderedDict toml constructor here?


class Config():
	def __init__(self, source_tree):
		self.source_dir = source_tree.dir
		self.profile_fs = Profile.Fs(source_tree.dir)

		self.key_dict = {}

		config_name = Default.pak_config_base + Default.pak_config_ext
		self.readConfig(config_name)

		# This is needed by Game.Game, so better set them in source_tree
		if not source_tree.game_name:
			source_tree.game_name = self.requireKey("game")

		self.game_profile = Game.Game(source_tree)

	def readConfig(self, config_name):
		config_path = self.profile_fs.getPath(config_name)

		if not config_path:
			Ui.error("pak config file not found: " + config_name)

		logging.debug("reading pak config file " + config_path)

		config_file = open(config_path, "r")
		config_dict = toml.load(config_file, _dict=OrderedDict)
		config_file.close()

		if not "config" in config_dict.keys():
			Ui.error("can't find config section in pak config file: " + config_path)

		logging.debug("config found in pak config file: " + config_path)
		self.key_dict = config_dict["config"]

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
				# HACK: FIXME: ugly quick&dirty .setinfo implementation
				if os.path.isfile(os.path.join(os.getcwd(), ".setinfo", "set.conf")):
					build_prefix = os.path.join(os.getcwd(), Default.build_prefix)
				else:
					build_prefix = self.source_dir + os.path.sep + Default.build_prefix

		return os.path.abspath(build_prefix)

	def getTestPrefix(self, build_prefix=None, test_prefix=None):
		if not test_prefix:
			env_test_prefix= os.getenv("TESTPREFIX")
			if env_test_prefix:
				Ui.notice("TESTPREFIX set, will use: " + env_test_prefix)
				test_prefix = env_test_prefix
			else:
				build_prefix = self.getBuildPrefix(build_prefix=build_prefix)
				test_prefix = build_prefix + os.path.sep + Default.test_prefix

		return os.path.abspath(test_prefix)

	def getPakPrefix(self, build_prefix=None, pak_prefix=None):
		if not pak_prefix:
			env_pak_prefix = os.getenv("PAKPREFIX")
			if env_pak_prefix:
				Ui.notice("PAKPREFIX set, will use: " + env_pak_prefix)
				pak_prefix = env_pak_prefix
			else:
				build_prefix = self.getBuildPrefix(build_prefix=build_prefix)
				pak_prefix = build_prefix + os.path.sep + Default.pak_prefix

		return os.path.abspath(pak_prefix)

	def getTestDir(self, build_prefix=None, test_prefix=None, test_dir=None, pak_name=None):
		if not test_dir:
			if not test_prefix:
				test_prefix = self.getTestPrefix(build_prefix=build_prefix)
			pak_name = self.requireKey("name")
			test_dir = test_prefix + os.path.sep + pak_name + "_test" + self.game_profile.pakdir_ext

		return os.path.abspath(test_dir)

	def getPakFile(self, build_prefix=None, pak_prefix=None, pak_file=None, pak_name=None):
		if not pak_file:
			if not pak_prefix:
				pak_prefix = self.getPakPrefix(build_prefix=build_prefix)
			pak_name = self.requireKey("name")
			pak_version = self.requireKey("version")

			if pak_version == "${ref}":
				file_repo = Git(self.source_dir, self.game_profile.pak_format)
				pak_version = file_repo.getVersion()

			pak_file = pak_prefix + os.path.sep + pak_name + "_" + pak_version + self.game_profile.pak_ext

		return os.path.abspath(pak_file)


class FileProfile():
	def __init__(self, source_tree):
		self.source_dir = source_tree.dir
		self.game_name = source_tree.game_name
		self.profile_name = source_tree.pak_name

		# because of: for self.inspector.inspector_name_dict
		self.inspector = Inspector(None, None, None)

		self.profile_fs = Profile.Fs(self.source_dir)

		self.file_type_dict = {}
		self.file_type_weight_dict = {}

		if self.profile_name:
			if not self.getProfilePath(self.profile_name):
				self.profile_name = self.game_name
		else:
			self.profile_name = self.game_name

		self.readProfile(self.profile_name)
		self.expandFileTypeDict()

	def getProfilePath(self, profile_name):
		file_profile_name = os.path.join(Default.file_profile_dir, profile_name + Default.file_profile_ext)
		return self.profile_fs.getPath(file_profile_name)

	def readProfile(self, profile_name):
		file_profile_path = self.getProfilePath(profile_name)

		if not file_profile_path:
			# that's not a typo
			Ui.error("file profile file not found: " + file_profile_path)

		file_profile_file = open(file_profile_path, "r")
		file_profile_dict = toml.load(file_profile_file, _dict=OrderedDict)
		file_profile_file.close()
		
		if "_init_" in file_profile_dict.keys():
			logging.debug("found “_init_” section in file profile: " + file_profile_path)
			if "extend" in file_profile_dict["_init_"]:
				value = file_profile_dict["_init_"]["extend"]

				if value == "${game}":
					value = self.game_name

				profile_parent_name = value
				logging.debug("found “extend” instruction in “_init_” section: " + profile_parent_name)
				logging.debug("loading parent file profile")
				self.readProfile(profile_parent_name)
			del file_profile_dict["_init_"]
		
		logging.debug("file profiles found: " + str(file_profile_dict.keys()))

		for file_type in file_profile_dict.keys():
			# if two section names collide, the child win
			self.file_type_dict[file_type] = file_profile_dict[file_type]

		for file_type in self.file_type_dict.keys():
			file_type = self.file_type_dict[file_type]
			for key in file_type.keys():
				if key in self.inspector.inspector_name_dict:
					if not isinstance(file_type[key], list):
						# value must always be a list, if there is only one string, put it in list
						file_type[key] = [ file_type[key] ]

		logging.debug("file types: " + str(self.file_type_dict))

	def printProfile(self):
		logging.debug(str(self.file_type_dict))
		print(toml.dumps(self.file_type_dict))

	def expandFileType(self, file_type_name):
		logging.debug("expanding file type: " + file_type_name)
		file_type = self.file_type_dict[file_type_name]

		if "inherit" in file_type.keys():
			inherited_type_name = file_type["inherit"]
			logging.debug("inherit from file type: " + inherited_type_name)
			expanded_file_type = self.expandFileType(inherited_type_name)
			self.file_type_weight_dict[file_type_name] = self.file_type_weight_dict[inherited_type_name] + 1
			del(file_type["inherit"])
		else:
			if not file_type_name in self.file_type_weight_dict:
				# if this file type was never processed
				self.file_type_weight_dict[file_type_name] = 0

			expanded_file_type = {}

		for keyword in expanded_file_type.keys():
			if keyword not in file_type.keys():
				# replace expanded keywords by newer if exist, keep peviously defined ones
				file_type[keyword] = expanded_file_type[keyword]

		return file_type

	def expandFileTypeDict(self):
		for file_type_name in self.file_type_dict.keys():
			self.file_type_dict[file_type_name] = self.expandFileType(file_type_name)


class Inspector():
	def __init__(self, source_tree, stage, disabled_action_list=[]):

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
			"dir_parent_name":		self.inspectDirParentName,
		}

		self.default_action_dict = {
			"prepare": "ignore",
			"build": "keep",
		}

		# FIXME: Why? (was previously testing source_dir)
		if not source_tree:
			return

		self.stage = stage

		self.disabled_action_list = disabled_action_list

		self.file_profile = FileProfile(source_tree)
		logging.debug("file type weight dict: " + str(self.file_profile.file_type_weight_dict))

		self.file_type_ordered_list = [x[0] for x in sorted(self.file_profile.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
		logging.debug("will try file types in this order: " + str(self.file_type_ordered_list))

		self.action_description_dict = OrderedDict()

		for action in Action.list():
			self.action_description_dict[action.keyword] = action.description

	def getDirFatherName(self, file_path):
		return os.path.basename(os.path.split(file_path)[0])

	def getDirGrandFatherName(self, file_path):
		return os.path.basename(os.path.split(os.path.split(file_path)[0])[0])

	def getBaseName(self, file_path):
		# do not use os.path.splitext() because of .xxx.xxx extensions
		# FIXME: broken with basenames containing dots
		return os.path.basename(file_path).split(os.path.extsep)[0]

	def inspectFileName(self, file_path, file_name):
		return os.path.basename(file_path) == file_name

	def inspectFileExt(self, file_path, file_ext):
		return file_path[-len(file_ext):] == file_ext

	def inspectFileBase(self, file_path, file_base):
		# FIXME: broken with basenames containing dots because of broken getBaseName()
		return self.getBaseName(file_path) == file_base

	def inspectFilePrefix(self, file_path, file_prefix):
		# FIXME: broken with basenames containing dots because of broken getBaseName()
		return self.getBaseName(file_path)[:len(file_prefix)] == file_prefix

	def inspectFileSuffix(self, file_path, file_suffix):
		# FIXME: broken with basenames containing dots because of broken getBaseName()
		return self.getBaseName(file_path)[-len(file_suffix):] == file_suffix

	def inspectDirAncestorName(self, file_path, dir_name):
		previous = file_path
		while file_path != "":
			previous = file_path
			file_path = os.path.split(file_path)[0]
		return previous == dir_name

	def inspectDirFatherName(self, file_path, dir_name):
		return self.getDirFatherName(file_path) == dir_name

	def inspectDirFatherExt(self, file_path, dir_ext):
		return self.inspectFileExt(self.getDirFatherName(file_path), dir_ext)

	def inspectDirGrandFatherName(self, file_path, dir_name):
		return self.getDirGrandFatherName(file_path) == dir_name

	def inspectDirGrandFatherExt(self, file_path, dir_ext):
		return self.inspectFileExt(self.getDirGrandFatherName(file_path), dir_ext)

	def inspectDirParentName(self, file_path, dir_name):
		# split the file name, do not check it
		parents, subpath = os.path.split(file_path)
		# split the last directory, check it, etc.
		parents, subpath = os.path.split(file_path)
		while parents != "":
			if subpath == dir_name:
				return True
			parents, subpath = os.path.split(parents)
		return False

	def inspect(self, file_path):
		logging.debug("looking for file path:" + file_path)

		# TODO: make a tree!
		description = "unknown file"
		action = self.default_action_dict[self.stage]
		for file_type_name in self.file_type_ordered_list:
			logging.debug("trying file type: " + file_type_name)
			criteria_dict = self.file_profile.file_type_dict[file_type_name].copy()

			if self.stage not in criteria_dict:
				file_type_action = "ignore"

			# all stages
			for stage in [ "prepare", "build" ]:
				if stage in criteria_dict:
					if stage == self.stage:
						file_type_action = criteria_dict.pop(stage)
					else:
						criteria_dict.pop(stage)

			file_type_description = criteria_dict.pop("description")

			matched_file_type = True
			for criteria in criteria_dict.keys():
				logging.debug("trying criteria: " + criteria + ", list: " + str(criteria_dict[criteria]))
				if criteria_dict[criteria] != None:
					matched_criteria_list = False
					for criteria_unit in criteria_dict[criteria]:
						logging.debug("trying criteria: " + criteria + ", value: " + criteria_unit)
						matched_criteria = self.inspector_name_dict[criteria](file_path, criteria_unit)
						logging.debug("matched criteria: " + str(matched_criteria))
						if matched_criteria:
							matched_criteria_list = True

					if not matched_criteria_list:
						matched_file_type = False
						break

			if matched_file_type:
				logging.debug("matched file type: " + file_type_name)
				logging.debug("matched file type action: " + file_type_action)

				if file_type_action in self.disabled_action_list:
					logging.debug("disabled action, will " + action + " instead: " + file_type_action)
				else:
					action = file_type_action

				description  = file_type_description
				break

		if action == "ignore":
			_print = Ui.verbose
		else:
			_print = Ui.print

		_print(file_path + ": " + description + " found, will " + self.action_description_dict[action] + ".")

		return action


class BlackList():
	def __init__(self, source_dir, pak_format):
		self.blacklist = [
			"README.md", # it's a repository thing, not a package one, use about/<something> for readme stuff to put in vfs
			"Makefile",
			"CMakeLists.txt",
			"Thumbs.db",
			"__MACOSX",
			"*.DS_Store",
			"*.autosave",
			"*.autosave.map",
			"*.bak",
			"*.lin",
			"*.prt",
			"*.srf",
			"*~",
			".*.swp",
			".git*",
			Default.pakinfo_dir,
			Default.paktrace_dir,
			Default.build_prefix,
		]
		pass

		if pak_format == "dpk":
			self.blacklist.append("DEPS")

		pakignore_name = Default.ignore_list_base + Default.ignore_list_ext
		pakignore_path = os.path.join(Default.pakinfo_dir, pakignore_name)
		pakignore_path = os.path.join(source_dir, pakignore_path)

		if os.path.isfile(pakignore_path):
			pakignore_file = open(pakignore_path, "r")
			line_list = [line.strip() for line in pakignore_file]
			pakignore_file.close()

			for pattern in line_list:
				if not pattern.startswith("#") and len(pattern) != 0:
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
	# Always path game_name when nested
	def __init__(self, source_dir, game_name=None, is_nested=False):
		self.dir = os.path.realpath(source_dir)

		self.game_name = game_name
		self.pak_name = None

		if not is_nested:
			self.pak_config = Config(self)
			self.pak_format = self.pak_config.game_profile.pak_format
			self.pak_name = self.pak_config.requireKey("name")
		else:
			# HACK: the most universal one (and it does not write DEPS)
			self.pak_format = "pk3"

			assert self.game_name != None, "game_name can't be empty when is_nested is true"

	def isValid(self):
		return os.path.isfile(os.path.join(self.dir, Default.pakinfo_dir, Default.pak_config_base + Default.pak_config_ext))

	def listFiles(self):
		file_list = []
		for dir_name, subdir_name_list, file_name_list in os.walk(self.dir):
			dir_name = os.path.relpath(dir_name, self.dir)

			logging.debug("dir_name: " + str(dir_name) + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

			for file_name in file_name_list:
				file_path = os.path.join(dir_name, file_name)
				file_list.append(file_path)

		blacklist = BlackList(self.dir, self.pak_format)
		file_list = blacklist.filter(file_list)

		return file_list


class Paktrace():
	def __init__(self, source_tree, build_dir):
		self.source_dir = os.path.realpath(source_tree.dir)
		self.build_dir = os.path.realpath(build_dir)
		self.paktrace_dir = Default.paktrace_dir

	def readTraceFile(self, paktrace_path):
		logging.debug("read paktrace from path: " + paktrace_path)

		paktrace_file = open(paktrace_path, "r")
		json_string = paktrace_file.read()
		paktrace_file.close()

		return json_string

	def readTraceDict(self, paktrace_path):
		# FIXME: cache me
		if os.path.isfile(paktrace_path):
			json_string = self.readTraceFile(paktrace_path)
			try:
				return json.loads(json_string)
			except json.decoder.JSONDecodeError:
				Ui.warning("paktrace file is not a valid JSON file: " + paktrace_path)
				os.remove(paktrace_path)
				return {}
		else:
			return {}

	def readTraceSourceDict(self, paktrace_path):
		trace_dict = self.readTraceDict(paktrace_path)
		if "input" in trace_dict.keys():
			return trace_dict["input"]
		else:
			return {}

	def readTraceSourceList(self, paktrace_path):
		return self.readTraceSourceDict(paktrace_path).keys()

	def readTraceBodyList(self, paktrace_path):
		trace_dict = self.readTraceDict(paktrace_path)
		if "output" in trace_dict.keys():
			return trace_dict["output"]
		else:
			return []

	# this is a list to keep built files names
	def readBody(self, head):
		logging.debug("read body for head: " + head)

		paktrace_path = self.getPath(head)
		body = self.readTraceBodyList(paktrace_path)

		logging.debug("body read:" + str(body))
		return body

	def getTimestampString(self, file_realpath):
		return str(os.path.getmtime(file_realpath))

	def computeSha256sumString(self, file_realpath):
		file_handler = open(file_realpath, "rb")
		file_bytes = file_handler.read()
		file_handler.close()
		return hashlib.sha256(file_bytes).hexdigest()

	def write(self, src, head, body):
		logging.debug("write paktrace for head: " + head)

		self.remove(head)

		# head is part of body
		if head not in body:
			body.append(head)

		src_realpath = os.path.join(self.source_dir, src)
		src_timestamp = self.getTimestampString(src_realpath)
		src_sha256sum = self.computeSha256sumString(src_realpath)
		src_dict = { "timestamp": src_timestamp, "sha256sum": src_sha256sum }

		json_dict = {}
		json_dict["input"] = { src: src_dict }
		json_dict["output"] = body

		json_string = json.dumps(json_dict, sort_keys=True, indent=4)

		paktrace_path = self.getPath(head)

		paktrace_subdir = os.path.dirname(paktrace_path)
		os.makedirs(paktrace_subdir, exist_ok=True)

		paktrace_file = open(paktrace_path, "w")
		paktrace_file.write(json_string + "\n")
		paktrace_file.close()

		head_path = os.path.join(self.build_dir, head)

		shutil.copystat(head_path, paktrace_path)

	def remove(self, head, old_format=False):
		logging.debug("remove paktrace for head: " + head)

		paktrace_path = self.getPath(head, old_format=old_format)

		if os.path.isfile(paktrace_path):
			os.remove(paktrace_path)

	def getName(self, head, old_format=False):
		head_path = os.path.join(self.build_dir, head)

		ext = Default.paktrace_file_ext

		if old_format:
			ext = ".txt"

		paktrace_name = head + ext
		return paktrace_name

	def getPath(self, head, old_format=False):
		if not old_format:
			self.remove(head, old_format=True)

		paktrace_name = self.getName(head, old_format=old_format)
		paktrace_dirpath = os.path.join(self.build_dir, self.paktrace_dir)
		paktrace_path = os.path.join(paktrace_dirpath, paktrace_name)

		return paktrace_path

	def listAll(self):
		paktrace_dir = Default.paktrace_dir
		paktrace_path = os.path.join(self.build_dir, paktrace_dir)

		file_list = []
		if os.path.isdir(paktrace_path):
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_path):
				for file_name in file_name_list:
					if file_name.endswith(Default.paktrace_file_ext):
						file_path = os.path.join(dir_name, file_name)
						body = self.readTraceBodyList(file_path)
						file_list += body

		return file_list
	
	def getFileDict(self):
		paktrace_dir = Default.paktrace_dir
		paktrace_path = os.path.join(self.build_dir, paktrace_dir)

		file_dict = {
			"input": {},
			"output": {},
		}

		if os.path.isdir(paktrace_path):
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_path):
				for file_name in file_name_list:
					if file_name.endswith(Default.paktrace_file_ext):
						file_path = os.path.join(dir_name, file_name)
						input_list = self.readTraceSourceList(file_path)
						output_list = self.readTraceBodyList(file_path)

						for output_path in output_list:
							for input_path in input_list:
								if input_path not in file_dict["input"].keys():
									file_dict["input"][input_path] = []

								file_dict["input"][input_path].append(output_path)

								if output_path not in file_dict["output"].keys():
									file_dict["output"][output_path] = []

								file_dict["output"][output_path].append(input_path)

		return file_dict


	def isDifferent(self, head):
		build_path = os.path.join(self.build_dir, head)

		paktrace_path : self.getPath(head)

		logging.debug("read sources for head: " + head)
		paktrace_path = self.getPath(head)
		source_dict = self.readTraceSourceDict(paktrace_path)

		if source_dict == {}:
			return True;

		for source_path in source_dict.keys():
			source_realpath = os.path.join(self.source_dir, source_path)
			if not os.path.exists( source_realpath ):
				return True;

			previous_timestamp = source_dict[source_path]["timestamp"]
			current_timestamp = self.getTimestampString(source_realpath)
			if (previous_timestamp == current_timestamp):
				# do not test for sha256sum
				continue

			previous_sha256sum = source_dict[source_path]["sha256sum"]
			current_sha256sum = self.computeSha256sumString(source_realpath)
			if (previous_sha256sum == current_sha256sum):
				times = (-1, float(previous_timestamp))
				os.utime(source_realpath, times)
				os.utime(build_path, times)
				continue
			else:
				return True

		return False


class Git():
	def __init__(self, source_dir, pak_format):
		self.source_dir = source_dir
		self.pak_format = pak_format

		self.git = ["git", "-C", str(self.source_dir)]
		self.subprocess_stdout = subprocess.DEVNULL
		self.subprocess_stderr = subprocess.DEVNULL

	# Unused
	def test(self):
		proc = subprocess.call(self.git + ["rev-parse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		return proc.numerator == 0

	def getVersion(self):
		version = self.computeVersion("HEAD")

		if self.isDirty():
			version += "-dirty"

		return version

	def computeVersion(self, reference):
		commit = self.getCommit(reference)

		straight = False
		version = "0"

		if commit == None:
			commit_date = int(time.strftime("%s", time.gmtime()))
			short_id = '0000000'
		else:
			for reference in self.getCommitList(commit):
				tag = self.getVersionTag(reference)

				if tag:
					# v1.0 → 1.0
					version = tag[1:]

					if reference == commit:
						straight = True

					break

			if not straight:
				commit_date = self.getDate(commit)
				short_id = self.getShortId(commit)

		if not straight:
			time_stamp = self.getCompactHumanTimeStamp(commit_date)
			version += "-" + time_stamp + "-" + short_id

		return version

	def isDirty(self):
		proc = subprocess.call(self.git + ["diff", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

		modified = proc.numerator != 0

		proc = subprocess.Popen(self.git + ["ls-files", "--others", "--exclude-standard"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		file_list = stdout.decode().splitlines()

		added = len(file_list) > 0

		return modified or added


	def getHexTimeStamp(self, commit_date):
		# not used
		time_stamp = "0" + hex(int(commit_date))[2:]
		return time_stamp

	def getCompactHumanTimeStamp(self, commit_date):
		time_stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(int(commit_date)))
		return time_stamp
		
	def getCommitList(self, reference):
		# more recent first
		# repository without commit displays an error on stderr we silent
		proc = subprocess.Popen(self.git + ["rev-list", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		commit_list = stdout.decode().splitlines()

		if len(commit_list) > 0:
			return commit_list
		else:
			return []
	
	def getCommit(self, reference):
		# repository without commit displays an error on stderr we silent
		proc = subprocess.Popen(self.git + ["rev-list", "-n", "1", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		commit_list = stdout.decode().splitlines()

		if len(commit_list) > 0:
			return commit_list[0]
		else:
			return None

	def getVersionTag(self, reference):
		# greater first
		proc = subprocess.Popen(self.git + ["tag", "--points-at", reference, "--sort=-version:refname", "v*"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		tag_list = stdout.decode().splitlines()

		if len(tag_list) > 0:
			return tag_list[0]
		else:
			return None
	
	def getShortId(self, reference):
		return self.getCommit(reference)[:7]

	def getDate(self, reference):
		proc = subprocess.Popen(self.git + ["log", "-1", "--pretty=format:%ct", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()
		return stdout.decode().splitlines()[0]

	def listFiles(self):
		proc = subprocess.Popen(self.git + ["ls-files"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()
		file_list = stdout.decode().splitlines()

		blacklist = BlackList(self.source_dir, self.pak_format)
		file_list = blacklist.filter(file_list)

		return file_list

	def listUntrackedFiles(self):
		proc = subprocess.Popen(self.git + ["ls-files", "--others", "--exclude-standard"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()
		file_list = stdout.decode().splitlines()

		blacklist = BlackList(self.source_dir, self.pak_format)
		file_list = blacklist.filter(file_list)

		return file_list

	def listFilesSinceReference(self, reference):
		file_list = []
		proc = subprocess.Popen(self.git + ["diff", "--name-only", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()
		repo_file_list = stdout.decode().splitlines()

		for file_path in repo_file_list:
			full_path = os.path.join(self.source_dir, file_path)

			# if file still in history
			if os.path.isfile(full_path):
				logging.debug("file still in repository: " + file_path)
				file_list.append(file_path)
			else:
				logging.debug("file not there anymore: " + file_path)

		blacklist = BlackList(self.source_dir, self.pak_format)
		file_list = blacklist.filter(file_list)

		return file_list


class Deps():
	def __init__(self):
		self.deps_dict = OrderedDict()

	def read(self, pakdir_path):
		deps_file_path = os.path.join(pakdir_path, "DEPS")

		if not os.path.isfile(deps_file_path):
			return False

		deps_file = open(deps_file_path, "r")
		line_list = [line.strip() for line in deps_file]
		deps_file.close()

		empty_line_pattern = re.compile(r"^[ \t]*$")
		basic_deps_line_pattern = re.compile(r"^[ \t]*(?P<pak_name>[^ \t]*)[ \t]*$")
		version_deps_line_pattern = re.compile(r"^[ \t]*(?P<pak_name>[^ \t]*)[ \t]*(?P<pak_version>.*)$")

		for line in line_list:
			line_match = empty_line_pattern.match(line)
			if line_match:
				continue

			line_match = basic_deps_line_pattern.match(line)
			if line_match:
				pak_name = line_match.group("pak_name")
				pak_version = None
				self.set(pak_name, pak_version)
				continue

			line_match = version_deps_line_pattern.match(line)
			if line_match:
				pak_name = line_match.group("pak_name")
				pak_version = line_match.group("pak_version")
				self.set(pak_name, pak_version)
				continue

			Ui.error("malformed line in DEPS file: " + line)

		return True

	def translateTest(self, pakpath):
		Ui.laconic("translating DEPS for testing")
		for pak_name in self.deps_dict.keys():
			pak_version = self.get(pak_name)

			if pak_version == "src":
				pak_version = "test"

			self.set(pak_name, pak_version)

	def translateRelease(self, pakpath):
		Ui.laconic("translating DEPS for release")
		for pak_name in self.deps_dict.keys():
			pak_version = self.get(pak_name)

			if pak_version == "test":
				pak_version = pakpath.getPakDirVersion(pak_name)

			self.set(pak_name, pak_version)

	def write(self, pakdir_path):
		deps_file_path = os.path.join(pakdir_path, "DEPS")
		deps_file = open(deps_file_path, "w")
		deps_file.write(self.produce())
		return deps_file_path

	def get(self, pak_name):
		if pak_name not in self.deps_dict.keys():
			return None

		return self.deps_dict[pak_name]

	def set(self, pak_name, pak_version):
		if pak_version != None:
			empty_version_pattern = re.compile(r"^[ \t]*$")
			if empty_version_pattern.match(pak_version):
				pak_version = None

		self.deps_dict[pak_name] = pak_version

	def produce(self):
		string = ""
		for pak_name in self.deps_dict.keys():
			pak_version = self.get(pak_name)

			if pak_version == None:
				string += pak_name
			else:
				string += pak_name + " " + pak_version

			string += "\n"

		return string

	def print(self):
		print(self.produce())

	def remove(self, pakdir_path):
		deps_file_path = os.path.join(pakdir_path, "DEPS")
		if os.path.isfile(deps_file_path):
			os.remove(deps_file_path)


class PakVfs:
	def __init__(self):
		self.pakpath_list = []
		pakdir_ext = ".dpkdir"

		# ugly quick&dirty .setinfo implementation
		# TODO: please fix
		if os.path.isfile(os.path.join(os.getcwd(), ".setinfo", "set.conf")):
			pakpath = os.path.join(os.getcwd(), Default.source_prefix)
			self.pakpath_list.append(pakpath)

		pakpath_env = os.getenv("PAKPATH")
		if pakpath_env:
			self.pakpath_list.extend(pakpath_env.split(":"))

			while "" in self.pakpath_list:
				self.pakpath_list.remove("")

			Ui.notice("PAKPATH set, will use: " + ":".join(self.pakpath_list))

		self.pakdir_dict = {}
		for pakpath in self.pakpath_list:
			for dir_name in os.listdir(pakpath):
				full_path = os.path.abspath(os.path.join(pakpath, dir_name))
				if os.path.isdir(full_path):
					if dir_name.endswith(pakdir_ext):
						# FIXME: Handle properly multiple pakdir with same name
						# in multiple pakpaths
						if dir_name not in self.pakdir_dict:
							pak_name = dir_name.split('_')[0]
							pak_version = dir_name.split('_')[1][:-len(pakdir_ext)]

							logging.debug("found version for pakdir “" + dir_name + "”: " + pak_version)

							self.pakdir_dict[pak_name] = {}
							self.pakdir_dict[pak_name]["full_path"] = full_path
							self.pakdir_dict[pak_name]["version"] = pak_version

	def listPakPath(self):
		return self.pakpath_list

	def listPakDir(self):
		return self.pakdir_dict

	def getPakDirVersion(self, pak_name):
		if pak_name not in self.pakdir_dict:
			Ui.warning("missing pakdir, can't enforce version: " + pak_name)
			return None

		pak_version = self.pakdir_dict[pak_name]["version"]

		if pak_version == "src":
			full_path = self.pakdir_dict[pak_name]["full_path"]
			print("hoho")
			startTime = time.time()
			git = Git(full_path, "dpk")
			print(str(time.time() - startTime))
			startTime = time.time()
			pak_version = git.getVersion()
			print(str(time.time() - startTime))

		logging.debug("found version for pak “" + pak_name + "”: " + pak_version)

		return pak_version
