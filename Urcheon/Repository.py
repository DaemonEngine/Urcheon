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

dpk_special_files = [
	"DELETED",
	"DEPS",
]

class Config():
	def __init__(self, source_tree):
		self.source_dir = source_tree.dir
		self.base_name = source_tree.base_name
		self.profile_fs = Profile.Fs(source_tree.dir)

		self.known_key_name_list = [ "type", "game", "name", "version" ]
		self.known_pak_name_list = [ "dpk", "pk3", "pk4" ]
		self.key_dict = {}

		for key_name in self.known_key_name_list:
			self.key_dict[key_name] = None

		self.readLegacyConfig()
		self.readConfig()
		self.guessConfig()

		# Override game name from command line.
		if source_tree.game_name:
			game_name = self.getKey("game")
			if game_name:
				Ui.warning("Overriding “game” config key “" + game_name + "” with: " + source_tree.game_name )
			self.setKey("game", source_tree.game_name)

		# This is needed by Game.Game, so better set it in source_tree directly.
		# Do not exit on error to display an help message.
		source_tree.game_name = self.requireKey("game", silent=True, exit=False)

		if not source_tree.game_name:
			Ui.help("You can use the --game argument to set a game without writing any configuration", exit=True)

		self.game_profile = Game.Game(source_tree)

	def getKeyNameListWithout(self, ignored_key_name):
		return [key_name for key_name in self.known_key_name_list if key_name != ignored_key_name]

	def guessConfig(self):
		pak_type = None
		pak_name = None
		pak_version = None

		for type_name in self.known_pak_name_list:
			pakdir_ext = "." + type_name + "dir"

			if not self.base_name.endswith(pakdir_ext):
				continue

			pak_type = type_name

			base_name = self.base_name[:-len(pakdir_ext)]

			if pak_type == "dpk":
				if "_" in base_name:
					pak_name = base_name.split("_")[0]
					pak_version = base_name.split("_")[1]

				if pak_version == "src":
					pak_version = "${ref}"

			else:
				pak_name = base_name

			break

		guessed_config_dict = {
			"type": pak_type,
			"name": pak_name,
			"version": pak_version,
		}

		for key_name in self.getKeyNameListWithout("game"):
			if not self.getKey(key_name):
				value = guessed_config_dict[key_name]

				if not value:
					Ui.error("Cannot guess “" + key_name + "” config key for :" + self.source_dir)

				logging.debug("Guessed “" + key_name + "” config key with:" + value)
				self.setKey(key_name, value)

	def readKeyFile(self, config_file_path):
		config_file = open(config_file_path, "r")
		# TODO: Add a warning if more than one line.
		value = config_file.readline().strip()
		config_file.close()
		return value

	def readConfig(self):
		for key_name in self.known_key_name_list:
			config_file_name = key_name + ".txt"
			config_file_path = self.profile_fs.getPath(config_file_name)

			if config_file_path:
				value = self.readKeyFile(config_file_path)

				if value:
					if self.getKey(key_name):
						Ui.warning("Duplicated config key: " + key_name)
					else:
						logging.debug("Found config key “" + key_name + "” with: " + value)
						self.setKey(key_name, value)

	def readLegacyConfig(self):
		config_file_name = "pak.conf"

		config_file_path = self.profile_fs.getPath(config_file_name)

		if not config_file_path:
			logging.debug("Legacy pak config file not found: " + config_file_name)
			return

		logging.debug("reading pak config file " + config_file_path)

		# FIXME: Catch error.
		config_file = open(config_file_path, "r")
		config_dict = toml.load(config_file, _dict=OrderedDict)
		config_file.close()

		if not "config" in config_dict.keys():
			logging.debug("can't find config section in pak config file: " + config_file_path)
			return

		logging.debug("config found in pak config file: " + config_file_path)

		for key_name in config_dict["config"].keys():
			value = config_dict["config"][key_name]
			logging.debug("Found legacy config key “" + key_name + "” with value: " + value)
			self.setKey(key_name, value)

	def requireKey(self, key_name, silent=False, exit=True):
		value = self.getKey(key_name)

		if not value:
			Ui.error("key not found in pak config: " + key_name, silent=silent, exit=exit)

		return value

	def getKey(self, key_name):
		return self.key_dict[key_name]

	def setKey(self, key_name, value):
		self.key_dict[key_name] = value

	def getBuildPrefix(self, args):
		if args and args.build_prefix:
			build_prefix = args.build_prefix
		else:
			env_build_prefix = os.getenv("URCHEON_BUILD_PREFIX")

			if env_build_prefix:
				Ui.notice("URCHEON_BUILD_PREFIX set, will use: " + env_build_prefix)
				build_prefix = env_build_prefix

			else:
				build_parent_dir = None

				source_real_path = os.path.realpath(self.source_dir)
				parent_dir = os.path.dirname(source_real_path)

				if os.path.basename(parent_dir) == "src":
					self.errorLegacyLayout()

				if os.path.basename(parent_dir) == Default.base_dir:
					grand_parent_dir = os.path.dirname(parent_dir)

					set_build_prefix = os.path.join(grand_parent_dir, Default.build_prefix)
					pak_build_prefix = os.path.join(self.source_dir, Default.build_prefix)

					config_dir = Default.getCollectionConfigDir(grand_parent_dir)

					config_file_path = os.path.join(grand_parent_dir, config_dir, "collection.txt")
					legacy_config_file_path = os.path.join(grand_parent_dir, config_dir, "set.conf")

					if os.path.isfile(config_file_path):
						logging.debug("Found collection config file: " + config_file_path)
						build_parent_dir = grand_parent_dir

					elif os.path.isfile(legacy_config_file_path):
						logging.debug("Found legacy config file: " + legacy_config_file_path)
						build_parent_dir = grand_parent_dir

				if build_parent_dir:
					logging.debug("Found package collection directory “" + build_parent_dir + "” for: " + self.source_dir )
				else:
					logging.debug("Found lone package directory: " + self.source_dir )
					build_parent_dir = self.source_dir

				build_prefix = os.path.join(build_parent_dir, Default.build_prefix)

		return os.path.abspath(build_prefix)

	def getPackagePrefix(self, args):
		if args and args.package_prefix:
			package_prefix = args.package_prefix
		else:
			if args and args.build_prefix:
				package_prefix = args.build_prefix
			else:
				env_package_prefix = os.getenv("URCHEON_PACKAGE_PREFIX")

				if env_package_prefix:
					Ui.notice("URCHEON_PACKAGE_PREFIX set, will use: " + env_package_prefix)
					package_prefix = env_package_prefix
				else:
					env_build_prefix = os.getenv("URCHEON_BUILD_PREFIX")

					if env_build_prefix:
						Ui.notice("URCHEON_BUILD_PREFIX set, will use as package prefix: " + env_build_prefix)
						package_prefix = env_build_prefix
					else:
						package_parent_dir = None

						source_real_path = os.path.realpath(self.source_dir)
						parent_dir = os.path.dirname(source_real_path)

						if os.path.basename(parent_dir) == "src":
							self.errorLegacyLayout()

						if os.path.basename(parent_dir) == Default.base_dir:
							grand_parent_dir = os.path.dirname(parent_dir)

							set_package_prefix = os.path.join(grand_parent_dir, Default.package_prefix)
							pak_package_prefix = os.path.join(self.source_dir, Default.package_prefix)

							config_dir = Default.getCollectionConfigDir(grand_parent_dir)

							config_file_path = os.path.join(grand_parent_dir, config_dir, "collection.txt")
							legacy_config_file_path = os.path.join(grand_parent_dir, config_dir, "set.conf")

							if os.path.isfile(config_file_path):
								logging.debug("Found collection config file: " + config_file_path)
								package_parent_dir = grand_parent_dir

							elif os.path.isfile(legacy_config_file_path):
								logging.debug("Found legacy config file: " + legacy_config_file_path)
								package_parent_dir = grand_parent_dir

						if package_parent_dir:
							logging.debug("Found package collection directory “" + package_parent_dir + "” for: " + self.source_dir )
						else:
							logging.debug("Found lone package directory: " + self.source_dir )
							package_parent_dir = self.source_dir

						package_prefix = os.path.join(package_parent_dir, Default.package_prefix)

		return os.path.abspath(package_prefix)

	def getBuildRootPrefix(self, args):
		if args and args.build_root_prefix:
			build_root_prefix = args.build_root_prefix
		else:
			env_build_root_prefix= os.getenv("URCHEON_BUILD_ROOT_PREFIX")
			if env_build_root_prefix:
				Ui.notice("URCHEON_BUILD_ROOT_PREFIX set, will use: " + env_build_root_prefix)
				build_root_prefix = env_build_root_prefix
			else:
				build_prefix = self.getBuildPrefix(args)

				if os.path.exists(os.path.join(build_prefix, "test")):
					self.errorLegacyLayout()

				build_root_prefix = os.path.join(build_prefix, Default.build_parent_dir)

		return os.path.abspath(build_root_prefix)

	def getPackageRootPrefix(self, args):
		if args and args.package_root_prefix:
			package_root_prefix = args.package_root_prefix
		else:
			env_package_root_prefix= os.getenv("URCHEON_PACKAGE_ROOT_PREFIX")
			if env_package_root_prefix:
				Ui.notice("URCHEON_PACKAGE_ROOT_PREFIX set, will use: " + env_package_root_prefix)
				package_root_prefix = env_package_root_prefix
			else:
				package_prefix = self.getPackagePrefix(args)

				if os.path.exists(os.path.join(package_prefix, "test")):
					self.errorLegacyLayout()

				package_root_prefix = os.path.join(package_prefix, Default.package_parent_dir).rstrip("/")

		return os.path.abspath(package_root_prefix)

	def getBuildBasePrefix(self, args):
		if args and args.build_base_prefix:
			build_base_prefix = args.build_base_prefix
		else:
			build_root_prefix = self.getBuildRootPrefix(args)

			build_base_prefix = os.path.join(build_root_prefix, Default.base_dir)

		return os.path.abspath(build_base_prefix)

	def getPackageBasePrefix(self, args):
		if args and args.package_base_prefix:
			package_base_prefix = args.package_base_prefix
		else:
			package_root_prefix = self.getPackageRootPrefix(args)

			package_base_prefix = os.path.join(package_root_prefix, Default.base_dir)

		return os.path.abspath(package_base_prefix)

	def getTestDir(self, args):
		if args and args.test_dir:
			test_dir = args.test_dir
		else:
			if args and args.build_base_prefix:
				build_base_prefix = args.build_base_prefix
			else:
				build_base_prefix = self.getBuildBasePrefix(args)

			if args and args.pak_name:
				pak_name = args.pak_name
			else:
				pak_name = self.requireKey("name")

			pak_type = self.requireKey("type")

			if pak_type == "dpk":
				test_dir_name = pak_name + "_test" + self.game_profile.pakdir_ext
			else:
				test_dir_name = pak_name + self.game_profile.pakdir_ext

			test_dir = os.path.join(build_base_prefix, test_dir_name)

		return os.path.abspath(test_dir)

	def getPakFile(self, args):
		if args and args.pak_file:
			pak_file = args.pak_file
		else:
			if args and args.package_base_prefix:
				package_base_prefix = args.package_base_prefix
			else:
				package_base_prefix = self.getPackageBasePrefix(args)

			if args and args.pak_name:
				pak_name = args.pak_name
			else:
				pak_name = self.requireKey("name")

			pak_type = self.requireKey("type")

			if pak_type == "dpk":
				pak_version = self.requireKey("version")

				if args and args.version_suffix:
					version_suffix = args.version_suffix

				if pak_version == "${ref}":
					file_repo = Git(self.source_dir, self.game_profile.pak_format)
					pak_version = file_repo.getVersion(version_suffix=args.version_suffix)
				elif version_suffix:
					pak_version += args.version_suffix

				pak_file_name = pak_name + "_" + pak_version + self.game_profile.pak_ext

			else:
				pak_file_name = pak_name + self.game_profile.pak_ext

			pakprefix = ""

			if args and args.pakprefix:
				pakprefix = args.pakprefix
			else:
				env_pakprefix = os.getenv("URCHEON_PAKPREFIX")

				if env_pakprefix:
					Ui.notice("URCHEON_PAKPREFIX set, will use: " + env_pakprefix)
					pakprefix = env_pakprefix

			pak_file = os.path.join(package_base_prefix, pakprefix, pak_file_name)

		return os.path.abspath(pak_file)

	def errorLegacyLayout(self):
		Ui.error("Unsupported legacy layout", silent=True)


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

		# Needed to detect symbolic links.
		self.source_dir = source_tree.dir

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

	def inspect(self, file_path, deletion=False):
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

		action_description = self.action_description_dict[action]

		full_path = os.path.join(self.source_dir, file_path)

		# TODO: Maybe some filesystem doesn't support symbolic link
		# and we would have to use another solution.
		# TODO: Check if symbolic link is not outside of repository
		# and if symbolic link is relative because only relative symbolic
		# link is supported, usually with limited depth only.
		# Even if we can solve absolute link to the same package and turn
		# it into a relative link, no one should commit such link anyway.
		if os.path.islink(full_path):
			_print(file_path + ": " + description + " symbolic link found, will not " + action_description + " but link to source target.")
		else:
			if deletion:
				if file_path.startswith(Default.repository_config_dir + os.path.sep):
					pass
				elif file_path.startswith(Default.legacy_pakinfo_dir + os.path.sep):
					pass
				else:
					_print(file_path + ": deleted.")
			else:
				_print(file_path + ": " + description + " found, will " + action_description + ".")

		return action


class BlackList():
	def __init__(self, source_dir, pak_format):
		dust_blacklist = [
			"Thumbs.db",
			"__MACOSX",
			"*.DS_Store",
			"*~",
			".*.swp",
		]

		build_blacklist = [
			"Makefile",
			"CMakeLists.txt",
		]

		q3map2_blacklist = [
			"*.autosave",
			"*.autosave.map",
			"*.bak",
			"*.lin",
			"*.prt",
			"*.srf",
		]

		git_blacklist = [
			".git*",
		]

		urcheon_blacklist = [
			Default.legacy_pakinfo_dir,
			Default.repository_config_dir,
			Default.legacy_paktrace_dir,
			Default.cache_dir,
			Default.build_prefix,
		]

		blacklist_list = [
			dust_blacklist,
			build_blacklist,
			q3map2_blacklist,
			git_blacklist,
			urcheon_blacklist
		]

		self.blacklist = []

		for blacklist in blacklist_list:
			self.blacklist.extend(blacklist)

		if pak_format == "dpk":
			self.blacklist.extend(dpk_special_files)

		pakignore_name = Default.ignore_list_file

		config_dir = Default.getPakConfigDir(source_dir)

		pakignore_path = os.path.join(config_dir, pakignore_name)

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
	# Always pass game_name when nested
	def __init__(self, source_dir, game_name=None, is_nested=False):
		self.dir = os.path.realpath(source_dir)
		# FIXME: even if using source_dir, a symlink would contain the real path.
		# We still need to use the real path when building the current directory with ”.”.
		self.base_name = os.path.basename(self.dir)

		self.game_name = game_name
		self.pak_name = None

		self.pak_vfs = PakVfs(source_dir)

		if not is_nested:
			self.pak_config = Config(self)
			self.pak_format = self.pak_config.game_profile.pak_format
			self.pak_name = self.pak_config.requireKey("name")
		else:
			# HACK: the most universal one (and it does not write DEPS)
			self.pak_format = "pk3"

			assert self.game_name != None, "game_name can't be empty when is_nested is true"

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

		source_full_path = os.path.join(self.source_dir, src)
		source_real_path = os.path.realpath(source_full_path)

		source_timestamp = self.getTimestampString(source_real_path)
		source_sha256sum = self.computeSha256sumString(source_real_path)

		# TODO: Make sure files are in the same pakdir else error out.
		source_real_dir = os.path.realpath(self.source_dir)
		source_relpath = os.path.relpath(source_real_path, start=source_real_dir)

		source_dict = {
			"relpath": source_relpath,
			"timestamp": source_timestamp,
			"sha256sum": source_sha256sum
		}

		json_dict = {}
		json_dict["input"] = { src: source_dict }
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

		paktrace_dir = Default.getPakTraceDir(self.build_dir)
		paktrace_name = self.getName(head, old_format=old_format)

		paktrace_path = os.path.join(paktrace_dir, paktrace_name)

		return paktrace_path

	def listAll(self):
		paktrace_dir = Default.getPakTraceDir(self.build_dir)

		file_list = []
		if os.path.isdir(paktrace_dir):
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_dir):
				for file_name in file_name_list:
					if file_name.endswith(Default.paktrace_file_ext):
						file_path = os.path.join(dir_name, file_name)
						body = self.readTraceBodyList(file_path)
						file_list += body

		return file_list

	def getFileDict(self):
		paktrace_dir = Default.getPakTraceDir(self.build_dir)

		file_dict = {
			"input": {},
			"output": {},
		}

		if os.path.isdir(paktrace_dir):
			for dir_name, subdir_name_list, file_name_list in os.walk(paktrace_dir):
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
			source_full_path = os.path.join(self.source_dir, source_path)
			if not os.path.exists( source_full_path ):
				return True;

			# TODO: Make sure files are in the same pakdir else error out.
			source_real_dir = os.path.realpath(self.source_dir)
			current_relpath = os.path.relpath(source_full_path, start=source_real_dir)

			# Older versions of Urcheon were not writing the relpath key,
			# ignore if it is not there.
			if "relpath" in source_dict[source_path].keys():
				previous_relpath = source_dict[source_path]["relpath"]
				if previous_relpath != current_relpath:
					return True

			previous_timestamp = source_dict[source_path]["timestamp"]
			current_timestamp = self.getTimestampString(source_full_path)
			if (previous_timestamp == current_timestamp):
				# do not test for sha256sum
				continue

			previous_sha256sum = source_dict[source_path]["sha256sum"]
			current_sha256sum = self.computeSha256sumString(source_full_path)
			if (previous_sha256sum == current_sha256sum):
				times = (-1, float(previous_timestamp))
				os.utime(source_full_path, times)
				os.utime(build_path, times)
				continue
			else:
				return True

		return False


class Git():
	def __init__(self, source_dir, pak_format, workaround_no_delete=False):
		self.source_dir = source_dir
		self.pak_format = pak_format
		self.workaround_no_delete = workaround_no_delete

		self.git = ["git", "-C", str(self.source_dir)]
		self.subprocess_stdout = subprocess.DEVNULL
		self.subprocess_stderr = subprocess.DEVNULL

		self.version_tag_pattern = re.compile(r"^v[0-9].*")

		# TODO: add a command-line option
		env_timestamp_hex = os.getenv("URCHEON_TIMESTAMP_HEX")
		if env_timestamp_hex:
			self.timestamp_function = self.getHexTimeStamp
		else:
			self.timestamp_function = self.getCompactHumanTimeStamp

	def isGit(self):
		proc = subprocess.call(self.git + ["rev-parse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		return proc.numerator == 0

	def getVersion(self, version_suffix=None):
		version = self.computeVersion("HEAD")

		if version_suffix:
			version += version_suffix

		if self.isDirty():
			version += "+dirty"

		return version

	def isVersionTag(self, reference):
		return self.version_tag_pattern.match(reference)

	def computeVersion(self, since_reference, named_reference=False):
		reference_id = self.getCommit(since_reference)

		is_tag = self.isVersionTag(since_reference)
		is_straight = False
		is_empty = False
		version = "0"

		if reference_id == None:
			commit_date = int(time.strftime("%s", time.gmtime()))
			short_id = '0'
		else:
			for commit in self.getCommitList(reference_id):
				tag_name = self.getVersionTag(commit)
				logging.debug("commit name: " + commit + ", tag name: " + str(tag_name))

				# Skip commits without version tag when reference is
				# a version tag producing an empty pak.
				if named_reference and is_empty:
					if is_tag and not tag_name:
						# Look for next commit having a version tag.
						continue

					# If diff with previous reference produced empty pak,
					# restart computeVersion on this reference instead.
					return self.computeVersion(commit)

				if tag_name:
					# v1.0 → 1.0
					version = tag_name[1:]

					if commit == reference_id:
						is_straight = True

					break

				# We should skip commit with unmodified files
				# only if the reference is not a version tag,
				# otherwise doing:
				#   urcheon build -r unvanquished/0.52.0 src/unvanquished_src.dpkdir
				#   urcheon package src/unvanquished_src.dpkdir
				# would produce a DEPS file with this line:
				#   unvanquished 0.51.1-20210506-112416-ea9badd
				# instead of this line:
				#  unvanquished 0.52.0
				# because the commit tagged unvanquished/0.52.0
				# is a merge commit and then doesn't have any
				# change.

				# We assume a version tag always had been previously
				# built, even if that meant to rebuild the package
				# entirely.

				# If the commit does not modify files and a partial
				# build would produce an empty pak and then the pak
				# will not be written, look for older version tags
				# so building a partial build with such reference
				# will not depend on a non-existing pak.
				if named_reference and not self.hasModification(reference_id):
					# Attempt to computeVersion on next reference.
					logging.debug("commit " + commit + " has no modification")
					is_empty = True
					continue

			if not is_straight:
				commit_date = self.getDate(reference_id)
				short_id = self.getShortId(reference_id)

		if not is_straight:
			time_stamp = self.timestamp_function(commit_date)
			version += "-" + time_stamp + "-" + short_id

		return version

	def hasModification(self, reference):
		# Never call it on git tag, only on git commit id, because the output of
		# the git call would print some tag related info and then the test will
		# always be true and then produce a false positive.

		# Unvanquished game did not supported DELETED file until after to 0.52.1.
		if (self.pak_format == "dpk" and not self.workaround_no_delete):
			# Test for ACMD: Added, Copied, Modified, Deleted
			# Do not test for RTUX: Renamed, Changed (file Type), Unmerged, Unknown
			# Disable renaming detection, original path of renamed file is listed
			# as deleted.
			proc = subprocess.Popen(self.git + ["show", "--diff-filter=ACMD", "--no-renames", "--pretty=format:", "--name-only", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

		else:
			# Test for ACMR: Added, Copied, Modified, Renamed
			# Do not test for DTUX: Deleted, Changed (file Type), Unmerged, Unknown
			proc = subprocess.Popen(self.git + ["show", "--diff-filter=ACMR", "--pretty=format:", "--name-only", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

		stdout, stderr = proc.communicate()

		file_list = stdout.decode().splitlines()
		logging.debug("modified file list: " + str(file_list))

		return len(file_list) != 0

	def isDirty(self):
		proc = subprocess.call(self.git + ["diff", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

		# modified file
		if proc.numerator != 0:
			# Ignore modified file outside the dpkdir (when the dpkdir is a subfolder of a repository)

			# TODO: Add an option to force those files to marke the package as dirty.
			# Some files may be contributed to the final package with --merge-directory
			# like binaries built from sources files from the same repository.

			proc = subprocess.Popen(self.git + ["rev-parse", "--show-toplevel"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
			stdout, stderr = proc.communicate()

			if proc.returncode != 0:
				Ui.error("Something bad happened with pakdir " + self.source_dir, silent=True)

			toplevel_path = stdout.decode().splitlines()[0]

			proc = subprocess.Popen(self.git + ["diff", "-z", "--name-only"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
			stdout, stderr = proc.communicate()

			file_list = [x for x in stdout.decode().split('\0')[:-1]]

			source_dir_fullpath = os.path.realpath(self.source_dir)
			for file_path in file_list:
				full_path = os.path.realpath(os.path.join(toplevel_path, file_path))
				if not os.path.relpath(source_dir_fullpath, full_path).startswith(".."):
					return True

			# TODO: Add an option for ignoring changes in submodules of the dpkdir.
			# The chance someone does that is very little anyway.
			# We may want this if we want files modified outside of dpkdir to
			# make the package dirty if binary merged to the packages are built
			# from the same repository but outside the dpkdir.

		proc = subprocess.Popen(self.git + ["ls-files", "-z", "--others", "--exclude-standard"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		file_list = stdout.decode().split('\0')[:-1]

		# added file
		return len(file_list) > 0

	def getDeletedFileList(self, reference):
		proc = subprocess.Popen(self.git + ["diff", "--diff-filter=D", "--no-renames", "--pretty=format:", "--name-only", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		file_list = stdout.decode().splitlines()

		return file_list

	def getHexTimeStamp(self, commit_date):
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
		# smaller first
		proc = subprocess.Popen(self.git + ["tag", "--points-at", reference, "--sort=version:refname", "v[0-9]*"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()

		tag_list = stdout.decode().splitlines()

		if len(tag_list) > 0:
			# If there are more than one tag we should use
			# the more recent one by default.

			# For example doing:
			#  urcheon build src/map-parpax_src.dpkdir
			#  urcheon package src/map-parpax_src.dpkdir
			# at unvanquished/0.53.1 time would produce:
			#  map-parpax_2.7.2.dpk
			# and not
			#  map-parpax_2.7.1.dpk
			# despite the v2.7.2 version just being a
			# rebuild with newer daemonmap tool and then
			# the v2.7.1 tag and the v2.7.2 tag are set on
			# the same commit and then there is no change
			# in source repository between them.

			# Historians wanting to rebuild v2.7.1 package
			# with tools used at v2.7.1 time after v2.7.2
			# is tagged would have to rename the package
			# themselves.

			# One cannot really make an option to use
			# the first tag instead because it may even
			# happens that v2.7.3 would be a new repackage
			# without navmeshes even if source did not
			# change and then no one can decide what tag to
			# use among v2.7.1, v2.7.2 and v2.7.3.
			# In such situation where a v2.7.3 tag is added
			# to the same commit and if an historian wants
			# to rebuild v2.7.2 only him would know the
			# version string he wants. The tool cannot
			# know which tag to use: the oldest one,
			# the most recent one, or which one in between.

			# The greatest one is the most recent one
			# because those are version numbers.
			greatest_tag = tag_list[-1]

			if len(tag_list) > 1:
				Ui.warning("more than one version tag for reference " + reference + ": " + ", ".join(tag_list) + ", using " + greatest_tag)

			return greatest_tag
		else:
			return None

	def getShortId(self, reference):
		return self.getCommit(reference)[:7]

	def getDate(self, reference):
		proc = subprocess.Popen(self.git + ["log", "-1", "--pretty=format:%ct", reference], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		stdout, stderr = proc.communicate()
		lines = stdout.decode().splitlines()
		if len(lines) == 0:
			return 0
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

class Deleted():
	def __init__(self, source_tree, test_dir, stage_name):
		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.test_dir = test_dir
		self.stage_name = stage_name
		self.deleted_file_list = []
		self.deleted_part_list = []

	def get_source_path(self):
		deleted_file_path = os.path.join(self.source_dir, "DELETED")
		return deleted_file_path

	def get_test_path(self):
		deleted_file_path = os.path.join(self.test_dir, "DELETED")
		return deleted_file_path

	def read(self):
		deleted_file_path = self.get_source_path()

		if not os.path.isfile(deleted_file_path):
			return False

		deleted_file = open(deleted_file_path, "r")
		line_list = [line.strip() for line in deleted_file]
		deleted_file.close()

		empty_line_pattern = re.compile(r"^[ \t]*$")
		deleted_line_pattern = re.compile(r"^[ \t]*(?P<pak_name>[^ \t]*)[ \t]*(?P<file_path>.*)$")

		for line in line_list:
			line_match = empty_line_pattern.match(line)
			if line_match:
				continue

			line_match = deleted_line_pattern.match(line)
			if line_match:
				pak_name = line_match.group("pak_name")
				file_path = line_match.group("file_path")
				self.set(pak_name, file_path)
				continue

			Ui.error("malformed line in DELETED file: " + line)

		return True

	def getActions(self):
		if not self.read():
			return []

		action_list = []

		for deleted_file_dict in self.deleted_file_list:
			pak_name = deleted_file_dict["pak_name"]
			file_path = deleted_file_dict["file_path"]

			if pak_name == self.source_tree.pak_name:
				action_dict = {
					"action_name": "delete",
					"file_path": file_path,
				}

				action_list.append(action_dict)

		return action_list

	def set(self, pak_name, file_path):
		deleted_file_dict = {
			"pak_name": pak_name,
			"file_path": file_path,
		}

		if deleted_file_dict not in self.deleted_file_list:
			self.deleted_file_list.append(deleted_file_dict)

	def write(self):
		if not self.deleted_part_list:
			return False

		Ui.laconic("writing DELETED file list")

		deleted_file = open(self.get_test_path(), "w")
		deleted_file.write(self.produce())
		deleted_file.close()

		return True

	def produce(self):
		line_list= []
		for deleted_part_dict in self.deleted_part_list:
			line = deleted_part_dict["pak_name"]
			line += " "
			line += deleted_part_dict["file_path"]
			line_list.append(line)

		line_list.sort()

		string = ""
		for line in line_list:
			string += line
			string += "\n"

		return string

	def translate(self):
		inspector = Inspector(self.source_tree, self.stage_name)

		for deleted_file_dict in self.deleted_file_list:
			file_path = deleted_file_dict["file_path"]
			action_name = inspector.inspect(file_path, deletion=True)

			for action_type in Action.list():
				if action_type.keyword == action_name:
					target_action = action_type(self.source_tree, self.test_dir, file_path, self.stage_name)

					translated_file_path = target_action.getFileNewName()

					deleted_part_dict = {
						"pak_name": deleted_file_dict["pak_name"],
						"file_path": translated_file_path,
					}

					self.deleted_part_list.append(deleted_part_dict)
					break;

		return self.deleted_part_list

	def removePart(self, pak_name, file_path):
		deleted_part_dict = {
			"pak_name": pak_name,
			"file_path": file_path,
		}

		self.deleted_part_list.remove(deleted_part_dict)

	def remove(self, pakdir_path):
		deleted_file_path = os.path.join(pakdir_path, "DELETED")
		if os.path.isfile(deleted_file_path):
			os.remove(deleted_file_path)


class Deps():
	def __init__(self, source_tree, test_dir):
		self.deps_dict = OrderedDict()
		self.source_dir = source_tree.dir
		self.test_dir = test_dir

	def get_source_path(self, deps_dir):
		if not deps_dir:
			deps_dir = self.source_dir

		deleted_file_path = os.path.join(deps_dir, "DEPS")

		return deleted_file_path

	def get_test_path(self, deps_dir):
		if not deps_dir:
			deps_dir = self.test_dir

		deleted_file_path = os.path.join(deps_dir, "DEPS")

		return deleted_file_path

	def read(self, deps_dir=None):
		deps_file_path = self.get_source_path(deps_dir)

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

	def translateTest(self):
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

	def write(self, deps_dir=None):
		deps_file_path = self.get_test_path(deps_dir)
		deps_file = open(deps_file_path, "w")
		deps_file.write(self.produce())
		deps_file.close()

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
	def __init__(self, source_dir):
		self.pakpath_list = []

		# FIXME: Ugly quick&dirty pakpath lookup.
		pakpath = os.path.dirname(os.path.realpath(source_dir))
		self.pakpath_list.append(pakpath)

		pakpath_env = os.getenv("PAKPATH")

		if pakpath_env:
			separator = ":"

			if os.name == 'nt':
				separator = ";"

			pakpath_list = pakpath_env.split(separator)

			for pakpath in pakpath_list:
				if pakpath != "":
					self.pakpath_list.append(os.path.realpath(pakpath))

			Ui.notice("PAKPATH set, will use: " + separator.join(self.pakpath_list))

		self.pakdir_dict = {}

		for pakpath in self.pakpath_list:
			for dir_name in os.listdir(pakpath):
				full_path = os.path.abspath(os.path.join(pakpath, dir_name))

				if os.path.isdir(full_path):
					# HACK: Only support dpkdir for now.
					dpkdir_ext = ".dpkdir"

					if dir_name.endswith(dpkdir_ext):
						# FIXME: Handle properly multiple dpkdir with same name
						# in multiple pakpaths.

						if dir_name not in self.pakdir_dict:
							pak_name = dir_name.split('_')[0]
							pak_version = dir_name.split('_')[1][:-len(dpkdir_ext)]

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
			git = Git(full_path, "dpk")
			pak_version = git.getVersion()

		logging.debug("found version for pak “" + pak_name + "”: " + pak_version)

		return pak_version
