#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon.Ui import Ui
import configparser
import importlib
import logging
import operator
import os
from collections import OrderedDict


ui = Ui()


class PakConfig():
	def __init__(self, source_dir):
		# TODO: check absolute path (check in map ini too)
		config_pak_path = source_dir + os.path.sep + ".pakinfo" + os.path.sep + "pak" + os.path.extsep +  "ini"
		self.pak_config = configparser.ConfigParser()
		self.key_dict = None
		self.loaded = False

		if os.path.isfile(config_pak_path):
			self.readConfig(config_pak_path)
		else:
			logging.debug("pak config file not found: " + config_pak_path)

	def readConfig(self, config_pak_path):
		logging.debug("reading pak config file " + config_pak_path)

		if not self.pak_config.read(config_pak_path):
			ui.error("error reading pak config file: " + config_pak_path)

		logging.debug("config sections: " + str(self.pak_config.sections()))

		if not "config" in self.pak_config.sections():
			ui.error("can't find config section in pak config file: " + config_pak_path)

		logging.debug("config found in pak config file: " + config_pak_path)

		self.key_dict = self.pak_config["config"]

	def requireKey(self, key_name):
		# TODO: strip quotes
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			ui.error("key not found in pak config: " + key_name)

	def getKey(self, key_name):
		# TODO: strip quotes
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			return None


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
		self.action_name_dict["convert_vorbis"] =			"convert to vorbis format"
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
		file_type_ordered_list = [x[0] for x in sorted(self.file_profile.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
		logging.debug("looking for file path:" + file_path)
#		logging.debug("will try file types in this order: ", str(file_type_ordered_list))

		action = "keep"
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

		if action == "keep":
			ui.warning(file_path + ": unknown file found, will " + self.action_name_dict[action] + ".")
		else:
			ui.print(file_path + ": " + description + " found, will " + self.action_name_dict[action] + ".")

		return action

