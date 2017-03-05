#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon import Action
from Urcheon import Defaults
from Urcheon import Ui
from collections import OrderedDict
import configparser
import fnmatch
import importlib
import logging
import operator
import os
import shutil
import subprocess
import pytoml


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

			if pak_version == "@ref":
				file_repo = Git(self.source_dir)
				pak_version = file_repo.getVersion()

			pak_file = pak_prefix + os.path.sep + pak_name + "_" + pak_version + os.path.extsep + "pk3"

		return os.path.abspath(pak_file)

class FileProfile():
	def __init__(self, source_dir, profile_name):
		# not yet used:
		self.source_dir = source_dir

		# for self.inspector.inspector_name_dict
		self.inspector = Inspector(None, None)

		self.file_type_dict = {}
		self.file_type_weight_dict = {}
		self.readProfile(profile_name)
		self.expandFileTypeDict()

	def readProfile(self, profile_name, is_parent=False):
		file_profile_path = Defaults.getGameFileProfilePath(profile_name)

		if not file_profile_path:
			Ui.error("missing file profile: " + file_profile_path)

		file_profile_file = open(file_profile_path, "r")
		file_profile_dict = pytoml.load(file_profile_file)
		file_profile_file.close()
		
		if "_init_" in file_profile_dict.keys():
			logging.debug("found “_init_” section in file profile: " + file_profile_path)
			if "extend" in file_profile_dict["_init_"]:
				profile_parent_name = file_profile_dict["_init_"]["extend"]
				logging.debug("found “extend” instruction in “_init_” section: " + profile_parent_name)
				logging.debug("loading parent file profile")
				self.readProfile(profile_parent_name, is_parent=True)
			del file_profile_dict["_init_"]
		
		logging.debug("file profiles found: " + str(file_profile_dict.keys()))

		for file_type in file_profile_dict.keys():
			# if two names collide, the child win
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
		print(pytoml.dumps(self.file_type_dict))

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
	def __init__(self, source_dir, game_name, disabled_action_list=[]):
		if game_name:
			self.file_profile = FileProfile(source_dir, game_name)
			logging.debug("file type weight dict: " + str(self.file_profile.file_type_weight_dict))
			self.file_type_ordered_list = [x[0] for x in sorted(self.file_profile.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
			logging.debug("will try file types in this order: " + str(self.file_type_ordered_list))
		else:
			self.file_profile = None

		self.disabled_action_list = disabled_action_list

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
		for action in Action.list():
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
		logging.debug("looking for file path:" + file_path)

		# TODO: make a tree!
		description = "unknown file"
		action = self.default_action
		for file_type_name in self.file_type_ordered_list:
			logging.debug("trying file type: " + file_type_name)
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
				logging.debug("matched file type: " + file_type_name)
				logging.debug("matched file type action: " + file_type_action)

				if file_type_action in self.disabled_action_list:
					logging.debug("disabled action, will " + action + " instead: " + file_type_action)
				else:
					action = file_type_action

				description  = file_type_description
				break

		# TODO read from config
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
			"*.lin",
			"*.prt",
			"*.srf",
			"*~",
			".*.swp",
			".git*",
			".pakinfo",
			"build",
		]
		pass

		pakignore_name = "ignore" + os.path.extsep + "txt"
		pakignore_path = os.path.join(".pakinfo", pakignore_name)
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


class PakTrace():
	paktrace_dir = ".paktrace"

	def __init__(self, test_dir):
		self.test_dir = test_dir

	# this is a list to keep files names that are produced while building with other files
	def read(self, head):
		logging.debug("read paktrace for head: " + head)

		paktrace_path = self.getPath(head)
		body = self.readByPath(paktrace_path)

		if not body:
			body = [head]

		logging.debug("body read:" + str(body))
		return body

	def readByPath(self, file_path):
		paktrace_path = os.path.join(self.test_dir, file_path)

		logging.debug("read paktrace from path: " + paktrace_path)

		if os.path.isfile(paktrace_path):
			paktrace_file = open(paktrace_path, "r")
			body = paktrace_file.read().splitlines()
			paktrace_file.close()

			unmodified_body = []
			for member_file in body:
				member_path = os.path.join(self.test_dir, member_file)
				if os.path.isfile(member_path):
					if os.stat(member_path).st_mtime == os.stat(paktrace_path).st_mtime:
						unmodified_body.append(member_path)
			unmodifed_body = body
			return body
		else:
			return None

	def write(self, head, body):
		logging.debug("write paktrace for head: " + head)

		self.remove(head)

		paktrace_path = self.getPath(head)

		paktrace_subdir = os.path.dirname(paktrace_path)
		os.makedirs(paktrace_subdir, exist_ok=True)

		paktrace_file = open(paktrace_path, "w")
		for line in body:
			paktrace_file.write(line + "\n")
		paktrace_file.close()

		head_path = os.path.join(self.test_dir, head)

		shutil.copystat(head_path, paktrace_path)

	def remove(self, head):
		logging.debug("remove paktrace for head: " + head)

		paktrace_path = self.getPath(head)

		if os.path.isfile(paktrace_path):
			os.remove(paktrace_path)

	def getName(self, head):
		head_path = os.path.join(self.test_dir, head)
		paktrace_name = head + os.path.extsep + "txt"
		return paktrace_name
		
	def getPath(self, head):
		paktrace_name = self.getName(head)
		paktrace_dirpath = os.path.join(self.test_dir, self.paktrace_dir)
		paktrace_path = os.path.join(paktrace_dirpath, paktrace_name)
		return paktrace_path

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

	def getVersion(self):
		tag_name = self.getLastTag()
		commit_id = self.getLastCommitId()

		append = ""
		compute_append = True
		if tag_name:
			version = tag_name
			if version.startswith("v"):
				# v9.0 → 9.0
				version = version[1:]

			tag_commit = self.getCommitIdByTag(tag_name)
			if tag_commit != commit_id:
				compute_append = True

		else:
			version = "0"
			compte_append = True

		if compute_append:
			short_id = commit_id[:7]
			commit_date = self.getLastCommitDate()
			time_stamp = "0" + hex(int(commit_date))[2:]
			append = "+" + time_stamp + "~" + short_id

		version += append

		return version

	def getLastTag(self):
		tag_name = None
		proc = subprocess.Popen(self.git + ["describe", "--abbrev=0", "--tags"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for tag_name in stdout:
				tag_name = tag_name.decode()
				if tag_name.endswith("\n"):
					tag_name = tag_name[:-1]
		return tag_name
	
	def getCommitIdByTag(self, tag_name):
		commit_id = None
		proc = subprocess.Popen(self.git + ["rev-list", "-n", "1", tag_name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for commit_id in stdout:
				commit_id = commit_id.decode()
				if commit_id.endswith("\n"):
					commit_id = commit_id[:-1]
		return commit_id

	def getLastCommitId(self):
		commit_id = None
		proc = subprocess.Popen(self.git + ["rev-parse", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for commit_id in stdout:
				commit_id = commit_id.decode()
				if commit_id.endswith("\n"):
					commit_id = commit_id[:-1]
		return commit_id

	def getLastCommitDate(self):
		commit_date = None
		proc = subprocess.Popen(self.git + ["log", "-1", "--pretty=format:%ct"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		with proc.stdout as stdout:
			for commit_date in stdout:
				commit_date = commit_date.decode()
				if commit_date.endswith("\n"):
					commit_date = commit_date[:-1]
		return commit_date

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
