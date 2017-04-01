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
from collections import OrderedDict
import logging
import os
import pytoml
import shutil
import subprocess
import tempfile

class Slothdir():
	def __init__(self, source_dir, slothdir_file_path, game_name=None):
		self.source_dir = source_dir
		self.slothdir_file_path = os.path.normpath(slothdir_file_path)
		self.profile_fs = Profile.Fs(self.source_dir)
		self.slothdir_dict = OrderedDict()

		self.sloth_list = []
		self.diffuse_list = []
		self.preview_list = []

		self.base_path = None
		self.dir_path = None
		self.shader_name = None

		if game_name:
			self.game_name = game_name
		else:
			# not required
			pak_config = Repository.Config(self.source_dir)
			self.game_name = pak_config.getKey("game")

		if self.slothdir_file_path:
			self.read(self.slothdir_file_path, real_path=True)
			self.base_path = self.slothdir_file_path[:-len(os.path.extsep + Default.slothdir_profile_ext)]
			self.dir_path = self.base_path
			if "dir" in self.slothdir_dict["suffix"]:
				self.base_path = self.base_path[:-len(self.slothdir_dict["suffix"]["dir"])]

			if not os.path.isdir(self.dir_path):
				Ui.error("missing directory: " + self.dir_path)

			logging.debug("found slothdir directory: " + self.dir_path)

		default_suffix_dict = {
			"dir": "_src",
			"normal": "_n",
			"diffuse": "_d",
			"height": "_h",
			"specular": "_s",
			"addition": "_a",
			"preview": "_p",
		}

		self.suffix_dict = {}
		for suffix in default_suffix_dict.keys():
			if suffix in self.slothdir_dict["suffix"].keys():
				self.suffix_dict[suffix] = self.slothdir_dict["suffix"][suffix]
			else:
				self.suffix_dict[suffix] = default_suffix_dict[suffix]

		default_shader_dict = {
			"header": None,
			"dir": "scripts",
			"ext": "shader",
		}

		self.shader_dict = {}
		for key in default_shader_dict.keys():
			if key in self.slothdir_dict["shader"].keys():
				self.shader_dict[key] = self.slothdir_dict["shader"][key]
			else:
				self.shader_dict[key] = default_shader_dict[key]

		if self.slothdir_file_path:
			shader_basename = os.path.basename(self.base_path) + os.path.extsep + self.shader_dict["ext"]
			shader_name = os.path.normpath(os.path.join(self.shader_dict["dir"], shader_basename))
			self.shader_name = shader_name

			self.walk()

			logging.debug("sloth list: " + str(self.sloth_list))
			logging.debug("diffuse list: " + str(self.diffuse_list))

	def read(self, slothdir_profile, real_path=False):
		if not real_path:
			slothdir_profile_name = os.path.join(Default.slothdir_profile_dir, slothdir_profile + os.path.extsep + Default.slothdir_profile_ext)
			slothdir_profile_path = self.profile_fs.getPath(slothdir_profile_name)
		else:
			slothdir_profile_path = slothdir_profile
			if not os.path.isfile(slothdir_profile_path):
				Ui.error("slothdir profile file not found: " + slotdir_profile_path)

		logging.debug("reading slothdir profile file: " + slothdir_profile_path)
		slothdir_profile_file = open(slothdir_profile_path, "r")
		slothdir_dict = pytoml.load(slothdir_profile_file)
		slothdir_profile_file.close()

		if "_init_" in slothdir_dict.keys():
			logging.debug("found “_init_” section in slothdir profile file: " + slothdir_profile_path)
			if "extend" in slothdir_dict["_init_"].keys():
				parent_slothdir_name = slothdir_dict["_init_"]["extend"]
				logging.debug("found “extend” instruction in “_init_” section: " + parent_slothdir_name)
				logging.debug("loading parent slothdir profile file")
				self.read(parent_slothdir_name)

			del slothdir_dict["_init_"]

		for section in slothdir_dict.keys():
			# if two section names collide, the child win
			self.slothdir_dict[section] = slothdir_dict[section]


	def print(self):
		logging.debug(str(self.slothdir_dict))
		print(pytoml.dumps(self.slothdir_dict))


	def walk(self):
		diffuse_list = []
		sloth_list = []

		for dir_name, subdir_name_list, file_name_list in os.walk(self.dir_path):
			dir_name = os.path.relpath(dir_name, self.source_dir)

			logging.debug("dir_name: " + str(dir_name) + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

			for file_name in file_name_list:
				file_ext = os.path.splitext(file_name)[1]
				if file_ext in [ ".bmp", ".jpg", ".jpeg", ".png", ".tga", ".webp" ]:
					base_name = file_name[:-len(file_ext)]
					if base_name[-len(self.suffix_dict["diffuse"]):] == self.suffix_dict["diffuse"]:
						diffuse_name = os.path.join(dir_name, file_name)
						logging.debug("diffuse texture found: " + diffuse_name)

						diffuse_name = os.path.join(dir_name, file_name)
						preview_name = self.getPreviewName(diffuse_name)

						diffuse_name = os.path.normpath(diffuse_name)
						preview_name = os.path.normpath(preview_name)

						if preview_name:
							logging.debug("will generate preview: " + preview_name)
							diffuse_list.append(diffuse_name)
						else:
							logging.debug("will reuse diffuse as preview")

				elif file_ext == os.path.extsep + Default.sloth_profile_ext:
					sloth_name = os.path.join(dir_name, file_name)
					logging.debug("sloth file found: " + sloth_name)
					sloth_list.append(sloth_name)

		self.sloth_list = sloth_list
		self.diffuse_list = diffuse_list


	def getForeignPreviewName(self, diffuse_name):
		dir_name = os.path.dirname(diffuse_name)
		slothdir_file_name = dir_name + os.path.extsep + Default.slothdir_profile_ext
		slothdir_file_path = os.path.realpath(os.path.join(self.source_dir, slothdir_file_name))
		if not os.path.isfile(slothdir_file_path):
			Ui.error("slothdir file not found: " + slothdir_file_path)

		slothdir = SlothDir(self.source_dir, slothdir_file_name, game_name=self.game_name)
		preview_name = slothdir.getPreviewName(diffuse_name)
		logging.debug("preview name for “ " + diffuse_name + " ”: " + preview_name)
		return preview_name


	def getPreviewName(self, diffuse_name):
		if not self.slothdir_file_path:
			return self.getForeignPreviewName(diffuse_name)

		file_ext = os.path.splitext(diffuse_name)[1]
		base_name = diffuse_name[:-len(file_ext)]
		preview_name = base_name[:-len(self.suffix_dict["diffuse"])] + self.suffix_dict["preview"] + os.path.extsep + "jpg"

		if preview_name == diffuse_name:
			return None
		else:
			return preview_name


	def preview(self, diffuse_name):
		diffuse_path = os.path.normpath(os.path.join(self.source_dir, diffuse_name))
		diffuse_fullpath = os.path.realpath(diffuse_path)
		preview_name = self.getPreviewName(diffuse_name)

		if not preview_name:
			logging.debug("will reuse diffuse as preview for: " + diffuse_name)
			return

		preview_path = os.path.normpath(os.path.join(self.source_dir, preview_name))
		preview_fullpath = os.path.realpath(preview_path)

		# HACK: never check because multiple files produces on reference
		# we can detect added files, but not removed files yet
		# if FileSystem.isSame(preview_fullpath, diffuse_fullpath):
		#	logging.debug("unmodified diffuse, skipping preview generation")
		#	return

		command_list = [ "convert" ]
		command_list += [ diffuse_fullpath ]
		command_list += [ "-quality", "75", "-background", "magenta", "-alpha", "remove", "-alpha", "off" ]
		command_list += [ preview_fullpath ]

		Ui.print("Generate preview: " + diffuse_path)

		logging.debug("convert command line: " + str(command_list))

		# TODO: set something else in verbose mode
		subprocess_stdout = subprocess.DEVNULL
		subprocess_stderr = subprocess.DEVNULL
		subprocess.call(command_list, stdout=subprocess_stdout, stderr=subprocess_stderr)

		shutil.copystat(diffuse_path, preview_fullpath)

		self.preview_list += [ preview_path ]


	def previewAll(self):
		for diffuse_name in self.diffuse_list:
			self.preview(diffuse_name)


	def getStatReference(self):
		sourcedir_file_list = []
		for file_path in [ self.slothdir_file_path ] + self.sloth_list + self.diffuse_list:
			full_path = os.path.realpath(os.path.join(self.source_dir, file_path))
			sourcedir_file_list.append(full_path)

		# TODO: check also slothdir and sloth files in pakinfo and profiles directories
		file_reference_list = sourcedir_file_list
		file_reference = FileSystem.getNewer(file_reference_list)

		return file_reference


	def setTimeStamp(self):
		shader_path = os.path.join(self.source_dir, self.shader_name)
		shader_fullpath = os.path.realpath(shader_path)

		file_reference = self.getStatReference()
		shutil.copystat(file_reference, shader_fullpath)


	# always sloth after preview generation
	def sloth(self):
		shader_path = os.path.join(self.source_dir, self.shader_name)
		shader_fullpath = os.path.realpath(shader_path)

		# HACK: never check because multiple files produces on reference
		# we can detect added files, but not removed files yet
		# if FileSystem.isSame(shader_fullpath, file_reference):
		#	logging.debug("unmodified slothdir, skipping sloth generation")
		#	return

		command_list = [ "sloth.py" ]

		if self.game_name:
			sloth_profile_name = os.path.join(Default.sloth_profile_dir, self.game_name + os.path.extsep + Default.sloth_profile_ext)
			sloth_profile_path = self.profile_fs.getPath(sloth_profile_name)
			if sloth_profile_path:
				command_list += [ "-f", sloth_profile_path ]

		if "dir" in self.suffix_dict.keys():
			command_list += [ "--strip", self.suffix_dict["dir"] ]

		if "diffuse" in self.suffix_dict.keys():
			command_list += [ "--diff", self.suffix_dict["diffuse"] ]

		if "normal" in self.suffix_dict.keys():
			command_list += [ "--normal", self.suffix_dict["normal"] ]

		if "height" in self.suffix_dict.keys():
			command_list += [ "--height", self.suffix_dict["height"] ]

		if "specular" in self.suffix_dict.keys():
			command_list += [ "--spec", self.suffix_dict["specular"] ]

		if "preview" in self.suffix_dict.keys():
			command_list += [ "--prev", self.suffix_dict["preview"] ]

		sloth_header_file = None
		if "header" in self.shader_dict.keys():
			header_handle, sloth_header_file = tempfile.mkstemp(suffix="sloth_header_" + os.path.basename(self.dir_path) + os.path.extsep + "txt")
			sloth_header_content = self.shader_dict["header"]
			os.write(header_handle, str.encode(sloth_header_content))
			os.close(header_handle)

			# TODO: write file

			command_list += [ "--header", sloth_header_file ]

		command_list += [ "--out", shader_fullpath ]

		dir_fullpath = os.path.abspath(os.path.join(self.source_dir, self.dir_path))
		command_list += [ dir_fullpath ]

		logging.debug("sloth command line: " + str(command_list))

		Ui.print("Sloth shader: " + self.dir_path)

		# TODO: set something else in verbose mode
		subprocess_stdout = subprocess.DEVNULL
		subprocess_stderr = subprocess.DEVNULL
		subprocess.call(command_list, stdout=subprocess_stdout, stderr=subprocess_stderr)

		if sloth_header_file:
			os.remove(sloth_header_file)


	def run(self):
		self.previewAll()
		self.sloth()
