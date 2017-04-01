#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Default
from Urcheon import FileSystem
from Urcheon import Profile
from Urcheon import Repository
from Urcheon import Ui
import configparser
import logging
import os


class Game():
	def __init__(self, source_dir, game_name=None):
		self.source_dir = source_dir
		self.profile_fs = Profile.Fs(source_dir)

		self.key_dict = {}

		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.getKey("game")

		self.read(game_name)

		self.pak_format = self.requireKey("pak")
		self.pak_ext = os.path.extsep + self.pak_format
		self.pakdir_ext = self.pak_ext + "dir"


	def read(self, profile_name):
		profile_name = os.path.join(Default.game_profile_dir, profile_name + Default.game_profile_ext)
		profile_path = self.profile_fs.getPath(profile_name)

		if not profile_path:
			Ui.error("game profile file not found: " + profile_name)

		logging.debug("reading game profile file " + profile_path)
		config_parser = configparser.ConfigParser()

		if not config_parser.read(profile_path):
			Ui.error("error reading game profile file: " + profile_path)

		if "_init_" in config_parser.sections():
			logging.debug("found “_init_” section in game profile: " + profile_path)
			if "extend" in config_parser["_init_"].keys():
				game_name = config_parser["_init_"]["extend"]
				logging.debug("found “extend” instruction in “_init_” section: " + game_name)
				logging.debug("loading parent game profile")
				self.read(game_name)

			del config_parser["_init_"]

		# only one section supported at this time, let's keep it simple
		if "config" in config_parser.sections():
			logging.debug("config found in game profile file: " + profile_path)
			self.key_dict = config_parser["config"]


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
