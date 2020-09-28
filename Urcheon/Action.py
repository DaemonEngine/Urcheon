#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

from Urcheon import Default
from Urcheon import FileSystem
from Urcheon import IqmConfig
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
	def __init__(self, source_dir, stage_name, game_name=None, disabled_action_list=[]):
		if not game_name:
			pak_config = Repository.Config(source_dir)
			game_name = pak_config.requireKey("game")

		self.source_dir = source_dir
		self.game_name = game_name
		action_list_file_name = os.path.join(Default.action_list_dir, stage_name + Default.action_list_ext)
		self.action_list_file_path = os.path.join(Default.pakinfo_dir, action_list_file_name)
		self.action_list_path = os.path.join(self.source_dir, self.action_list_file_path)

		self.inspector = Repository.Inspector(source_dir, self.game_name, stage_name, disabled_action_list=disabled_action_list)
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
	# do slow things at first so the thread manager
	# can fill the available slots with quicker things
	# when the slow tasks are not very well
	# multithreaded
	action_list = [
		# even bsp copying can be slow if it triggers minimap
		# and navmesh generation
		CopyBsp,
		CompileBsp,
		# perhaps one day MergeBsp will be run on a copied bsp
		# so it must be called after that
		MergeBsp,
		# those are probably the slowest compression image
		# formats we know
		ConvertKtx,
		ConvertDds,
		ConvertCrn,
		ConvertNormalCrn,
		ConvertLosslessWebp,
		ConvertLossyWebp,
		# sloth needs previews to be done before sloth
		# TODO: be sure Sloth is not called before
		# all previews are generated
		# the prepare stage is currently sequential
		# because of things like that
		PrevRun,
		SlothRun,
		# usually quick
		CompileIqm,
		# can take some time but not blocking
		ConvertVorbis,
		ConvertOpus,
		# quick tasks
		ConvertPng,
		ConvertJpg,
		ConvertBadJpg,
		# very quick tasks
		Copy,
		Keep,
		Ignore,
	]
	return action_list


class Action():
	keyword = "dumb"
	description = "dumb action"
	is_parallel = True
	threaded = False

	def __init__(self, source_dir, build_dir, file_path, stage_name, game_name=None, map_profile=None, thread_count=1, is_parallel=True, is_nested=False):
		self.body = []
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.file_path = file_path
		self.game_name = game_name
		self.stage_name = stage_name
		self.map_profile = map_profile
		self.thread_count = thread_count
		self.is_parallel = is_parallel
		self.is_nested = is_nested
		self.paktrace = Repository.Paktrace(self.source_dir, self.build_dir)

	def isDone(self):
		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return self.getOldProducedUnitList()

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
				self.paktrace.write(self.file_path, head, body)

		unit = {
			"head": head,
			"body": body
		}

		return [ unit ]

	def getOldProducedUnitList(self):
		head = self.getFileNewName()

		# we are reusing already built files, reuse body
		body = self.paktrace.readBody(head)
		
		unit = {
			"head": head,
			"body": body
		}

		return [ unit ]

	def getExt(self):
		return os.path.splitext(self.file_path)[1][len(os.path.extsep):].lower()
	
	def isDifferent(self):
		if not os.path.isfile(self.getTargetPath()):
			return True

		return self.paktrace.isDifferent(self.getFileNewName(), self.getSourceList())

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

	def callProcess(self, command_list):
		if Ui.verbosely:
			subprocess_stdout = None
			subprocess_stderr = None
		else:
			subprocess_stdout = subprocess.DEVNULL
			subprocess_stderr = subprocess.DEVNULL

		if subprocess.call(command_list, stdout=subprocess_stdout, stderr=subprocess_stderr) != 0:
			Ui.error("command failed: '" + "' '".join(command_list) + "'")

	def getSourceList(self):
		return [ self.file_path ]

	def getStatReference(self):
		file_reference_list = []

		for source_path in self.getSourceList():
			file_reference_list.append(os.path.join(self.source_dir, source_path))

		return FileSystem.getNewer(file_reference_list)

class Ignore(Action):
	keyword = "ignore"
	description = "ignore file"

	def isDone(self):
		# trick, the task is done in test stage to bypass the available thread compute
		Ui.verbose("Ignore: " + self.file_path)
		return True

	def run(self):
		# trick, the task is done in test stage to bypass the available thread compute
		return self.getProducedUnitList()

	def getProducedUnitList(self):
		return {}


class Keep(Action):
	keyword = "keep"
	description = "keep file"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		Ui.print("Keep: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class Copy(Action):
	keyword = "copy"
	description = "copy file"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		Ui.print("Copy: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertJpg(Action):
	keyword = "convert_jpg"
	description = "convert to jpg format"

	printable_target_format = "jpg"
	convert_jpg_quality = 92

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() in ("jpg", "jpeg"):
			Ui.print("File already in jpg, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to " + self.printable_target_format + ": " + self.file_path)
			self.callProcess(["convert", "-verbose", "-quality", str(self.convert_jpg_quality), source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("jpg")


class ConvertBadJpg(ConvertJpg):
	keyword = "convert_bad_jpg"
	description = "convert to bad jpg format"

	printable_target_format = "bad jpg"
	convert_jpg_quality = 50


class ConvertPng(Action):
	keyword = "convert_png"
	description = "convert to png format"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "png":
			Ui.print("File already in png, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to png: " + self.file_path)
			self.callProcess(["convert", "-verbose", "-quality", "100", source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("png")


class ConvertLossyWebp(Action):
	threaded = True

	keyword = "convert_lossy_webp"
	description = "convert to lossy webp format"

	printable_target_format = "lossy webp"
	cwebp_extra_args = ["-m", "6", "-q", "95", "-pass", "10"]

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "webp":
			Ui.print("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to " + self.printable_target_format +  ": " + self.file_path)
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "png")
			os.close(transient_handle)
			self.callProcess(["convert", "-verbose", "-strip", source_path, "png:" + transient_path])
			self.callProcess(["cwebp", "-v", "-mt"] + self.cwebp_extra_args + [transient_path, "-o", build_path])
			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("webp")
	

class ConvertLosslessWebp(ConvertLossyWebp):
	keyword = "convert_lossless_webp"
	description = "convert to lossless webp format"

	printable_target_format = "lossless webp"
	cwebp_extra_args = ["-lossless", "-z", "9"]
	

class ConvertCrn(Action):
	threaded = True

	keyword = "convert_crn"
	description = "convert to crn format"

	printable_target_format = "crn"
	crunch_extra_args = []

	file_ext = "crn"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == self.file_ext:
			Ui.print("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to " + self.printable_target_format + ": " + self.file_path)

			# the convert tool from ImageMagick is known to fail to properly convert some jpg files to tga (some of them are produced upside down)
			# see https://bugs.launchpad.net/ubuntu/+source/imagemagick/+bug/1838860
			# we know that convert properly converts those jpg to png if we strip metadata
			# so we can convert them to png to tga before converting them to crn
			# we must strip metadata to be sure the bug is not postponed to the png to tga conversion 
			transient_transient_handle, transient_transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient_transient" + os.path.extsep + "png")
			os.close(transient_transient_handle)
			self.callProcess(["convert", "-verbose", "-strip", source_path, "png:" + transient_transient_path])

			# the crunch tool only supports a small number of formats, and is known to fail on some variants of the format it handles (example: png)
			# See https://github.com/DaemonEngine/crunch/issues/13
			# the tga format produced by the `convert` tool is believed to be a safe input format for crunch
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "tga")
			os.close(transient_handle)
			self.callProcess(["convert", "-verbose", "-strip", transient_transient_path, "tga:" + transient_path])

			self.callProcess(["crunch", "-helperThreads", str(self.thread_count), "-file", transient_path] + self.crunch_extra_args + ["-quality", "255", "-out", build_path])

			if os.path.isfile(transient_transient_path):
				os.remove(transient_transient_path)

			if os.path.isfile(transient_path):
				os.remove(transient_path)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension(self.file_ext)


class ConvertNormalCrn(ConvertCrn):
	keyword = "convert_normalized_crn"
	description = "convert to normalized crn format"

	printable_target_format = "normalized crn"
	crunch_extra_args = ["-dxn", "-renormalize", "-rtopmip"]


class ConvertDds(ConvertCrn):
	keyword = "convert_dds"
	description = "convert to dds format"

	printable_target_format = "dds"

	file_ext = "dds"

class ConvertKtx(ConvertCrn):
	keyword = "convert_ktx"
	description = "convert to ktx format"

	printable_target_format = "ktx"

	file_ext = "ktx"

class ConvertVorbis(Action):
	keyword = "convert_vorbis"
	description = "convert to vorbis format"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "ogg":
			Ui.print("File already in vorbis, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to vorbis: " + self.file_path)
			self.callProcess(["ffmpeg", "-acodec", "libvorbis", "-i", source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("ogg")


class ConvertOpus(Action):
	keyword = "convert_opus"
	description = "convert to opus format"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "opus":
			Ui.print("File already in opus, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.print("Convert to opus: " + self.file_path)
			self.callProcess(["opusenc", source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("opus")


class CompileIqm(Action):
	keyword = "compile_iqm"
	description = "compile to iqm format"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "iqm":
			Ui.print("File already in iqm, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			iqe_command_file = source_path + os.path.extsep + "cfg"
			if os.path.isfile(iqe_command_file):
				iqm_config = IqmConfig.File()
				iqm_config.readFile(iqe_command_file)
				iqm_config.translate(self.source_dir, self.build_dir)

				transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "iqe.cfg")
				os.close(transient_handle)

				iqm_config.writeFile(transient_path)

				Ui.print("Compile to iqm using a command file: " + self.file_path)
				self.callProcess(["iqm", "--cmd", transient_path])
			else:
				Ui.print("Compile to iqm: " + self.file_path)
				self.callProcess(["iqm", build_path, source_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("iqm")

	def getSourceList(self):
		source_list = [ self.file_path ]

		iqe_command_file = self.file_path + os.path.extsep + "cfg"
		if os.path.isfile(iqe_command_file):
			source_list.append(iqe_command_file)

		return source_list


# it's a prepare stage action only
class PrevRun(Action):
	keyword = "run_prevrun"
	description = "produce previews"
	# must run before SlothRun
	is_parallel = False

	def isDone(self):
		# HACK: always consider it's not already done because
		# we can detect added files, but not removed files yet
		return False

	def run(self):
		source_path = self.getSourcePath()

		self.prevrun = Texset.PrevRun(self.source_dir, source_path, game_name=self.game_name)
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
	is_parallel = False

	def isDone(self):
		# HACK: always consider it's not already done because
		# we can detect added files, but not removed files yet
		return False

	def run(self):
		source_path = self.getSourcePath()

		self.slothrun = Texset.SlothRun(self.source_dir, source_path, game_name=self.game_name)
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
		file_tree = Repository.Tree(self.transient_path, game_name=self.game_name, is_nested=True)
		file_list = file_tree.listFiles()

		### TODO: write better code to write dummy pak.conf
		transient_pakinfo_dir = os.path.join(self.transient_path, Default.pakinfo_dir)
		os.mkdir(transient_pakinfo_dir)
		transient_pakinfo_file_path = os.path.join(transient_pakinfo_dir, "pak" + os.path.extsep + "conf")

		transient_pakinfo_file = open(transient_pakinfo_file_path, 'wt', encoding='utf-8')
		transient_pakinfo_file.write("[config]")
		transient_pakinfo_file.close()

		builder = Pak.Builder(self.transient_path, self.stage_name, self.build_dir, game_name=self.game_name, disabled_action_list=disabled_action_list, is_nested=True, is_parallel=False)
		# keep track of built files
		produced_unit_list = builder.build()

		self.body = []
		for unit in produced_unit_list:
			self.body.extend(unit["body"])

		shutil.rmtree(self.transient_path)


class CopyBsp(DumbTransient):
	keyword = "copy_bsp"
	description = "copy bsp file"

	def run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		self.createTransientPath()
		bsp_path = self.getFileNewName()
		bsp_transient_path = os.path.join(self.transient_path, bsp_path)

		Ui.print("Copy bsp: " + self.file_path)
		shutil.copyfile(source_path, bsp_transient_path)
		# TODO: isn't it done in setTimeStamp()?
		shutil.copystat(source_path, bsp_transient_path)

		map_compiler = MapCompiler.Compiler(self.source_dir, game_name=self.game_name, map_profile=self.map_profile, is_parallel=self.is_parallel)
		map_compiler.compile(bsp_transient_path, self.transient_maps_path, stage_done=["bsp", "vis", "light"])

		self.buildTransientPath(disabled_action_list=["copy_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()


class MergeBsp(DumbTransient):
	keyword = "merge_bsp"
	description = "merge into a bsp file"
	is_parallel = False

	def run(self):
		# HACK: it's called on all the files but called for every file
		# that's why this action is not callable in parallel:
		# once the first run is done for one file, it's done
		# for others files too

		# TODO: ensure bsp is already copied/compiled if modifying copied/compiled bsp
		# TODO: this is not yet possible to merge over something built
		# Ui.warning("Bsp file already there, will reuse: " + source_path)

		# TODO if file already there
		# you must ensure compile bsp and copy bsp are made before
		# beware of multithreading

		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		# TODO: remove target before merging, to avoid bugs when merging in place
		# merging in place is not implemented yet

		self.createTransientPath()

		bspdir_path = self.getBspDirName()
		bsp_path = self.getFileNewName()

		Ui.print("Merging to bsp: " + bspdir_path)

		bsp = Bsp.Bsp()
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
		map_compiler.compile(bsp_transient_path, self.transient_maps_path, stage_done=["bsp", "vis", "light"])

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

	def run(self):
		source_path = self.getSourcePath()
		copy_path = self.getTargetPath()
		build_path = self.getTargetPath()
		bsp_path = self.getFileNewName()
		self.createSubdirs()

		self.createTransientPath()

		Ui.print("Compiling to bsp: " + self.file_path)

		map_compiler = MapCompiler.Compiler(self.source_dir, game_name=self.game_name, map_profile=self.map_profile)
		map_compiler.compile(source_path, self.transient_maps_path)

		self.buildTransientPath(disabled_action_list=["copy_bsp", "compile_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("bsp")
