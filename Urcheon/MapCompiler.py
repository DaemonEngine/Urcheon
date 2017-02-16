#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

from Urcheon import Defaults
from Urcheon.SourceTree import PakConfig
from Urcheon.Ui import Ui
import configparser
import logging
import shutil
import subprocess
import sys
import tempfile
import os
from collections import OrderedDict


ui = Ui()


class MapConfig():
	def __init__(self, source_dir, game_name=None, map_path=None):
		self.map_config = OrderedDict()

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
			pak_config = PakConfig(source_dir)
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
			ui.error("was not able to load any map config")


	def readConfig(self, config_path, is_parent=False):
		config = configparser.ConfigParser()

		if not config_path:
			ui.error("not a map config path")

		logging.debug("reading map config: " + config_path)
		if not config.read(config_path):
			ui.error("failed to load map config: ", config_path)

		if ":config:" in config.sections():
			logging.debug("found extend section in map profile: " + config_path)
			if "extend" in config[":config:"].keys():
				game_name = config[":config:"]["extend"]
				logging.debug("found “extend” instruction in “:config:” section: " + game_name)
				logging.debug("loading parent game map config")
				game_config_path = Defaults.getGameMapConfigPath(game_name)
				self.readConfig(game_config_path, is_parent=True)

			if "copy" in config[":config:"].keys():
				copy = config[":config:"]["copy"]
				logging.debug("found “copy” instruction in “:config:” section: " + copy)

				if copy == "yes":
					self.copy_map = True
				elif copy == "no":
					self.copy_map = False
				else:
					ui.error("unknown “copy” value in config section, must be “yes” or “no”: " + config_path)

			del config[":config:"]

		logging.debug("build profiles found: " + str(config.sections()))

		for build_profile in config.sections():
			logging.debug("build profile found: " + build_profile)

			if build_profile not in self.map_config.keys():
				self.map_config[build_profile] = OrderedDict()

			for build_stage in config[build_profile].keys():
				logging.debug("found build stage in “" + build_profile + "” profile: " + build_stage)
				if build_stage not in self.build_stages + [ "all" ]:
					ui.warning("unknown stage in “" + config_path + "”: " + build_stage)
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


	def printConfig(self):
		first_line = True
		for build_profile in self.map_config.keys():
			if first_line:
				first_line = False
			else:
				ui.print("")

			ui.print("[" + build_profile + "]")

			if self.map_config[build_profile]:
				for build_stage in self.map_config[build_profile].keys():
					logging.debug("parameters for “" + build_stage + "” stage: " + str(self.map_config[build_profile][build_stage]))
					ui.print(build_stage + " = " + " ".join(self.map_config[build_profile][build_stage]))


class BspCompiler():
	def __init__(self, source_dir, game_name, map_profile):
		self.source_dir = source_dir
		self.map_profile = map_profile

		# TODO: optional
		self.game_name = game_name

		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None;
		self.subprocess_stderr = None;


		"""
			if map_profile == self.map_profile:
				logging.debug("will use profile: " + map_profile)
			else
				ui.error("profile not found: " + map_profile)
				sys.exit()
		"""

	def compileBsp(self, map_path, build_prefix, stage_list=None):
		logging.debug("building " + map_path + " to prefix: " + build_prefix)

		# name without .map or .bsp extension
		map_base = os.path.splitext(os.path.basename(map_path))[0]
		lightmapdir_path = build_prefix + os.path.sep + map_base

		os.makedirs(build_prefix, exist_ok=True)

		prt_handle, prt_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "prt")
		srf_handle, srf_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "srf")
		bsp_path = build_prefix + os.path.sep + map_base + os.path.extsep + "bsp"

		map_config = MapConfig(self.source_dir, game_name=self.game_name, map_path=map_path)

		if not stage_list:
			if self.map_profile not in map_config.map_config.keys():
				ui.error("unknown map profile: " + self.map_profile)
			stage_list = map_config.map_config[self.map_profile].keys()

		build_stage_dict = map_config.map_config[self.map_profile]

		for build_stage in stage_list:
			if build_stage_dict[build_stage] == None:
				continue
			elif build_stage_dict[build_stage] == "none":
				continue

			ui.print("Building " + map_path + ", stage: " + build_stage)

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
				self.renderMiniMap(map_path, bsp_path)
				continue

			# pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
			pakpath_list = ["-fs_pakpath", self.source_dir]

			pakpath_env = os.getenv("PAKPATH")
			if pakpath_env:
				for pakpath in pakpath_env.split(":"):
					pakpath_list += ["-fs_pakpath", pakpath]

			stage_option_list = build_stage_dict[build_stage]
			logging.debug("stage options: " + str(stage_option_list))

			# TODO: game independant
			call_list = ["q3map2", "-game", "unvanquished"] + ["-" + build_stage] + pakpath_list + extended_option_list + stage_option_list + [source_path]

			logging.debug("call list: " + str(call_list))
			# TODO: verbose?
			ui.print("Build command: " + " ".join(call_list))
			subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		if map_config.copy_map:
			self.copyMap(map_path, build_prefix)

		if os.path.isfile(prt_path):
			os.remove(prt_path)

		if os.path.isfile(srf_path):
			os.remove(srf_path)

	def renderMiniMap(self, map_path, bsp_path):
		# TODO: if minimap not newer
		ui.print("Creating MiniMap for: " + map_path)
#		subprocess.call(["q3map2", "-game", "unvanquished", "-minimap", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
		q3map2_helper_path = os.path.join(sys.path[0], "tools", "q3map2_helper")
		subprocess.call([q3map2_helper_path, "--minimap", bsp_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

	def copyMap(self, map_path, build_prefix):
		# TODO: for all files created
#		shutil.copystat(source_path, build_path)

		ui.print("Copying map source: " + map_path)
		map_name = os.path.basename(map_path)
		copy_path = build_prefix + os.path.sep + map_name
		shutil.copyfile(map_path, copy_path)
		shutil.copystat(map_path, copy_path)


