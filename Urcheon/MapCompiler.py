#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Default
from Urcheon import Parallelism
from Urcheon import Profile
from Urcheon import Repository
from Urcheon import Ui
from collections import OrderedDict
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
import os
import toml


class Config():
	def __init__(self, source_tree, map_path=None):
		self.source_dir = source_tree.dir
		self.game_name = source_tree.game_name

		self.profile_fs = Profile.Fs(self.source_dir)
		self.profile_dict = OrderedDict()

		self.default_profile = None
		self.keep_source = True
		self.q3map2_config = {}


		config_path = None

		# try loading map config first
		if map_path:
			map_base = os.path.splitext(os.path.basename(map_path))[0]
			map_config_path = os.path.join(Default.map_profile_dir, map_base + Default.map_profile_ext)

			if self.profile_fs.isFile(map_config_path):
				config_path = map_config_path

		# TODO: name config based on pak name instead of game name

		# if no map config, try loading game map config
		if not config_path and self.game_name:
			game_config_path = os.path.join(Default.map_profile_dir, self.game_name + Default.map_profile_ext)

			if self.profile_fs.isFile(game_config_path):
				config_path = game_config_path

		# if no map config and no game config, try loading default one
		if not config_path:
			default_config_path = os.path.join(Default.map_profile_dir, Default.default_base + Default.map_profile_ext)

			if self.profile_fs.isFile(default_config_path):
				config_path = default_config_path

		# well, if it occurs it means there is missing files installation dir
		if not config_path:
			Ui.error("missing map compiler config")

		self.readConfig(config_path)

	def readConfig(self, config_file_name, is_parent=False):
		config_path = self.profile_fs.getPath(config_file_name)

		logging.debug("reading map config: " + config_path)
		config_file = open(config_path, "r")
		config_dict = toml.load(config_file, _dict=OrderedDict)
		config_file.close()

		if "_init_" in config_dict.keys():
			logging.debug("found “_init_” section in map profile: " + config_file_name)
			if "extend" in config_dict["_init_"].keys():
				extend_game_name = config_dict["_init_"]["extend"]
				logging.debug("found “extend” instruction in “_init_” section: " + extend_game_name)
				logging.debug("loading parent game map config")

				if extend_game_name == "${game}":
					extend_game_name = self.game_name

				game_config_path = os.path.join(Default.map_profile_dir, extend_game_name + Default.map_profile_ext)
				self.readConfig(game_config_path, is_parent=True)

			if "default" in config_dict["_init_"].keys():
				default = config_dict["_init_"]["default"]
				logging.debug("found “default” instruction in “_init_” section: " + default)
				self.default_profile = default

			if "source" in config_dict["_init_"].keys():
				keep_source = config_dict["_init_"]["source"]
				logging.debug("found “source” instruction in “_init_” section: " + str(keep_source))
				self.keep_source = keep_source

			del config_dict["_init_"]

		if "_q3map2_" in config_dict.keys():
			for key in config_dict["_q3map2_"].keys():
				value = config_dict["_q3map2_"][key]
				if value == "${game}":
					value = self.game_name
				self.q3map2_config[key] = value
			del config_dict["_q3map2_"]

		logging.debug("build profiles found: " + ", ".join(config_dict.keys()))

		for profile_name in config_dict.keys():
			logging.debug("build profile found: " + profile_name)

			# overwrite parent profile
			self.profile_dict[profile_name] = OrderedDict()

			for build_stage in config_dict[profile_name].keys():
				logging.debug("found build stage in “" + profile_name + "” profile: " + build_stage)

				profile_build_stage_dict = OrderedDict()
				config_stage_dict = config_dict[profile_name][build_stage]

				if "tool" in config_stage_dict.keys():
					if isinstance(config_stage_dict["tool"], str):
						logging.debug("found tool, “" + build_stage + "” stage will run: " + config_stage_dict["tool"])
						profile_build_stage_dict["tool"] = config_stage_dict["tool"]
					else:
						logging.error("in map build profile stage, \"tool\" key must be a string")
				else:
					logging.error("missing tool in “" + build_stage + "” stage in profile: " + profile_name)

				if "after" in config_stage_dict.keys():
					if isinstance(config_stage_dict["after"], str):
						logging.debug("found prerequisite, stage “" + build_stage + "” must run after: " + config_stage_dict["after"])
						profile_build_stage_dict["prerequisites"] = [config_stage_dict["after"]]
					elif isinstance(config_stage_dict["after"], list):
						logging.debug("found prerequisites, stage “" + build_stage + "” must run after: " + ", ".join(config_stage_dict["after"]))
						profile_build_stage_dict["prerequisites"] = config_stage_dict["after"]
					else:
						logging.error("in map build profile stage, \"after\" key must be a string or a list")
				else:
					profile_build_stage_dict["prerequisites"] = []

				if "options" in config_stage_dict.keys():
					if isinstance(config_stage_dict["options"], str):
						logging.debug("found options for “" + build_stage + "” stage: " + config_stage_dict["options"])
						profile_build_stage_dict["options"] = config_stage_dict["options"].split(" ")
					else:
						logging.error("in map build profile stage, \"options\" key must be a string")
				else:
					profile_build_stage_dict["options"] = []

				self.profile_dict[profile_name][build_stage] = profile_build_stage_dict

		default_prerequisite_dict = {
			"vis": ["bsp"],
			"light": ["vis"],
			"minimap": ["vis"],
			"nav": ["vis"],
		}

		for profile_name in self.profile_dict.keys():
				# HACK: vis stage is optional
				if "vis" not in self.profile_dict[profile_name].keys() \
					and "bsp" in self.profile_dict[profile_name].keys():
					self.profile_dict[profile_name]["vis"] = {
						"tool": "dummy",
						"options": [],
					}

				# set default prerequisites
				for stage_name in self.profile_dict[profile_name].keys():
					is_prerequisites_empty = False
					if "prerequisites" in self.profile_dict[profile_name][stage_name].keys():
						if self.profile_dict[profile_name][stage_name]["prerequisites"] == []:
							is_prerequisites_empty = True
					else:
						# FIXME: isn't always set?
						self.profile_dict[profile_name][stage_name]["prerequisites"] = []
						is_prerequisites_empty = True

					if is_prerequisites_empty:
						if stage_name in default_prerequisite_dict.keys():
							for prerequisite_stage_name in default_prerequisite_dict[stage_name]:
								if stage_name in self.profile_dict[profile_name].keys():
									self.profile_dict[profile_name][stage_name]["prerequisites"].append(prerequisite_stage_name)

		if is_parent:
			return


	def requireDefaultProfile(self):
		if not self.default_profile:
			Ui.error("no default map profile found, cannot compile map")
		return self.default_profile


	def printConfig(self):
		# TODO: order it?
		print(toml.dumps(self.profile_dict))


class Compiler():
	def __init__(self, source_tree, map_profile=None, is_parallel=True):
		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.map_profile = map_profile
		self.is_parallel = is_parallel

		if not map_profile:
			# TODO: test it
			map_config = Config(self.source_tree)
			map_profile = map_config.requireDefaultProfile()

		self.map_profile = map_profile

		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None
		self.subprocess_stderr = None


	def compile(self, map_path, build_prefix, stage_done=[]):
		self.map_path = map_path
		self.build_prefix = build_prefix
		stage_name = None
		stage_option_list = []
		self.pakpath_list = []

		tool_dict = {
			"q3map2": self.q3map2,
			"daemonmap": self.daemonmap,
			"copy": self.copy,
			"dummy": self.dummy,
		}

		prt_handle, self.prt_path = tempfile.mkstemp(suffix="_q3map2" + os.path.extsep + "prt")
		srf_handle, self.srf_path = tempfile.mkstemp(suffix="_q3map2" + os.path.extsep + "srf")
		# close them since they will be written and read by another program
		os.close(prt_handle)
		os.close(srf_handle)

		logging.debug("building " + self.map_path + " to prefix: " + self.build_prefix)
		os.makedirs(self.build_prefix, exist_ok=True)

		self.map_config = Config(self.source_tree, map_path=map_path)
		self.pakpath_list = Repository.PakVfs().listPakPath()

		build_stage_dict = self.map_config.profile_dict[self.map_profile]

		# FIXME: if default profile is not set but map profile is set on command line
		# this fails on recursion (transient dir processing)
		if self.map_profile not in self.map_config.profile_dict.keys():
			Ui.error("unknown map profile: " + self.map_profile)

		# list(…) because otherwise:
		# AttributeError: 'odict_keys' object has no attribute 'remove'
		stage_list = list(build_stage_dict.keys())

		# remove from todo list
		# stages that are already marked as done
		# by actions like copy_bsp or merge_bsp
		for stage_name in stage_done:
			if stage_name in stage_list:
				stage_list.remove(stage_name)

		subprocess_dict = {}

		# loop until all the stages are done
		while stage_list != []:
			for stage_name in stage_list:
				# if stage started (ended or not), skip it
				if stage_name in subprocess_dict.keys():
					# if stage ended, remove it from the todo list
					if not subprocess_dict[stage_name].is_alive():
						# join dead thread to raise thread exceptions
						Parallelism.joinDeadThreads(list(subprocess_dict.values()))

						del subprocess_dict[stage_name]
						stage_list.remove(stage_name)
					continue

				logging.debug("found stage: " + stage_name)

				stage_option_list = build_stage_dict[stage_name]

				tool_name = stage_option_list["tool"]
				logging.debug("tool name: " + tool_name)

				if not tool_name in tool_dict:
					Ui.error("unknown tool name: " + tool_name)

				prerequisite_list = stage_option_list["prerequisites"]
				logging.debug("stage prerequisites: " + str(prerequisite_list))

				# if there is at least one stage not done that is known as prerequisite, pass this stage
				if not set(stage_list).isdisjoint(prerequisite_list):
					continue

				# otherwise run the stage
				Ui.laconic("Building " + self.map_path + ", stage: " + stage_name)

				option_list = stage_option_list["options"]
				logging.debug("stage options: " + str(option_list))

				if tool_name in ["q3map2", "daemonmap"]:
					option_list = ["-v"] + option_list
					# default game
					if not "-game" in option_list:
						if "game" in self.map_config.q3map2_config.keys():
							option_list = ["-game", self.map_config.q3map2_config["game"]] + option_list

				subprocess_dict[stage_name] = Parallelism.Thread(target=tool_dict[tool_name], args=(option_list,))
				subprocess_dict[stage_name].start()

				# wait for this task to finish if sequential build
				if not self.is_parallel:
					subprocess_dict[stage_name].join()

				# join dead thread to raise thread exceptions
				Parallelism.joinDeadThreads(list(subprocess_dict.values()))

			# no need to loop at full cpu speed
			time.sleep(.05)

		# when the last stage is running, find it and wait for it
		for stage_name in subprocess_dict.keys():
			subprocess_dict[stage_name].join()

		if os.path.isfile(self.prt_path):
			os.remove(self.prt_path)

		if os.path.isfile(self.srf_path):
			os.remove(self.srf_path)


	def dummy(self, option_list):
		pass


	def q3map2(self, option_list, tool_name="q3map2"):
		map_base = os.path.splitext(os.path.basename(self.map_path))[0]
		lightmapdir_path = os.path.join(self.build_prefix, map_base)
		bsp_path = os.path.join(self.build_prefix, map_base + os.path.extsep + "bsp")

		# FIXME: needed for some advanced lightstyle (generated q3map2_ shader)
		# q3map2 is not able to create the “scripts/” directory itself
		scriptdir_path = os.path.realpath(os.path.join(self.build_prefix, "..", "scripts"))
		os.makedirs(scriptdir_path, exist_ok=True)

		pakpath_option_list = ["-fs_nobasepath", "-fs_nohomepath", "-fs_nomagicpath"]

		# FIXME: is os.path.abspath() needed?
		pakpath_option_list += ["-fs_pakpath", self.source_dir]

		for pakpath in self.pakpath_list:
			# FIXME: is os.path.abspath() needed?
			pakpath_option_list += ["-fs_pakpath", pakpath]

		extended_option_list = []

		# bsp stage is the one that calls -bsp, etc.
		for stage in ["bsp", "vis", "light", "minimap", "nav"]:
			if "-" + stage in option_list:
				stage_name = stage
				logging.debug("stage name: " + stage_name)

		if "-bsp" in option_list:
			extended_option_list = ["-prtfile", self.prt_path, "-srffile", self.srf_path, "-bspfile", bsp_path, "-leaktest", "-custinfoparms"]
			source_path = self.map_path
		elif "-vis" in option_list:
			extended_option_list = ["-prtfile", self.prt_path, "-saveprt"]
			source_path = bsp_path
		elif "-light" in option_list:
			extended_option_list = ["-srffile", self.srf_path, "-bspfile", bsp_path, "-lightmapdir", lightmapdir_path]
			source_path = self.map_path
		elif "-nav" in option_list:
			source_path = bsp_path
		elif "-minimap" in option_list:
			source_path = bsp_path
		else:
			extended_option_list = ["-prtfile", self.prt_path, "-srffile", self.srf_path, "-bspfile", bsp_path]
			# TODO: define the name somewhere
			Ui.warning("unknown q3map2 stage in command line, remind that -bsp is required by Urcheon: " + " ".join(option_list))
			source_path = self.map_path

		command_list = [tool_name] + option_list + pakpath_option_list + extended_option_list + [source_path]
		logging.debug("call list: " + str(command_list))
		Ui.verbose("Build command: " + " ".join(command_list))

		if subprocess.call(command_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr) != 0:
				Ui.error("command failed: '" + "' '".join(command_list) + "'")

		# keep map source
		if "-bsp" in option_list and self.map_config.keep_source:
			self.copy([])


	def daemonmap(self, option_list):
		self.q3map2(option_list, tool_name="daemonmap")

	def copy(self, option_list):
		Ui.laconic("Copying map source: " + self.map_path)
		source_path = os.path.join(self.source_dir, self.map_path)
		if os.path.isfile(source_path):
			copy_path = os.path.join(self.build_prefix, os.path.basename(self.map_path))
			shutil.copyfile(source_path, copy_path)
			shutil.copystat(source_path, copy_path)
