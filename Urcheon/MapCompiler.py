#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon import Defaults
from Urcheon import Repository
from Urcheon import Ui
import configparser
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import os
from collections import OrderedDict


class Config():
	def __init__(self, source_dir, game_name=None, map_path=None):
		self.profile = OrderedDict()

		self.default_profile = None
		self.keep_source = True

		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.getKey("game")

		config_loaded = False

		# try loading map config first
		if map_path:
			config_path = Defaults.getPakMapConfigPath(source_dir, map_path)

			if config_path:
				self.readConfig(config_path)
				config_loaded = True

		# if no map config, try loading game map config
		if game_name:
			game_config_path = Defaults.getGameMapConfigPath(game_name)

			if not config_loaded and game_config_path:
				self.readConfig(game_config_path)
				config_loaded = True

		# if no map config and no game config, try loading default one
		default_config_path = Defaults.getDefaultMapConfigPath()
		if not config_loaded and default_config_path:
			self.readConfig(default_config_path)
			config_loaded = True

		# well, it must never occurs, previous errors raise before
		if not config_loaded:
			Ui.error("was not able to load any map config")


	def readConfig(self, config_path, is_parent=False):
		config = configparser.ConfigParser()

		if not config_path:
			Ui.error("not a map config path")

		logging.debug("reading map config: " + config_path)
		if not config.read(config_path):
			Ui.error("failed to load map config: " + config_path)

		if "_init_" in config.sections():
			logging.debug("found “_init_” section in map profile: " + config_path)
			if "extend" in config["_init_"].keys():
				game_name = config["_init_"]["extend"]
				logging.debug("found “extend” instruction in “_init_” section: " + game_name)
				logging.debug("loading parent game map config")
				game_config_path = Defaults.getGameMapConfigPath(game_name)
				self.readConfig(game_config_path, is_parent=True)

			if "default" in config["_init_"].keys():
				default = config["_init_"]["default"]
				logging.debug("found “default” instruction in “_init_” section: " + default)
				self.default_profile = default

			if "source" in config["_init_"].keys():
				keep_source = config["_init_"]["source"]
				logging.debug("found “source” instruction in “_init_” section: " + keep_source)
				if keep_source == "true":
					# the default option is True
					pass
				elif keep_source == "false":
					self.keep_source = False
				else:
					Ui.error("unknown “source” value: " + keep_source)

			del config["_init_"]

		logging.debug("build profiles found: " + str(config.sections()))

		for build_profile in config.sections():
			logging.debug("build profile found: " + build_profile)

			# overwrite parent profile
			self.profile[build_profile] = OrderedDict()

			for build_stage in config[build_profile].keys():
				logging.debug("found build stage in “" + build_profile + "” profile: " + build_stage)

				logging.debug("add build parameters for “" + build_stage + "” stage: " + config[build_profile][build_stage])
				arguments = config[build_profile][build_stage].split(" ")
				self.profile[build_profile][build_stage] = arguments

		if is_parent:
			return

		# reordered empty config without "all" stuff
		temp_config = OrderedDict()

		for build_profile in self.profile.keys():
			if build_profile == "all":
				continue

			temp_config[build_profile] = OrderedDict()

			if "all" in self.profile.keys():
				for build_stage in self.profile["all"].keys():
					temp_config[build_profile][build_stage] = self.profile["all"][build_stage]

			for build_stage in self.profile[build_profile].keys():
				temp_config[build_profile][build_stage] = self.profile[build_profile][build_stage]

		self.profile = temp_config


	def requireDefaultProfile(self):
		if not self.default_profile:
			Ui.error("no default map profile found, cannot compile map")
		return self.default_profile


	def printConfig(self):
		print("[_init_]")
		if self.default_profile:
			print("default = " + self.default_profile)
		if self.keep_source == True :
			print("source = true")
		elif self.keep_source == False:
			print("source = false")

		for build_profile in self.profile.keys():
			print("")

			print("[" + build_profile + "]")

			if self.profile[build_profile]:
				for build_stage in self.profile[build_profile].keys():
					logging.debug("parameters for “" + build_stage + "” stage: " + str(self.profile[build_profile][build_stage]))
					print(build_stage + " = " + " ".join(self.profile[build_profile][build_stage]))


class Compiler():
	def __init__(self, source_dir, game_name=None, map_profile=None):
		self.source_dir = source_dir
		self.map_profile = map_profile

		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.requireKey("game")

		self.game_name = game_name

		if not map_profile:
			map_config = self.Config(source_dir)
			map_profile = map_config.requireDefaultProfile()

		self.map_profile = map_profile


		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None
		self.subprocess_stderr = None


	def compile(self, map_path, build_prefix, stage_list=None):
		self.map_path = map_path
		self.build_prefix = build_prefix
		self.tool_stage = None
		self.stage_option_list = []
		self.pakpath_list = []

		tool_dict = {
			"q3map2": self.q3map2,
			"daemonmap": self.daemonmap,
			"copy": self.copy,
		}

		logging.debug("building " + self.map_path + " to prefix: " + self.build_prefix)
		os.makedirs(self.build_prefix, exist_ok=True)

		self.map_config = Config(self.source_dir, game_name=self.game_name, map_path=map_path)

		# is it needed?
		# self.pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
		self.pakpath_list = ["-fs_pakpath", self.source_dir]

		for pakpath in Repository.PakPath().listPakPath():
			self.pakpath_list += ["-fs_pakpath", pakpath]

		if not stage_list:
			if self.map_profile not in self.map_config.profile.keys():
				Ui.error("unknown map profile: " + self.map_profile)
			stage_list = self.map_config.profile[self.map_profile].keys()

		build_stage_dict = self.map_config.profile[self.map_profile]

		for build_stage in stage_list:
			# TODO: if previous stage failed
			if build_stage not in build_stage_dict:
				# happens in copy_bsp and merge_bsp
				continue

			Ui.print("Building " + self.map_path + ", stage: " + build_stage)

			self.stage_option_list = build_stage_dict[build_stage]

			tool_keyword = self.stage_option_list[0]
			logging.debug("tool keyword: " + tool_keyword)

			self.stage_option_list = self.stage_option_list[1:]
			logging.debug("stage options: " + str(self.stage_option_list))

			if tool_keyword[0] != "!":
				Ui.error("keyword must begin with “!”")

			tool_keyword = tool_keyword[1:]

			if ":" in tool_keyword:
				tool_name, self.tool_stage = tool_keyword.split(":")
			else:
				tool_name, self.tool_stage = tool_keyword, None

			logging.debug("tool name: " + tool_name)
			logging.debug("tool stage: " + str(self.tool_stage))

			if tool_name in tool_dict:
				tool_dict[tool_name]()
			else:
				Ui.error("unknown tool name: " + tool_name)


	def q3map2(self):
		map_base = os.path.splitext(os.path.basename(self.map_path))[0]
		lightmapdir_path = os.path.join(self.build_prefix, map_base)
		prt_handle, prt_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "prt")
		srf_handle, srf_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "srf")
		bsp_path = os.path.join(self.build_prefix, map_base + os.path.extsep + "bsp")

		extended_option_list = []

		if self.tool_stage == "bsp":
			extended_option_list = ["-prtfile", prt_path, "-srffile", srf_path, "-bspfile", bsp_path]
			source_path = self.map_path
		elif self.tool_stage == "vis":
			extended_option_list = ["-prtfile", prt_path]
			source_path = bsp_path
		elif self.tool_stage == "light":
			extended_option_list = ["-srffile", srf_path, "-bspfile", bsp_path, "-lightmapdir", lightmapdir_path]
			source_path = self.map_path
		elif self.tool_stage == "nav":
			source_path = bsp_path
		elif self.tool_stage == "minimap":
			source_path = bsp_path
		else:
			Ui.error("bad q3map2 stage: " + stage)

		call_list = ["q3map2", "-" + self.tool_stage] + self.pakpath_list + extended_option_list + self.stage_option_list + [source_path]
		logging.debug("call list: " + str(call_list))
		Ui.verbose("Build command: " + " ".join(call_list))

		# TODO: remove that ugly workaround
		if self.tool_stage == "minimap" and self.game_name == "unvanquished":
			self.q3map2MiniMap()
		else:
			subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		# keep map source
		if self.tool_stage == "bsp" and self.map_config.keep_source:
			self.copy()

		if os.path.isfile(prt_path):
			os.remove(prt_path)

		if os.path.isfile(srf_path):
			os.remove(srf_path)


	def daemonmap(self):
		map_base = os.path.splitext(os.path.basename(self.map_path))[0]
		bsp_path = os.path.join(self.build_prefix, map_base + os.path.extsep + "bsp")
		if self.tool_stage == "nav":
			source_path = bsp_path

			call_list = ["daemonmap", "-" + self.tool_stage] + self.stage_option_list + [source_path]
			logging.debug("call list: " + str(call_list))
			Ui.verbose("Build command: " + " ".join(call_list))

			subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		else:
				Ui.error("bad daemonmap stage: " + tool_stage)


	def q3map2MiniMap(self):
		map_base = os.path.splitext(os.path.basename(self.map_path))[0]
		bsp_path = os.path.join(self.build_prefix, map_base + os.path.extsep + "bsp")

		source_path = bsp_path
		call_list = ["q3map2", "-" + self.tool_stage] + self.pakpath_list + self.stage_option_list + [source_path]

		maps_subpath_len = len(os.path.sep + "maps")
		minimap_dir = self.build_prefix[:-maps_subpath_len]
		minimap_sidecar_name = map_base + os.path.extsep + "minimap"
		minimap_sidecar_path = os.path.join(minimap_dir, "minimap", minimap_sidecar_name)

		# without ext, will be read by engine
		minimap_image_path = os.path.join("minimaps", map_base)

		# TODO: if minimap not newer
		Ui.print("Creating MiniMap for: " + self.map_path)

		tex_coords_pattern = re.compile(r"^size_texcoords (?P<c1>[0-9.-]*) (?P<c2>[0-9.-]*) [0-9.-]* (?P<c3>[0-9.-]*) (?P<c4>[0-9.-]*) [0-9.-]*$")

		tex_coords = None
		proc = subprocess.Popen(call_list, stdout=subprocess.PIPE, stderr=self.subprocess_stderr)
		with proc.stdout as stdout:
			for line in stdout:
				line = line.decode()
				match = tex_coords_pattern.match(line)
				if match:
					tex_coords = " ".join([match.group("c1"), match.group("c2"), match.group("c3"), match.group("c4")])

		if not tex_coords:
			Ui.error("failed to get coords from minimap generation")

		minimap_sidecar_str = "{\n"
		minimap_sidecar_str += "\tbackgroundColor 0.0 0.0 0.0 0.333\n"
		minimap_sidecar_str += "\tzone {\n"
		minimap_sidecar_str += "\t\tbounds 0 0 0 0 0 0\n"
		minimap_sidecar_str += "\t\timage \"" + minimap_image_path + "\" " + tex_coords + "\n"
		minimap_sidecar_str += "\t}\n"
		minimap_sidecar_str += "}\n"
		
		os.makedirs(os.path.dirname(minimap_sidecar_path), exist_ok=True)
		minimap_sidecar_file = open(minimap_sidecar_path, "w")
		minimap_sidecar_file.write(minimap_sidecar_str)
		minimap_sidecar_file.close()


	def copy(self):
		Ui.print("Copying map source: " + self.map_path)
		source_path = os.path.join(self.source_dir, self.map_path)
		copy_path = os.path.join(self.build_prefix, os.path.basename(self.map_path))
		shutil.copyfile(source_path, copy_path)
		shutil.copystat(source_path, copy_path)
