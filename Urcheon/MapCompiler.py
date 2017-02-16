#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

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


class BspCompiler():
	def __init__(self, source_dir, game_name, map_profile):
		self.map_config = configparser.ConfigParser()
		self.source_dir = source_dir
		self.map_profile = map_profile
		self.build_stage_dict = OrderedDict()

		# I want compilation in this order:
		self.build_stage_dict["bsp"] = None
		self.build_stage_dict["vis"] = None
		self.build_stage_dict["light"] = None
		self.build_stage_dict["nav"] = None
		self.build_stage_dict["minimap"] = None
		self.build_stage_dict["source"] = None

		# TODO: set something else for quiet and verbose mode
		self.subprocess_stdout = None;
		self.subprocess_stderr = None;

		# TODO: check
		default_ini_file = game_name + os.path.extsep + "ini"
		default_ini_path = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0]))) + os.path.sep + "profiles" + os.path.sep + "maps" + os.path.sep + default_ini_file

		self.readIni(default_ini_path)

	def readIni(self, ini_path):
		logging.debug("reading map profile: " + ini_path)
		self.map_config.read(ini_path)

		logging.debug("build profiles: " + str(self.map_config.sections()))
		for map_profile in self.map_config.sections():
			logging.debug("build profile found: " + map_profile)

			if map_profile == self.map_profile:
				logging.debug("will use profile: " + map_profile)

				for build_stage in self.map_config[map_profile].keys():
					if not build_stage in self.build_stage_dict.keys():
						ui.warning("unknown stage in " + ini_path + ": " + build_stage)

					else:
						logging.debug("add build parameter for stage " + build_stage + ": " + self.map_config[map_profile][build_stage])
						self.build_stage_dict[build_stage] = self.map_config[map_profile][build_stage]


	def compileBsp(self, map_path, build_prefix, stage_list=None):
		logging.debug("building " + map_path + " to prefix: " + build_prefix)

		# name without .map or .bsp extension
		map_base = os.path.splitext(os.path.basename(map_path))[0]
		lightmapdir_path = build_prefix + os.path.sep + map_base

		map_profile_path =  self.source_dir + os.path.sep + ".pakinfo" + os.path.sep + "maps" + os.path.sep + map_base + os.path.extsep + "ini"

		os.makedirs(build_prefix, exist_ok=True)

		if os.path.isfile(map_profile_path):
			ui.print("Customized build profile found: " + map_profile_path)
			self.readIni(map_profile_path)
		else:
			logging.debug("map profile not found: " + map_profile_path)

		prt_handle, prt_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "prt")
		srf_handle, srf_path = tempfile.mkstemp(suffix="_" + map_base + os.path.extsep + "srf")
		bsp_path = build_prefix + os.path.sep + map_base + os.path.extsep + "bsp"

		if not stage_list:
			stage_list = self.build_stage_dict.keys()

		for build_stage in stage_list:
			if self.build_stage_dict[build_stage] == None:
				continue
			elif self.build_stage_dict[build_stage] == "none":
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
				source_path == bsp_path
			elif build_stage == "minimap":
				self.renderMiniMap(map_path, bsp_path)
				continue
			elif build_stage == "source":
				self.copyMap(map_path, build_prefix)
				continue

			# pakpath_list = ["-fs_pakpath", os.path.abspath(self.source_dir)]
			pakpath_list = ["-fs_pakpath", self.source_dir]

			pakpath_env = os.getenv("PAKPATH")
			if pakpath_env:
				for pakpath in pakpath_env.split(":"):
					pakpath_list += ["-fs_pakpath", pakpath]

			stage_option_list = self.build_stage_dict[build_stage].split(" ")
			print("stage options: " + str(stage_option_list))
			if stage_option_list == ['']:
				stage_option_list == []

			# TODO: game independant
			call_list = ["q3map2", "-game", "unvanquished"] + ["-" + build_stage] + pakpath_list + extended_option_list + stage_option_list + [source_path]

			logging.debug("call list: " + str(call_list))
			# TODO: verbose?
			ui.print("Build command: " + " ".join(call_list))
			subprocess.call(call_list, stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

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


