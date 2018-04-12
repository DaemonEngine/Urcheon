#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

import os
import re

class File():
	def __init__(self):
		self.line_list = None
		self.output_pattern = re.compile(r"^[ \t]*output[ \t]*(?P<output>.*)$")
		self.scene_pattern = re.compile(r"^[ \t]*scene[ \t]*(?P<scene>.*)$")

	def readFile(self, file_name):
		config_file = open(file_name, "r")

		self.line_list = config_file.readlines()
		config_file.close()

	def translate(self, scene_dir, output_dir):
		translated_line_list = []

		for line in self.line_list:
			match = self.scene_pattern.match(line)
			if match:
				line = "scene " + os.path.join(scene_dir, match.group("scene"))
			match = self.output_pattern.match(line)
			if match:
				line = "output " + os.path.join(output_dir, match.group("output"))
			translated_line_list.append(line)

		self.line_list = translated_line_list

	def writeFile(self, file_name):
		config_string = "\n".join(self.line_list)
		config_file = open(file_name, "w")
		config_file.write(config_string)
		config_file.close()
