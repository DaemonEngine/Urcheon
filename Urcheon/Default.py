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

profile_dir = "profile"

legacy_pakinfo_dir = ".pakinfo"
legacy_setinfo_dir = ".setinfo"
repository_config_dir = ".urcheon"

cache_dir = ".cache"

legacy_paktrace_dir = ".paktrace"
paktrace_dir = os.path.join(cache_dir, "urcheon", "paktrace")
paktrace_file_ext = ".json"

default_base = "common"

game_profile_dir = "game"
game_profile_ext = ".conf"

map_profile_dir = "map"
map_profile_ext = ".conf"

sloth_profile_dir = "sloth"
sloth_profile_ext = ".sloth"

prevrun_profile_dir = "prevrun"
prevrun_profile_ext = ".prevrun"

slothrun_profile_dir = "slothrun"
slothrun_profile_ext = ".slothrun"

file_profile_dir = "file"
file_profile_ext = ".conf"
action_list_dir = "action"
action_list_ext = ".txt"

ignore_list_file = "ignore.txt"

build_prefix = "build"
source_prefix = "src"
test_prefix = "test"
pak_prefix = "pkg"

prefix_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

# HACK: if installed in lib/python3/dist-packages
if os.path.basename(prefix_dir) == "dist-packages":
	prefix_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../.."))

for sub_dir in [".", "share/Urcheon"]:
	share_dir = os.path.realpath(os.path.join(prefix_dir, sub_dir))
	if os.path.isdir(os.path.join(share_dir, profile_dir)):
		break

def getCollectionConfigDir(source_dir):
	config_dir = os.path.join(source_dir, repository_config_dir)
	legacy_config_dir = os.path.join(source_dir, legacy_setinfo_dir)

	if os.path.isdir(config_dir):
		logging.debug("Found collection configuration directory: " + config_dir)

	elif os.path.isdir(legacy_config_dir):
		logging.debug("Found legacy collection configuration directory: " + legacy_config_dir)
		config_dir = legacy_config_dir

	return config_dir

def getPakConfigDir(source_dir):
	config_dir = os.path.abspath(os.path.join(source_dir, repository_config_dir))
	legacy_config_dir = os.path.abspath(os.path.join(source_dir, legacy_pakinfo_dir))

	if os.path.isdir(config_dir):
		logging.debug("Found package configuration directory: " + config_dir)
	elif os.path.isdir(legacy_config_dir):
		logging.debug("Found legacy package configuration directory: " + config_dir)
		config_dir = legacy_config_dir

	return config_dir

def getPakTraceDir(build_dir):
	cache_dir = os.path.abspath(os.path.join(build_dir, paktrace_dir))
	legacy_cache_dir = os.path.abspath(os.path.join(build_dir, legacy_paktrace_dir))

	if os.path.isdir(cache_dir):
		logging.debug("Found paktrace cache directory: " + cache_dir)
	elif os.path.isdir(legacy_cache_dir):
		logging.debug("Found legacy paktrace cache directory: " + cache_dir)
		cache_dir = legacy_cache_dir

	return cache_dir
