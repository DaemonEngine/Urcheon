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
import toml
import shutil
import subprocess
import tempfile


class PrevRun():
	def __init__(self, source_dir, preview_profile_path, game_name=None):
		self.source_dir = source_dir
		self.source_dir_fullpath = os.path.realpath(self.source_dir)
		preview_profile_fullpath = os.path.join(self.source_dir_fullpath, preview_profile_path)

		self.profile_fs = Profile.Fs(self.source_dir)
		self.prevrun_dict = {}

		if game_name:
			self.game_name = game_name
		else:
			# not required
			pak_config = Repository.Config(self.source_dir)
			self.game_name = pak_config.requireKey("game")

		self.read(preview_profile_path, real_path = True)

		logging.debug("reading preview profile file: " + preview_profile_fullpath)
		preview_profile_file = open(preview_profile_fullpath, "r")
		prevrun_dict = toml.load(preview_profile_file)
		preview_profile_file.close()

		if "dir" not in self.prevrun_dict.keys():
			Ui.error("missing config section: dir")

		if "source" not in self.prevrun_dict["dir"].keys():
			Ui.error("missing “dir” key: dir")

		self.source_dir_name = self.prevrun_dict["dir"]["source"]
		self.source_dir_fullpath = os.path.realpath(os.path.join(self.source_dir, self.source_dir_name))

		if "preview" not in self.prevrun_dict["dir"].keys():
			Ui.error("missing “dir” key: preview")

		self.preview_dir_name = self.prevrun_dict["dir"]["preview"]
		self.preview_dir_fullpath = os.path.realpath(os.path.join(self.source_dir, self.preview_dir_name))

		if "suffix" not in self.prevrun_dict.keys():
			Ui.error("missing config section: suffix")

		if "source" not in self.prevrun_dict["suffix"].keys():
			Ui.error("missing “suffix” key: source")

		self.source_suf = self.prevrun_dict["suffix"]["source"]

		if "preview" not in self.prevrun_dict["suffix"].keys():
			Ui.error("missing “suffix” key: preview")

		self.preview_suf = self.prevrun_dict["suffix"]["preview"]


	def run(self):
		source_list = self.walk()
		
		preview_list = []
		for preview_source_name in source_list:
			preview_list.append(self.convert(preview_source_name))

		return preview_list


	def read(self, prevrun_profile, real_path=False):
		if not real_path:
			prevrun_profile_name = os.path.join(Default.prevrun_profile_dir, prevrun_profile + Default.prevrun_profile_ext)
			prevrun_profile_fullpath = self.profile_fs.getPath(prevrun_profile_name)
		else:
			prevrun_profile_fullpath = os.path.realpath(os.path.join(self.source_dir, prevrun_profile))

		if not os.path.isfile(prevrun_profile_fullpath):
			Ui.error("prevrun profile file not found: " + prevrun_profile_fullpath)

		logging.debug("reading prevrun profile file: " + prevrun_profile_fullpath)
		prevrun_profile_file = open(prevrun_profile_fullpath, "r")
		prevrun_dict = toml.load(prevrun_profile_file)
		prevrun_profile_file.close()

		if "_init_" in prevrun_dict.keys():
			logging.debug("found “_init_” section in prevrun profile file: " + prevrun_profile_fullpath)
			if "extend" in prevrun_dict["_init_"].keys():
				parent_prevrun_name = prevrun_dict["_init_"]["extend"]

				if parent_prevrun_name == "@game":
					parent_prevrun_name = self.game_name

				logging.debug("found “extend” instruction in “_init_” section: " + parent_prevrun_name)
				logging.debug("loading parent prevrun profile file")
				self.read(parent_prevrun_name)

			del prevrun_dict["_init_"]

		for section in prevrun_dict.keys():
			# if two section names collide, the child win
			self.prevrun_dict[section] = prevrun_dict[section]


	def print(self):
		logging.debug(str(self.prevrun_dict))
		print(toml.dumps(self.prevrun_dict))


	def walk(self):
		source_list = []

		for dir_name, subdir_name_list, file_name_list in os.walk(self.source_dir_fullpath):
			dir_relpath = os.path.relpath(dir_name, self.source_dir)

			logging.debug("dir_name: " + dir_name + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

			for file_name in file_name_list:
				file_ext = os.path.splitext(file_name)[1]
				if file_ext in [ ".bmp", ".jpg", ".jpeg", ".png", ".tga", ".webp" ]:
					base_name = file_name[:-len(file_ext)]
					if base_name.endswith(self.source_suf):	
						source_path = os.path.normpath(os.path.join(dir_relpath, file_name))
						logging.debug("preview source texture found: " + source_path)

						preview_path = self.getPreviewPath(source_path)
						if preview_path:
							logging.debug("will generate preview: " + preview_path)
							source_list.append(source_path)
						else:
							logging.debug("will reuse source as preview")

			return source_list


	def getPreviewPath(self, source_path):
		file_ext = os.path.splitext(source_path)[1]
		base_name = os.path.basename(source_path[:-len(file_ext)])
		preview_name = base_name[:-len(self.source_suf)] + self.preview_suf + os.path.extsep + "jpg"
		
		preview_path = os.path.normpath(os.path.join(self.preview_dir_name, preview_name))

		if preview_path == source_path:
			return None
		else:
			return preview_path


	def convert(self, source_path):
		preview_path = self.getPreviewPath(source_path)

		if not preview_path:
			logging.debug("will reuse itself as preview for: " + source_path)
			return

		preview_fullpath = os.path.realpath(os.path.join(self.source_dir, preview_path))
		source_fullpath = os.path.realpath(os.path.join(self.source_dir, source_path))

		if FileSystem.isSame(preview_fullpath, source_fullpath):
			Ui.print("Unmodified file, do nothing: " + source_path)
			return preview_path

		command_list = [ "convert" ]
		command_list += [ source_fullpath ]
		command_list += [ "-quality", "75", "-background", "magenta", "-alpha", "remove", "-alpha", "off", "-resize", "256x256!>"]
		command_list += [ preview_fullpath ]

		Ui.print("Generate preview: " + source_path)

		logging.debug("convert command line: " + str(command_list))

		# TODO: set something else in verbose mode
		subprocess_stdout = subprocess.DEVNULL
		subprocess_stderr = subprocess.DEVNULL
		subprocess.call(command_list, stdout=subprocess_stdout, stderr=subprocess_stderr)

		shutil.copystat(source_fullpath, preview_fullpath)

		return preview_path


class SlothRun():
	def __init__(self, source_dir, slothrun_file_path, game_name=None):
		self.source_dir = source_dir
		self.slothrun_file_path = os.path.normpath(os.path.relpath(slothrun_file_path, self.source_dir))

		self.profile_fs = Profile.Fs(self.source_dir)
		self.slothrun_dict = {}

		if game_name:
			self.game_name = game_name
		else:
			pak_config = Repository.Config(self.source_dir)
			self.game_name = pak_config.requireKey("game")

		self.read(self.slothrun_file_path, real_path=True)

		self.texture_source_dir_list = None

		if "dir" not in self.slothrun_dict.keys():
			Ui.error("missing slothrun section: dir")

		if "source" not in self.slothrun_dict["dir"].keys():
			Ui.error("missing key in “dir” slothrun section: source")

		texture_source_dir_key = self.slothrun_dict["dir"]["source"]

		if not isinstance(texture_source_dir_key, list):
			# value must always be a list, if there is only one string, put it in list
			self.texture_source_dir_list = [ texture_source_dir_key ]
		else:
			# TODO: missing directory
			self.texture_source_dir_list = texture_source_dir_key

		self.sloth_config = None

		if "sloth" in self.slothrun_dict.keys():
			if "config" in self.slothrun_dict["sloth"].keys():
				self.sloth_config = self.slothrun_dict["sloth"]["config"]

		self.shader_filename = None
		self.shader_namespace = None
		self.shader_header = None

		if "shader" not in self.slothrun_dict.keys():
			Ui.error("missing slothrun section: shader")

		if "filename" not in self.slothrun_dict["shader"].keys():
			Ui.error("missing key in “shader” slothrun section: filename")

		self.shader_filename = self.slothrun_dict["shader"]["filename"]

		if "header" in self.slothrun_dict["shader"].keys():
			self.shader_header = self.slothrun_dict["shader"]["header"]

		if "namespace" not in self.slothrun_dict["shader"].keys():
			Ui.error("missing key in “shader” slothrun section: namespace")

		self.shader_namespace = self.slothrun_dict["shader"]["namespace"]

		logging.debug("found slothrun directores: " + str(self.texture_source_dir_list))

		default_texture_suffix_dict = {
			"normal": "_n",
			"diffuse": "_d",
			"height": "_h",
			"specular": "_s",
			"addition": "_a",
			"preview": "_p",
		}

		self.texture_suffix_dict = {}
		for suffix in default_texture_suffix_dict.keys():
			if suffix in self.slothrun_dict["texture"].keys():
				self.texture_suffix_dict[suffix] = self.slothrun_dict["texture"][suffix]
			else:
				self.texture_suffix_dict[suffix] = default_texture_suffix_dict[suffix]


	def run(self):
		sloth_list = self.walk()
		logging.debug("sloth list: " + str(sloth_list))
		self.sloth()


	def read(self, slothrun_profile, real_path=False):
		if not real_path:
			slothrun_profile_name = os.path.join(Default.slothrun_profile_dir, slothrun_profile + Default.slothrun_profile_ext)
			slothrun_profile_fullpath = self.profile_fs.getPath(slothrun_profile_name)
		else:
			slothrun_profile_fullpath = os.path.realpath(os.path.join(self.source_dir, slothrun_profile))

		if not os.path.isfile(slothrun_profile_fullpath):
			Ui.error("slothrun profile file not found: " + slothrun_profile_fullpath)

		logging.debug("reading slothrun profile file: " + slothrun_profile_fullpath)
		slothrun_profile_file = open(slothrun_profile_fullpath, "r")
		slothrun_dict = toml.load(slothrun_profile_file)
		slothrun_profile_file.close()

		if "_init_" in slothrun_dict.keys():
			logging.debug("found “_init_” section in slothrun profile file: " + slothrun_profile_fullpath)
			if "extend" in slothrun_dict["_init_"].keys():
				parent_slothrun_name = slothrun_dict["_init_"]["extend"]

				if parent_slothrun_name == "@game":
					parent_slothrun_name = self.game_name

				logging.debug("found “extend” instruction in “_init_” section: " + parent_slothrun_name)
				logging.debug("loading parent slothrun profile file")
				self.read(parent_slothrun_name)

			del slothrun_dict["_init_"]

		for section in slothrun_dict.keys():
			# if two section names collide, the child win
			self.slothrun_dict[section] = slothrun_dict[section]


	def print(self):
		logging.debug(str(self.slothrun_dict))
		print(toml.dumps(self.slothrun_dict))


	def walk(self):
		for texture_source_dir in self.texture_source_dir_list:
			sloth_list = []

			for dir_name, subdir_name_list, file_name_list in os.walk(texture_source_dir):
				dir_relpath = os.path.relpath(dir_name, self.source_dir)

				logging.debug("dir_name: " + dir_name + ", subdir_name_list: " + str(subdir_name_list) + ", file_name_list: " + str(file_name_list))

				for file_name in file_name_list:
					file_ext = os.path.splitext(file_name)[1]

					if file_ext == Default.sloth_profile_ext:
						sloth_name = os.path.normpath(os.path.join(dir_relpath, file_name))
						logging.debug("sloth file found: " + sloth_name)
						sloth_list.append(sloth_name)

			return sloth_list


	def getStatReference(self):
		sourcedir_file_list = []
		for file_path in [ self.slothrun_file_path ] + self.sloth_list + self.preview_source_list:
			full_path = os.path.realpath(os.path.join(self.source_dir, file_path))
			sourcedir_file_list.append(full_path)

		# TODO: check also slothrun and sloth files in pakinfo and profiles directories
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
		shader_path = os.path.join(self.source_dir, self.shader_filename)
		shader_fullpath = os.path.realpath(shader_path)

		# HACK: never check because multiple files produces on reference
		# we can detect added files, but not removed files yet
		# if FileSystem.isSame(shader_fullpath, file_reference):
		#	logging.debug("unmodified slothrun, skipping sloth generation")
		#	return

		command_list = [ "sloth.py" ]

		if self.sloth_config:
			sloth_profile_name = os.path.join(Default.sloth_profile_dir, self.sloth_config + Default.sloth_profile_ext)
			sloth_profile_path = self.profile_fs.getPath(sloth_profile_name)
			if sloth_profile_path:
				command_list += [ "-f", sloth_profile_path ]

		if "diffuse" in self.texture_suffix_dict.keys():
			command_list += [ "--diff", self.texture_suffix_dict["diffuse"] ]

		if "normal" in self.texture_suffix_dict.keys():
			command_list += [ "--normal", self.texture_suffix_dict["normal"] ]

		if "height" in self.texture_suffix_dict.keys():
			command_list += [ "--height", self.texture_suffix_dict["height"] ]

		if "specular" in self.texture_suffix_dict.keys():
			command_list += [ "--spec", self.texture_suffix_dict["specular"] ]

		if "preview" in self.texture_suffix_dict.keys():
			command_list += [ "--prev", self.texture_suffix_dict["preview"] ]

		sloth_header_file = None
		if self.shader_header:
			header_handle, sloth_header_file = tempfile.mkstemp(suffix="sloth_header" + os.path.extsep + "txt")
			os.write(header_handle, str.encode(self.shader_header))
			os.close(header_handle)

			# TODO: write file

			command_list += [ "--header", sloth_header_file ]

		command_list += [ "--root", self.shader_namespace ]

		command_list += [ "--out", shader_fullpath ]

		for texture_source_dir in self.texture_source_dir_list:
			command_list += [ os.path.realpath(os.path.join(self.source_dir, texture_source_dir)) ]

		logging.debug("sloth command line: " + str(" ".join(command_list)))

		Ui.print("Sloth shader: " + self.slothrun_file_path)

		# TODO: set something else in verbose mode
		subprocess_stdout = subprocess.DEVNULL
		subprocess.call(command_list, stdout=subprocess_stdout)

		if sloth_header_file:
			os.remove(sloth_header_file)
