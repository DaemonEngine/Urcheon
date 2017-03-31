#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Default
from Urcheon import Ui
import logging
import os
import sys


class Fs():
	def __init__(self, source_dir):
		self.file_dict = {}

		profile_dir = os.path.join(Default.share_dir, Default.profile_dir)
		pakinfo_dir = os.path.abspath(os.path.join(source_dir , Default.pakinfo_dir))

		self.walk(profile_dir)
		self.walk(pakinfo_dir)

	def walk(self, dir_path):
		full_dir_path = os.path.abspath(dir_path)
		for dir_name, subdir_name_list, file_name_list in os.walk(full_dir_path):
			rel_dir_path = os.path.relpath(dir_name, full_dir_path)
			for file_name in file_name_list:
				rel_file_path = os.path.normpath(os.path.join(rel_dir_path, file_name))
				full_file_path = os.path.join(dir_name, file_name)
				self.file_dict[rel_file_path] = full_file_path

	def isFile(self, file_path):
		return file_path in self.file_dict.keys()

	def getPath(self, file_path):
		if self.isFile(file_path):
			return self.file_dict[file_path]
		else:
			return None

	def print(self):
		for file_path in self.file_dict.keys():
			print(file_path + " → " + self.file_dict[file_path])
