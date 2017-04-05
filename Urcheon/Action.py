#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

from Urcheon import Default
from Urcheon import FileSystem
from Urcheon import MapCompiler
from Urcheon import Repository
from Urcheon import Texset
from Urcheon import Ui
from Urcheon import Pak
from Urcheon import Bsp
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


class List():
	def __init__(self, source_dir, stage, game_name=None, disabled_action_list=[]):
		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.requireKey("game")

		self.source_dir = source_dir
		action_list_file_name = stage + Default.stage_action_list_ext
		self.action_list_file_path = os.path.join(Default.pakinfo_dir, action_list_file_name)
		self.action_list_path = os.path.join(self.source_dir, self.action_list_file_path)

		self.inspector = Repository.Inspector(source_dir, game_name, stage, disabled_action_list=disabled_action_list)
		self.active_action_dict = OrderedDict()
		self.disabled_action_dict = OrderedDict()
		self.computed_active_action_dict = OrderedDict()
		self.computed_disabled_action_dict = OrderedDict()

		# I want lines printed in this order
		for action_name in self.inspector.action_description_dict.keys():
			self.active_action_dict[action_name] = []
			self.disabled_action_dict[action_name] = []
			self.computed_active_action_dict[action_name] = []
			self.computed_disabled_action_dict[action_name] = []

	def readActions(self):
		if os.path.isfile(self.action_list_path):
			action_list_file = open(self.action_list_path, "r")
			line_list = [line.strip() for line in action_list_file]
			action_list_file.close()

			action_line_pattern = re.compile(r"^[ \t]*(?P<action_name>[^ \t]*)[ \t]*(?P<file_path>.*)$")
			quoted_path_pattern = re.compile(r"^\"(?P<file_path>.*)\"[ \t]*$")
			disabled_action_pattern = re.compile(r"^#[ \t]*(?P<action_name>.*)$")

			for line in line_list:
				line_match = action_line_pattern.match(line)
				if line_match:
					action_name = line_match.group("action_name")
					file_path = line_match.group("file_path")

					file_match = quoted_path_pattern.match(file_path)
					if file_match:
						file_path = file_match.group("file_path")

				disabled_action_match = disabled_action_pattern.match(action_name)
				if disabled_action_match:
					disabled_action = disabled_action_match.group("action_name")
					Ui.print(file_path + ": Known rule, will not " + disabled_action + " (disabled action).")
					self.disabled_action_dict[disabled_action].append(file_path)
				else:
					if action_name == "":
						# empty line
						continue

					file_fullpath = os.path.realpath(os.path.join(self.source_dir, file_path))
					if os.path.isfile(file_fullpath):
						Ui.print(file_path + ": Known rule, will " + self.inspector.action_description_dict[action_name] + " (predefined action).")
						self.active_action_dict[action_name].append(file_path)
					else:
						Ui.print(file_path + ": Known rule, will not " + self.inspector.action_description_dict[action_name] + " (missing file).")
						self.computed_disabled_action_dict[action_name].append(file_path)

		else:
			Ui.verbose("List not found: " + self.action_list_file_path)

	def computeActions(self, file_list):
		for file_path in file_list:
			file_path = os.path.normpath(file_path)
			unknown_file_path = True
			logging.debug("active actions: " + str(self.active_action_dict))
			logging.debug("inactive actions:" + str(self.disabled_action_dict))
			for read_action in self.active_action_dict.keys():
				if file_path in self.active_action_dict[read_action]:
					Ui.print(file_path + ": Known file, will " + self.inspector.action_description_dict[read_action] + ".")
					self.computed_active_action_dict[read_action].append(file_path)
					unknown_file_path = False
				elif file_path in self.disabled_action_dict[read_action]:
					Ui.print(file_path + ": Disabled known file, will ignore it.")
					self.computed_disabled_action_dict[read_action].append(file_path)
					unknown_file_path = False
			if unknown_file_path:
				computed_action = self.inspector.inspect(file_path)
				self.computed_active_action_dict[computed_action].append(file_path)

		self.active_action_dict = self.computed_active_action_dict
		self.active_inaction_dict = self.computed_disabled_action_dict

	def writeActions(self):
		pak_config_subdir = os.path.dirname(self.action_list_path)
		if os.path.isdir(pak_config_subdir):
			logging.debug("found pakinfo subdir: " +  pak_config_subdir)
		else:
			logging.debug("create pakinfo subdir: " + pak_config_subdir)
			os.makedirs(pak_config_subdir, exist_ok=True)

		action_list_file = open(self.action_list_path, "w")
		for action in self.active_action_dict.keys():
			for file_path in sorted(self.active_action_dict[action]):
				line = action + " " + file_path
				action_list_file.write(line + "\n")
		for action in self.computed_disabled_action_dict.keys():
			for file_path in sorted(self.disabled_action_dict[action]):
				line = "#" + action + " " + file_path
				action_list_file.write(line + "\n")
		action_list_file.close()

	def updateActions(self, action_list):
		self.readActions()

		file_tree = Repository.Tree(self.source_dir, game_name=self.game_name)
		file_list = file_tree.listFiles()
		self.computeActions(file_list)

		self.writeActions()


# I want actions printed and executed in this order
def list():
	action_list = [
		Copy,
		ConvertJpg,
		ConvertPng,
		ConvertCrn,
		ConvertNormalCrn,
		ConvertLossyWebp,
		ConvertLosslessWebp,
		ConvertVorbis,
		ConvertOpus,
		CompileIqm,
		PrevRun,
		SlothRun,
		CopyBsp,
		MergeBsp,
		CompileBsp,
		Keep,
		Ignore,
	]
	return action_list


class Action():
	keyword = "dumb"
	description = "dumb action"
	parallel = True

	# TODO: set something else in verbose mode
	subprocess_stdout = subprocess.DEVNULL
	subprocess_stderr = subprocess.DEVNULL

	def __init__(self, source_dir, build_dir, file_path, stage, game_name=None, map_profile=None, is_nested=False):
		self.body = []
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.file_path = file_path
		self.game_name = game_name
		self.stage = stage
		self.map_profile = map_profile
		self.is_nested = is_nested
		self.paktrace = Repository.Paktrace(self.build_dir)

	def run(self):
		Ui.print("Dumb action: " + self.file_path)
		return getProducedUnitList()

	def getFileNewName(self):
		# must be overriden in sub class
		# some actions rely on this one (keep, copy, copy_bsp)
		return self.file_path

	def getSourcePath(self):
		return os.path.join(self.source_dir, self.file_path)

	def getTargetPath(self):
		return os.path.join(self.build_dir, self.getFileNewName())

	def getStatReference(self):
		return self.getSourcePath()
		
	def getBody(self):
		head = self.getFileNewName()

		if head not in self.body:
			# head is always part of body
			self.body += [ head ]

		return self.body

	def getProducedUnitList(self):
		head = self.getFileNewName()
		body = self.getBody()

		if body:
			# always write paktrace, even if head is the only body part because
			# the prepare stage clean-up needs to track all produced files
			# except in nested build of course since they are already tracked
			if not self.is_nested:
				head = self.getFileNewName()
				self.paktrace.write(head, body)

		unit = {
			"head": head,
			"body": body
		}

		return [ unit ]


	def getOldProducedUnitList(self):
		head = self.getFileNewName()

		# we are reusing already built files, reuse body
		body = self.paktrace.read(head)
		
		unit = {
			"head": head,
			"body": body
		}

		return [ unit ]

	def getExt(self):
		return os.path.splitext(self.file_path)[1][len(os.path.extsep):].lower()
	
	def isDifferent(self):
		source_path = self.getStatReference()
		build_path = self.getTargetPath()
		return FileSystem.isDifferent(build_path, source_path)

	def switchExtension(self, extension):
		return os.path.splitext(self.file_path)[0] + os.path.extsep + extension

	def createSubdirs(self):
		build_subdir = os.path.dirname(self.getTargetPath())
		if os.path.isdir(build_subdir):
			logging.debug("found build subdir: " +  build_subdir)
		else:
			logging.debug("create build subdir: " + build_subdir)
			os.makedirs(build_subdir, exist_ok=True)

	def setTimeStamp(self):
		unit_list = self.getProducedUnitList()
		for unit in unit_list:
			body = unit["body"]
			for produced_file in body:
				produced_path = os.path.join(self.build_dir, produced_file)
				if os.path.isfile(produced_path):
					reference_path = self.getStatReference()
					logging.debug("setting stat from “" + reference_path + "”: " + produced_path)
					shutil.copystat(reference_path, produced_path)


class Ignore(Action):
	keyword = "ignore"
	description = "ignore file"
	parallel = True

	def run(self):
		Ui.verbose("Ignore: " + self.file_path)
		return self.getProducedUnitList()

	def getProducedUnitList(self):
		return {}


class Keep(Action):
	keyword = "keep"
	description = "keep file"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		Ui.print("Keep: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class Copy(Action):
	keyword = "copy"
	description = "copy file"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		Ui.print("Copy: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertJpg(Action):
	keyword = "convert_jpg"
	description = "convert to jpg format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() in ("jpg", "jpeg"):
			Ui.print("File already in jpg, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to jpg: " + self.file_path)
			subprocess.call(["convert", "-verbose", "-quality", "92", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("jpg")


class ConvertPng(Action):
	keyword = "convert_png"
	description = "convert to png format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "png":
			Ui.print("File already in png, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to png: " + self.file_path)
			subprocess.call(["convert", "-verbose", "-quality", "100", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("png")


class DumbWebp(Action):
	def getFileNewName(self):
		return self.switchExtension("webp")
	

class ConvertLossyWebp(DumbWebp):
	keyword = "convert_lossy_webp"
	description = "convert to lossy webp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "webp":
			Ui.print("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to lossy webp: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "png")
			os.close(transient_handle)
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-q", "95", "-pass", "10", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertLosslessWebp(DumbWebp):
	keyword = "convert_lossless_webp"
	description = "convert to lossless webp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "webp":
			Ui.print("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to lossless webp: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "png")
			os.close(transient_handle)
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["cwebp", "-v", "-lossless", transient_path, "-o", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()


class DumbCrn(Action):
	def getFileNewName(self):
		return self.switchExtension("crn")


# TODO: convertDDS
class ConvertCrn(DumbCrn):
	keyword = "convert_crn"
	description = "convert to crn format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "crn":
			Ui.print("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to crn: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "tga")
			os.close(transient_handle)
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertNormalCrn(DumbCrn):
	keyword = "convert_normalized_crn"
	description = "convert to normalized crn format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "crn":
			Ui.print("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to normalized crn: " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "tga")
			os.close(transient_handle)
			subprocess.call(["convert", "-verbose", source_path, transient_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			subprocess.call(["crunch", "-helperThreads", "1", "-file", transient_path, "-dxn", "-renormalize", "-quality", "255", "-out", build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)
			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertVorbis(Action):
	keyword = "convert_vorbis"
	description = "convert to vorbis format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "ogg":
			Ui.print("File already in vorbis, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to vorbis: " + self.file_path)
			subprocess.call(["ffmpeg", "-acodec", "libvorbis", "-i", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("ogg")


class ConvertOpus(Action):
	keyword = "convert_opus"
	description = "convert to opus format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "opus":
			Ui.print("File already in opus, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to opus: " + self.file_path)
			subprocess.call(["opusenc", source_path, build_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("opus")


class CompileIqm(Action):
	keyword = "compile_iqm"
	description = "compile to iqm format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		if self.getExt() == "iqm":
			Ui.print("File already in iqm, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Compile to iqm: " + self.file_path)
			subprocess.call(["iqm", build_path, source_path], stdout=self.subprocess_stdout, stderr=self.subprocess_stderr)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("iqm")


# it's a prepare stage action only
class PrevRun(Action):
	keyword = "run_prevrun"
	description = "produce previews"
	# must run before SlothRun
	parallel = False

	def run(self):
		source_path = self.getSourcePath()

		self.prevrun = Texset.PrevRun(self.source_dir, source_path, game_name=self.game_name)

		# HACK: never check because multiple files produces on reference
		# we can detect added files, but not removed files yet
		# if not self.isDifferent():
		#	Ui.print("Unmodified file, do nothing: " + self.file_path)
		#	return self.getOldProducedUnitList()

		self.preview_list = self.prevrun.run()

		# it does it itself
		# self.setTimeStamp()

		return self.getProducedUnitList()

	def getProducedUnitList(self):
		unit_list = []
		for head in self.preview_list:
			body = [ head ]
			self.paktrace.write(head, body)

			unit = {
				"head": head,
				"body": body,
			}

			unit_list.append(unit)

		return unit_list


# it's a prepare stage action only
class SlothRun(Action):
	keyword = "run_slothrun"
	description = "produce shader"
	# must run after PrevRun
	parallel = False

	def run(self):
		source_path = self.getSourcePath()

		self.slothrun = Texset.SlothRun(self.source_dir, source_path, game_name=self.game_name)

		# HACK: never check because multiple files produces on reference
		# we can detect added files, but not removed files yet
		# if not self.isDifferent():
		#	Ui.print("Unmodified file, do nothing: " + self.file_path)
		#	return self.getOldProducedUnitList()

		self.slothrun.run()

		self.body = [ self.getFileNewName() ]

		# HACK: we don't need it because we don't rely on it
		# self.setTimeStamp()

		return self.getProducedUnitList()

	def getStatReference(self):
		return self.slothrun.getStatReference()

	def getFileNewName(self):
		return self.slothrun.shader_filename


class DumbTransient(Action):
	def createTransientPath(self):
		build_path = self.getTargetPath()
		self.transient_path = tempfile.mkdtemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "dir")
		self.transient_maps_path = os.path.join(self.transient_path, "maps")
		os.makedirs(self.transient_maps_path, exist_ok=True)

	def buildTransientPath(self, disabled_action_list=[]):
		file_tree = Repository.Tree(self.transient_path, game_name=self.game_name, transient_path=True)
		file_list = file_tree.listFiles()

		action_list = List(self.transient_path, self.stage, game_name=self.game_name, disabled_action_list=disabled_action_list)
		action_list.computeActions(file_list)

		builder = Pak.Builder(self.transient_path, action_list, self.stage, self.build_dir, game_name=self.game_name, is_nested=True, parallel=False)
		# keep track of built files
		produced_unit_list = builder.build()

		self.body = []
		for unit in produced_unit_list:
			self.body.extend(unit["body"])
			
		shutil.rmtree(self.transient_path)


class CopyBsp(DumbTransient):
	keyword = "copy_bsp"
	description = "copy bsp file"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		self.createTransientPath()
		bsp_path = self.getFileNewName()
		bsp_transient_path = os.path.join(self.transient_path, bsp_path)

		Ui.print("Copy bsp: " + self.file_path)
		shutil.copyfile(source_path, bsp_transient_path)
		# TODO: isn't it done in setTimeStamp()?
		shutil.copystat(source_path, bsp_transient_path)

		map_compiler = MapCompiler.Compiler(self.source_dir, game_name=self.game_name, map_profile=self.map_profile)
		map_compiler.compile(bsp_transient_path, self.transient_maps_path, stage_list=["nav", "minimap"])

		self.buildTransientPath(disabled_action_list=["copy_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()

class MergeBsp(DumbTransient):
	keyword = "merge_bsp"
	description = "merge into a bsp file"
	parallel = False

	def run(self):
		# TODO: ensure bsp is already copied/compiled if modifying copied/compiled bsp
		# TODO: this is not yet possible to merge over something built
		# Ui.warning("Bsp file already there, will reuse: " + source_path)

		# TODO if file already there
		# you must ensure compile bsp and copy bsp are made before
		# beware of multithreading

		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		# TODO: remove target before merging, to avoid bugs when merging in place
		# merging in place is not implemented yet

		self.createTransientPath()

		bspdir_path = self.getBspDirName()
		bsp_path = self.getFileNewName()

		Ui.print("Merging to bsp: " + bspdir_path)

		bsp = Bsp.File()
		bsp.readDir(source_path)

		bsp_transient_path = os.path.join(self.transient_path, bsp_path)

		# in the future, we will be able to merge in place
		# built in final place so it's kept between calls for each file
		bsp.writeFile(build_path)

		# copy merged file in transient_path for nested extra actions because when
		# per-file merging will be enabled, merge will be done on final file only
		logging.debug("merge_bsp build path: " + build_path)
		shutil.copyfile(build_path, bsp_transient_path)
		shutil.copystat(source_path, bsp_transient_path)

		map_compiler = MapCompiler.Compiler(self.source_dir, game_name=self.game_name, map_profile=self.map_profile)
		map_compiler.compile(bsp_transient_path, self.transient_maps_path, stage_list=["nav", "minimap"])

		self.buildTransientPath(disabled_action_list=["copy_bsp", "compile_bsp"])

		# lucky unthought workaround: since the produced bsp will receive the date
		# of the original directory when first file is merged,
		# other call fors other files from same bspdir will be ignored
		# in the future we will use packtrace or something like that
		self.setTimeStamp()

		return self.getProducedUnitList()

	def getSourcePath(self):
		return os.path.join(self.source_dir, self.getBspDirName())

	def getBspDirName(self):
		# cut everything after ".bspdir" (including in directory file paths)
		# obviously it does not work in nested bspdir but this case does not exist,
		# so, don't call parent name with "bspdir" string inside
		return self.file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bspdir"

	def getFileNewName(self):
		return self.file_path.split(os.path.extsep + "bspdir")[0] + os.path.extsep + "bsp"


class CompileBsp(DumbTransient):
	keyword = "compile_bsp"
	description = "compile to bsp format"
	parallel = True

	def run(self):
		source_path = self.getSourcePath()
		copy_path = self.getTargetPath()
		build_path = self.getTargetPath()
		bsp_path = self.getFileNewName()
		self.createSubdirs()

		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

		self.createTransientPath()

		Ui.print("Compiling to bsp: " + self.file_path)

		map_compiler = MapCompiler.Compiler(self.source_dir, game_name=self.game_name, map_profile=self.map_profile)
		map_compiler.compile(source_path, self.transient_maps_path)

		self.buildTransientPath(disabled_action_list=["copy_bsp", "compile_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("bsp")
