#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 


import logging
import os.path
import sys


data_dir = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0])))
map_config_dir = data_dir + os.path.sep + "profile" + os.path.sep + "map"
# net yet used, must port to toml first
files_config_dir = data_dir + os.path.sep + "profile" + os.path.sep + "file"

def getPakMapConfigPath(source_dir, map_path):
	map_base = os.path.splitext(os.path.basename(map_path))[0]
	pak_map_config_path = source_dir + os.path.sep + ".pakinfo" + os.path.sep + "map" + os.path.sep + map_base + os.path.extsep + "ini"
	if os.path.isfile(pak_map_config_path):
		logging.debug("map profile found: " + pak_map_config_path)
		return pak_map_config_path
	else:
		logging.debug("map profile not found: " + pak_map_config_path)
		return None

def getGameMapConfigPath(game_name):
	game_map_config_file = game_name + os.path.extsep + "ini"
	game_map_config_path = map_config_dir + os.path.sep + game_map_config_file
	if os.path.isfile(game_map_config_path):
		logging.debug("game map config found: " + game_map_config_path)
		return game_map_config_path
	else:
		logging.debug("game map config not found")
		return None

def getDefaultMapConfigPath():
	default_map_config_file = "common" + os.path.extsep + "ini"
	default_map_config_path = map_config_dir + os.path.sep + default_map_config_file
	if os.path.isfile(default_map_config_path):
		logging.debug("default map config found: " + default_map_config_path)
		return default_map_config_path
	else:
		logging.debug("default map config not found")
		return None

