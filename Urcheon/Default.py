#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


import os.path
import sys


share_dir = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0])))
profile_dir = "profile"
pakinfo_dir = ".pakinfo"
paktrace_dir = ".paktrace"
paktrace_file_ext = ".txt"
default_base = "common"
pak_config_base = "pak"
pak_config_ext = ".ini"
game_profile_dir = "game"
game_profile_ext = ".ini"
map_profile_dir = "map"
map_profile_ext = ".ini"
sloth_profile_dir = "sloth"
sloth_profile_ext = ".sloth"
slothdir_profile_dir = "slothdir"
slothdir_profile_ext = ".slothdir"
file_profile_dir = "file"
file_profile_ext = ".toml"
stage_action_list_ext = ".txt"
ignore_list_base = "ignore"
ignore_list_ext = ".txt"
build_prefix = "build"
test_prefix = "test"
pak_prefix = "pkg"
