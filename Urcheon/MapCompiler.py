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
		self.map_config = OrderedDict()

		self.default_profile = None

		self.map_config = OrderedDict()

		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.getKey("game")

		map_config_loaded = False

		# try loading map config first
		if map_path:
			map_config_path = Defaults.getPakMapConfigPath(source_dir, map_path)

			if map_config_path:
				self.readConfig(map_config_path)
				map_config_loaded = True

		# if no map config, try loading game map config
		if game_name:
			game_config_path = Defaults.getGameMapConfigPath(game_name)

			if not map_config_loaded and game_config_path:
				self.readConfig(game_config_path)
				map_config_loaded = True

		# if no map config and no game config, try loading default one
		default_config_path = Defaults.getDefaultMapConfigPath()
		if not map_config_loaded and default_config_path:
			self.readConfig(default_config_path)
			map_config_loaded = True

		# well, it must never occurs, previous errors raise before
		if not map_config_loaded:
			Ui.error("was not able to load any map config")


	def readConfig(self, config_path, is_parent=False):
		config = configparser.ConfigParser()

		if not config_path:
			Ui.error("not a map config path")

		logging.debug("reading map config: " + config_path)
		if not config.read(config_path):
			Ui.error("failed to load map config: ", config_path)

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

			del config["_init_"]

		logging.debug("build profiles found: " + str(config.sections()))

		for build_profile in config.sections():
			logging.debug("build profile found: " + build_profile)

			# overwrite parent profile
			self.map_config[build_profile] = OrderedDict()

			for build_stage in config[build_profile].keys():
				logging.debug("found build stage in “" + build_profile + "” profile: " + build_stage)

				logging.debug("add build parameters for “" + build_stage + "” stage: " + config[build_profile][build_stage])
				arguments = config[build_profile][build_stage].split(" ")
				self.map_config[build_profile][build_stage] = arguments

		if is_parent:
			return

		# reordered empty map_config without "all" stuff
		temp_map_config = OrderedDict()

		for build_profile in self.map_config.keys():
			if build_profile == "all":
				continue

			temp_map_config[build_profile] = OrderedDict()

			if "all" in self.map_config.keys():
				for build_stage in self.map_config["all"].keys():
					temp_map_config[build_profile][build_stage] = self.map_config["all"][build_stage]

			for build_stage in self.map_config[build_profile].keys():
				temp_map_config[build_profile][build_stage] = self.map_config[build_profile][build_stage]

		self.map_config = temp_map_config


	def requireDefaultProfile(self):
		if not self.default_profile:
			Ui.error("no default map profile found, cannot compile map")
		return self.default_profile


	def printConfig(self):
		first_line = True
		if self.default_profile:
			Ui.print("[_init_]")
			Ui.print("default = " + self.default_profile)
			first_line = False

		for build_profile in self.map_config.keys():
			if first_line:
				first_line = False
			else:
				Ui.print("")

			Ui.print("[" + build_profile + "]")

			if self.map_config[build_profile]:
				for build_stage in self.map_config[build_profile].keys():
					logging.debug("parameters for “" + build_stage + "” stage: " + str(self.map_config[build_profile][build_stage]))
					Ui.print(build_stage + " = " + " ".join(self.map_config[build_profile][build_stage]))


class Bsp():
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

	def compileBsp(self, map_path, build_prefix, stage_list=None):
		logging.debug("building " + map_path + " to prefix: " + build_prefix)

		# name without .map or .bsp extension
		map_base = os.path.splitext(os.path.basename(map_path))[0]
		lightmapdir_path = build_prefix + os.path.sep + map_base

		os.makedirs(build_prefix, exist_ok=True)

		prt_handle, prt_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "prt")
		srf_handle, srf_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "srf")
		bsp_path = build_prefix + os.path.sep + map_base + os.path.extsep + "bsp"

		map_config = Config(self.source_dir, game_name=self.game_name, map_path=map_path)

		if not stage_list:
			if self.map_profile not in map_config.map_config.keys():
				Ui.error("unknown map profile: " + self.map_profile)
			stage_list = map_config.map_config[self.map_profile].keys()

		build_stage_dict = map_config.map_config[self.map_profile]

		for build_stage in stage_list:
			if build_stage not in build_stage_dict:
				# happens in copy_bsp and merge_bsp
				continue

			Ui.print("Building " + map_path + ", stage: " + build_stage)

			extended_option_list = []

			stage_option_list = build_stage_dict[build_stage]

			tool_keyword = stage_option_list[0]
			logging.debug("tool keyword: " + tool_keyword)

			stage_option_list = stage_option_list[1:]
			logging.debug("stage options: " + str(stage_option_list))


			if tool_keyword[0] != "!":
				Ui.error("keyword must begin with “!”")

			tool_keyword = tool_keyword[1:]

			if ":" in tool_keyword:
				tool_name, tool_stage = tool_keyword.split(":")
			else:
				tool_name, tool_stage = tool_keyword, None

			logging.debug("tool name: " + tool_name)
			logging.debug("tool stage: " + str(tool_stage))

			if tool_name == "q3map2":
				# TODO: if previous stage failed
				source_path = map_path
				if tool_stage == "bsp":
					extended_option_list = ["-prtfile", prt_path, "-srffile", srf_path, "-bspfile", bsp_path]
					source_path = map_path
				elif tool_stage == "vis":
					extended_option_list = ["-prtfile", prt_path]
					source_path = bsp_path
				elif tool_stage == "light":
					extended_option_list = ["-srffile", srf_path, "-bspfile", bsp_path, "-lightmapdir", lightmapdir_path]
					source_path = map_path
				elif tool_stage == "nav":
					source_path = bsp_path
				elif tool_stage == "minimap":
					source_path = bsp_path
				else:
					Ui.error("bad “" + tool_name + "” stage: " + tool_stage)

				# pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
				pakpath_list = ["-fs_pakpath", self.source_dir]

				pakpath_env = os.getenv("PAKPATH")
				if pakpath_env:
					for pakpath in pakpath_env.split(":"):
						pakpath_list += ["-fs_pakpath", pakpath]

				call_list = [tool_name, "-" + tool_stage] + pakpath_list + extended_option_list + stage_option_list + [source_path]
				logging.debug("call list: " + str(call_list))
				Ui.verbose("Build command: " + " ".join(call_list))

				# TODO: remove that ugly workaround
				if tool_stage == "minimap" and self.game_name == "unvanquished":
					self.renderMiniMap(map_path, source_path, build_prefix, call_list)
				else:
					subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

			elif tool_name == "daemonmap":
				if tool_stage == "nav":
					source_path = bsp_path

					call_list = [tool_name, "-" + tool_stage] + stage_option_list + [source_path]
					logging.debug("call list: " + str(call_list))
					Ui.verbose("Build command: " + " ".join(call_list))

					subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

				else:
					Ui.error("bad “" + tool_name + "” stage: " + tool_stage)

			elif tool_name == "copy":
				source_path = map_path
				self.copyMap(map_path, build_prefix)

			else:
				Ui.error("unknown tool name: " + tool_name)

		if os.path.isfile(prt_path):
			os.remove(prt_path)

		if os.path.isfile(srf_path):
			os.remove(srf_path)

	def renderMiniMap(self, map_path, bsp_path, build_prefix, call_list):
		# TODO: if minimap not newer
		Ui.print("Creating MiniMap for: " + map_path)

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

		minimap_image_path = "minimaps" + os.path.sep + os.path.splitext(os.path.basename(bsp_path))[0]
		minimap_sidecar_path = build_prefix[:-5] + os.path.sep + minimap_image_path + os.path.extsep + "minimap"
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

	def copyMap(self, map_path, build_prefix):
		Ui.print("Copying map source: " + map_path)
		source_path = os.path.join(self.source_dir, map_path)
		copy_path = os.path.join(build_prefix, os.path.basename(map_path))
		shutil.copyfile(source_path, copy_path)
		shutil.copystat(source_path, copy_path)

