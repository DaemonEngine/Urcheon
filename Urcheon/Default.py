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
pak_config_base = "pak"
pak_config_ext = ".conf"
paktrace_dir = ".paktrace"
paktrace_file_ext = ".txt"
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
stage_action_list_ext = ".txt"
ignore_list_base = "ignore"
ignore_list_ext = ".txt"
build_prefix = "build"
test_prefix = "test"
pak_prefix = "pkg"
