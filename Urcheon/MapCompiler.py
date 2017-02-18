#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


from Urcheon import Defaults
from Urcheon import SourceTree
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
		self.copy_map = True

		# I want compilation in this order
		self.build_stages = [
			"bsp",
			"vis",
			"light",
			"nav",
			"minimap",
		]

		self.map_config = OrderedDict()

		if not game_name:
			pak_config = SourceTree.Config(source_dir)
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

		if ":config:" in config.sections():
			logging.debug("found extend section in map profile: " + config_path)
			if "extend" in config[":config:"].keys():
				game_name = config[":config:"]["extend"]
				logging.debug("found “extend” instruction in “:config:” section: " + game_name)
				logging.debug("loading parent game map config")
				game_config_path = Defaults.getGameMapConfigPath(game_name)
				self.readConfig(game_config_path, is_parent=True)

			if "default" in config[":config:"].keys():
				default = config[":config:"]["default"]
				logging.debug("found “default” instruction in “:config:” section: " + default)
				self.default_profile = default

			if "copy" in config[":config:"].keys():
				copy = config[":config:"]["copy"]
				logging.debug("found “copy” instruction in “:config:” section: " + copy)

				if copy == "yes":
					self.copy_map = True
				elif copy == "no":
					self.copy_map = False
				else:
					Ui.error("unknown “copy” value in config section, must be “yes” or “no”: " + config_path)

			del config[":config:"]

		logging.debug("build profiles found: " + str(config.sections()))

		for build_profile in config.sections():
			logging.debug("build profile found: " + build_profile)

			if build_profile not in self.map_config.keys():
				self.map_config[build_profile] = OrderedDict()

			for build_stage in config[build_profile].keys():
				logging.debug("found build stage in “" + build_profile + "” profile: " + build_stage)
				if build_stage not in self.build_stages + [ "all" ]:
					Ui.warning("unknown stage in “" + config_path + "”: " + build_stage)
					continue

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
			if build_profile not in temp_map_config:
				temp_map_config[build_profile] = OrderedDict()

			# in this order please
			for build_stage in self.build_stages:
				# but ignore it if it does not exist
				# it already ignores "all" stage
				if build_stage not in self.map_config[build_profile].keys():
					continue
				temp_map_config[build_profile][build_stage] = []

		# things to set in all profiles, all stages
		all_all_prepend = None
		if "all" in self.map_config.keys():
			if "all" in self.map_config["all"].keys():
				all_all_prepend = self.map_config["all"]["all"]

		if all_all_prepend:
			for build_profile in temp_map_config.keys():
				for build_stage in temp_map_config[build_profile].keys():
					# no need to concatenate here, we know it's already empty, but there
					temp_map_config[build_profile][build_stage] = all_all_prepend

		# things to set in all profiles but same stage
		if "all" in self.map_config.keys():
			for build_profile in temp_map_config.keys():
				for build_stage in temp_map_config[build_profile].keys():
					if build_stage in self.map_config["all"]:
						all_stage_prepend = self.map_config["all"][build_stage]
						# concatenate
						arguments = temp_map_config[build_profile][build_stage] + all_stage_prepend
						temp_map_config[build_profile][build_stage] = arguments
						
		# things to set in all stages of same profile
		for build_profile in temp_map_config.keys():
			for build_stage in temp_map_config[build_profile].keys():
				if "all" in self.map_config[build_profile].keys():
					# concatenate
					arguments = temp_map_config[build_profile][build_stage] + self.map_config[build_profile]["all"]
					temp_map_config[build_profile][build_stage] = arguments

		for build_profile in temp_map_config.keys():
			for build_stage in temp_map_config[build_profile].keys():
				arguments = temp_map_config[build_profile][build_stage] + self.map_config[build_profile][build_stage]
				arguments = [ a for a in arguments if a != ""]
				temp_map_config[build_profile][build_stage] = arguments

		self.map_config = temp_map_config


	def requireDefaultProfile(self):
		if not self.default_profile:
			Ui.error("no default map profile found, cannot compile map")
		return self.default_profile


	def printConfig(self):
		first_line = True
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
			pak_config = SourceTree.Config(source_dir)
			game_name = pak_config.requireKey("game")

		self.game_name = game_name

		if not map_profile:
			map_config = MapCompiler.Config(source_dir)
			map_profile = map_config.requireDefaultProfile()

		self.map_profile = map_profile


		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None;
		self.subprocess_stderr = None;

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
			if build_stage not in build_stage_dict.keys():
				continue
			# TODO: :none: ?
			elif build_stage_dict[build_stage] == "none":
				continue

			Ui.print("Building " + map_path + ", stage: " + build_stage)

			# TODO: if previous stage failed
			source_path = map_path
			extended_option_list = []
			if build_stage == "bsp":
				extended_option_list = ["-prtfile", prt_path, "-srffile", srf_path, "-bspfile", bsp_path]
				source_path = map_path
			elif build_stage == "vis":
				extended_option_list = ["-prtfile", prt_path]
				source_path = bsp_path
			elif build_stage == "light":
				extended_option_list = ["-srffile", srf_path, "-bspfile", bsp_path, "-lightmapdir", lightmapdir_path]
				source_path = map_path
			elif build_stage == "nav":
				source_path = bsp_path
			elif build_stage == "minimap":
				source_path = bsp_path

			# pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
			pakpath_list = ["-fs_pakpath", self.source_dir]

			pakpath_env = os.getenv("PAKPATH")
			if pakpath_env:
				for pakpath in pakpath_env.split(":"):
					pakpath_list += ["-fs_pakpath", pakpath]

			stage_option_list = build_stage_dict[build_stage]
			logging.debug("stage options: " + str(stage_option_list))

			call_list = ["q3map2", "-" + build_stage] + pakpath_list + extended_option_list + stage_option_list + [source_path]

			logging.debug("call list: " + str(call_list))

			Ui.verbose("Build command: " + " ".join(call_list))

			# TODO: remove that ugly workaround
			if build_stage == "minimap" and self.game_name == "unvanquished":
				self.renderMiniMap(map_path, source_path, build_prefix, call_list)
			else:
				subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		if map_config.copy_map:
			self.copyMap(map_path, build_prefix)

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
		return
		map_name = os.path.basename(map_path)
		copy_path = build_prefix + os.path.sep + map_name
		shutil.copyfile(map_path, copy_path)
		shutil.copystat(map_path, copy_path)


