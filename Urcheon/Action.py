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
from PIL import Image


# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing
# TODO: comment out missing files


class List():
	def __init__(self, source_tree, stage_name, disabled_action_list=[]):
		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.game_name = source_tree.game_name

		config_dir = Default.getPakConfigDir(self.source_dir)

		action_list_file_name = os.path.join(Default.action_list_dir, stage_name + Default.action_list_ext)
		self.action_list_file_path = os.path.join(config_dir, action_list_file_name)
		self.action_list_path = os.path.join(self.source_dir, self.action_list_file_path)

		self.inspector = Repository.Inspector(self.source_tree, stage_name, disabled_action_list=disabled_action_list)
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

	def readActions(self, action_list=None):
		if not action_list:
			if os.path.isfile(self.action_list_path):
				action_list_file = open(self.action_list_path, "r")
				line_list = [line.strip() for line in action_list_file]
				action_list_file.close()
			else:
				Ui.verbose("List not found: " + self.action_list_file_path)
				return

			action_line_pattern = re.compile(r"^[ \t]*(?P<action_name>[^ \t]*)[ \t]*(?P<file_path>.*)$")
			quoted_path_pattern = re.compile(r"^\"(?P<file_path>.*)\"[ \t]*$")
			disabled_action_pattern = re.compile(r"^#[ \t]*(?P<action_name>.*)$")

			action_list = []

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
					else:
						action_dict = {
							"action_name": action_name,
							"file_path": file_path,
						}

						action_list.append(action_dict)

		# This is not an else.
		if action_list:
			for action_dict in action_list:
				action_name = action_dict["action_name"]
				file_path = action_dict["file_path"]

				file_fullpath = os.path.realpath(os.path.join(self.source_dir, file_path))
				if os.path.isfile(file_fullpath):
					Ui.print(file_path + ": Known rule, will " + self.inspector.action_description_dict[action_name] + " (predefined action).")
					self.active_action_dict[action_name].append(file_path)
				else:
					Ui.print(file_path + ": Known rule, will not " + self.inspector.action_description_dict[action_name] + " (missing file).")
					self.computed_disabled_action_dict[action_name].append(file_path)

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
			logging.debug("found package configuration subdirectory: " +  pak_config_subdir)
		else:
			logging.debug("create package configuration subdirectory: " + pak_config_subdir)
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

		file_list = self.source_tree.listFiles()
		self.computeActions(file_list)

		self.writeActions()


# I want actions printed and executed in this order
def list():
	# do slow things at first so the thread manager
	# can fill the available slots with quicker things
	# when the slow tasks are not very well
	# multithreaded
	return [
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
		Delete,
	]


class Action():
	# TODO: rename keyword to name
	keyword = "dumb"
	description = "dumb action"
	is_parallel = True
	threaded = False

	cwebp_base_command = ["cwebp", "-v", "-mt"]

	def __init__(self, source_tree, build_dir, file_path, stage_name, map_profile=None, action_list=None, thread_count=1, is_parallel=True, is_nested=False):
		self.body = []
		self.source_tree = source_tree
		self.source_dir = source_tree.dir
		self.game_name = source_tree.game_name
		self.build_dir = build_dir
		self.file_path = file_path
		self.stage_name = stage_name
		self.map_profile = map_profile
		self.action_list = action_list
		self.thread_count = thread_count
		self.is_parallel = is_parallel
		self.is_nested = is_nested
		self.paktrace = Repository.Paktrace(self.source_tree, self.build_dir)

	def isDone(self):
		if not self.isDifferent():
			Ui.print("Unmodified file, do nothing: " + self.file_path)
			return True
		else:
			return False

	# TODO: Maybe tell developer when nothing is done because he
	# has to call both run() and symlink() to handle all the uses cases.
	def run(self):
		full_path = os.path.join(self.source_dir, self.file_path)

		if os.path.islink(full_path):
			return []
		else:
			return self.effective_run()

	def symlink(self):
		full_path = os.path.join(self.source_dir, self.file_path)

		# It is not supported at prepare time,
		# The symlink already exists in source since it's source.
		# TODO: When we will be able to prepare to another directory
		# we would have to enable for this use case.
		if self.stage_name == "prepare":
			return []

		if os.path.islink(full_path):
			return self.effective_symlink()
		else:
			return []

	def effective_run(self):
		Ui.laconic("Dumb action: " + self.file_path)
		return getProducedUnitList()

	def effective_symlink(self):
		if not self.action_list:
			Ui.error("Doing symbolic links with Action class requires to pass action_list on initialization")

		full_path = os.path.join(self.source_dir, self.file_path)
		real_path = os.path.realpath(full_path)

		found_target = False
		for action_type in list():
			for target_file_path in self.action_list.active_action_dict[action_type.keyword]:
				target_full_path = os.path.join(self.source_dir, target_file_path)

				if self.file_path == target_file_path:
					continue

				target_real_path = os.path.realpath(target_full_path)

				if real_path == target_real_path:
					found_target = True

					target_action = action_type(self.source_tree, self.build_dir, target_file_path, self.stage_name)

					if not target_action.isDone():
						Ui.error("Target symbolic link for " + self.file_path + " cannot be done because " + target_file_path + " isn't built yet.")

					built_target_file_path = target_action.getFileNewName()
					built_target_full_path = os.path.join(self.build_dir, built_target_file_path)
					built_target_real_path = os.path.realpath(built_target_full_path)

					# Get the new name for the source file with the action of the target file.
					file_action = action_type(self.source_tree, self.build_dir, self.file_path, self.stage_name)
					built_file_path = file_action.getFileNewName()
					built_full_path = os.path.join(self.build_dir, built_file_path)

					# The existing file must be deleted before calling realpath
					# otherwise realpath may return path to a target path
					# if the symbolic link is already created.
					if os.path.exists(built_full_path):
						os.remove(built_full_path)

					built_real_path = os.path.realpath(built_full_path)

					built_dir = os.path.dirname(built_real_path)
					built_target_relative_path = os.path.relpath(built_target_real_path, start=built_dir)

					# Do not use built_real_path or the symbolic link
					# will be written to itself.
					Ui.laconic("Writing " + built_file_path + " symbolic link")

					symlink_parent_dir = os.path.dirname(built_full_path)
					os.makedirs(symlink_parent_dir, exist_ok=True)

					os.symlink(built_target_relative_path, built_full_path)

					logging.debug("setting stat from “" + real_path + "”: " + built_target_real_path)
					shutil.copystat(real_path, built_full_path)

					return self.getProducedUnitList(head=built_file_path)

		if not found_target:
			Ui.error("Target " + target_file_path + " not found for " + file_path)

	def getFileNewName(self):
		# must be overriden in sub class
		# some actions rely on this one (keep, copy, copy_bsp)
		return self.file_path

	def getSourcePath(self):
		return os.path.join(self.source_dir, self.file_path)

	def getTargetPath(self):
		return os.path.join(self.build_dir, self.getFileNewName())

	def getBody(self, head):
		if head not in self.body:
			# head is always part of body
			self.body += [ head ]

		return self.body

	def getProducedUnitList(self, head=None, write=True):
		if not head:
			head = self.getFileNewName()

		body = self.getBody(head)

		# If action is not ignore nor delete,
		# always write paktrace, even if head is the only body part because
		# the prepare stage clean-up needs to track all produced files
		# except in nested build of course since they are already tracked.
		if not self.is_nested:
			head = self.getFileNewName()
			if write:
				self.paktrace.write(self.file_path, head, body)

		unit = {
			"head": head,
			"body": body,
			"action": self.keyword
		}

		return [ unit ]

	def getOldProducedUnitList(self):
		head = self.getFileNewName()

		# we are reusing already built files, reuse body
		# TODO: write and read action
		body = self.paktrace.readBody(head)

		unit = {
			"head": head,
			"body": body,
			# TODO: write and read action
			"action": ""
		}

		return [ unit ]

	def getExt(self):
		return os.path.splitext(self.file_path)[1][len(os.path.extsep):].lower()

	def isDifferent(self):
		if not os.path.isfile(self.getTargetPath()):
			return True

		# Always consider files from nested build to be different
		# and contribute to the final build.
		if self.is_nested:
			return True

		return self.paktrace.isDifferent(self.getFileNewName())

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
		if Ui.verbosity == "verbose":
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

	# Produce an image that is properly writable.
	def openAndSanitizeImage(self):

		# HACK: Pillow has a bug and converts 8-bit greyscale PNG to 1-bit black and white image when converting to RGB,
		# We workaround the issue by converting PNG images to lossless WebP first, to get an RGB WebP
		# that will be properly loaded and converted to other RGB formats by Pillow.

		source_path = self.getSourcePath()

		if source_path[-4:].lower() == ".png":
			build_path = self.getTargetPath()

			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "webp")
			os.close(transient_handle)

			self.callProcess(self.cwebp_base_command + ["-lossless", "-z", "0", source_path, "-o", transient_path])

			image = Image.open(transient_path)

			os.remove(transient_path)
		else:
			image = Image.open(source_path)

		image = image.convert("RGBA")

		has_alpha = False

		# Strip the alpha channel if it's fully opaque.
		for x in range(0, image.width):
			for y in range(0, image.height):
				if image.getpixel((x, y))[3] != 255:
					has_alpha = True
					break

			if has_alpha:
				break

		if not has_alpha:
			image = image.convert("RGB")

		return image


# TODO: Catch when it is not supported and print a warning.
# It is only supported on DPK VFS.
# TODO: Raise a warning if used in an action file.
# It is not expected to be used in action files
# but generated by translating DELETED Files.
class Delete(Action):
	keyword = "delete"
	description = "mark file as deleted"

	def isDone(self):
		return False

	def effective_run(self):
		# Marking file as deleted is done once everything else is built.
		return self.getProducedUnitList(write=False)


class Ignore(Action):
	keyword = "ignore"
	description = "ignore file"

	def isDone(self):
		return False

	def effective_run(self):
		Ui.verbose("Ignore: " + self.file_path)
		return self.getProducedUnitList(write=False)


class Keep(Action):
	keyword = "keep"
	description = "keep file"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		Ui.laconic("Keep: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class Copy(Action):
	keyword = "copy"
	description = "copy file"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		Ui.laconic("Copy: " + self.file_path)
		shutil.copyfile(source_path, build_path)
		self.setTimeStamp()

		return self.getProducedUnitList()


class ConvertJpg(Action):
	keyword = "convert_jpg"
	description = "convert to jpg format"

	printable_target_format = "jpg"
	convert_jpg_quality = 92

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() in ("jpg", "jpeg"):
			Ui.laconic("File already in jpg, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to " + self.printable_target_format + ": " + self.file_path)
			image = self.openAndSanitizeImage()

			# OSError: cannot write mode RGBA as JPEG
			image = image.convert("RGB")

			image.save(build_path, quality=self.convert_jpg_quality)

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("jpg")


class ConvertBadJpg(ConvertJpg):
	keyword = "convert_low_jpg"
	description = "convert to low quality jpg format"

	printable_target_format = "low quality jpg"
	convert_jpg_quality = 50


class ConvertPng(Action):
	keyword = "convert_png"
	description = "convert to png format"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "png":
			Ui.laconic("File already in png, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to png: " + self.file_path)
			image = self.openAndSanitizeImage()
			image.save(build_path)

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

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "webp":
			Ui.laconic("File already in webp, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to " + self.printable_target_format +  ": " + self.file_path)

			image = self.openAndSanitizeImage()

			# cwebp doesn't support many input format, PNG is known to be well supported,
			# so we convert the image to PNG first.
			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "png")
			os.close(transient_handle)

			image.save(transient_path)

			self.callProcess(self.cwebp_base_command + self.cwebp_extra_args + [transient_path, "-o", build_path])

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

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == self.file_ext:
			Ui.laconic("File already in crn, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to " + self.printable_target_format + ": " + self.file_path)

			# HACK: The crunch tool only supports a small number of formats, and is
			# known to fail on some variants of the format it handles (example: PNG).
			# See https://github.com/DaemonEngine/crunch/issues/13
			# So, better convert to TGA first.

			# The TGA format produced by the ImageMagick "convert" tool is known to
			# be broken so we don't use the "convert" tool anymore.
			# See https://gitlab.com/illwieckz/investigating-tga-orientation-in-imagemagick

			# The image is converted to RGB or RGBA to make sure the produced TGA
			# is readable by crunch, and does not use an unsupported TGA variant.

			image = self.openAndSanitizeImage()

			transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "tga")
			os.close(transient_handle)

			image.save(transient_path)

			self.callProcess(["crunch", "-helperThreads", str(self.thread_count), "-noNormalDetection", "-file", transient_path] + self.crunch_extra_args + ["-quality", "255", "-out", build_path])

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

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "ogg":
			Ui.laconic("File already in vorbis, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to vorbis: " + self.file_path)
			self.callProcess(["ffmpeg", "-acodec", "libvorbis", "-i", source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("ogg")


class ConvertOpus(Action):
	keyword = "convert_opus"
	description = "convert to opus format"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "opus":
			Ui.laconic("File already in opus, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			Ui.laconic("Convert to opus: " + self.file_path)
			self.callProcess(["opusenc", source_path, build_path])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("opus")


class CompileIqm(Action):
	keyword = "compile_iqm"
	description = "compile to iqm format"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		if self.getExt() == "iqm":
			Ui.laconic("File already in iqm, copy: " + self.file_path)
			shutil.copyfile(source_path, build_path)
		else:
			for command_name in [ "iqmtool", "iqm", None ]:
				if command_name == None:
					Ui.error("FTEQW iqmtool utility not found")
				elif shutil.which(command_name) != None:
					break

			iqe_command_file = source_path + os.path.extsep + "cfg"
			if os.path.isfile(iqe_command_file):
				iqm_config = IqmConfig.File()
				iqm_config.readFile(iqe_command_file)
				iqm_config.translate(self.source_dir, self.build_dir)

				transient_handle, transient_path = tempfile.mkstemp(suffix="_" + os.path.basename(build_path) + "_transient" + os.path.extsep + "iqe.cfg")
				os.close(transient_handle)

				iqm_config.writeFile(transient_path)

				Ui.laconic("Compile to iqm using a command file: " + self.file_path)
				self.callProcess([command_name, "--cmd", transient_path])
			else:
				Ui.laconic("Compile to iqm: " + self.file_path)
				self.callProcess([command_name, build_path, source_path])

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

	def effective_run(self):
		source_path = self.getSourcePath()

		self.prevrun = Texset.PrevRun(self.source_tree, source_path)
		self.preview_list = self.prevrun.run()

		# it does it itself
		# self.setTimeStamp()

		return self.getProducedUnitList()

	def getProducedUnitList(self):
		unit_list = []
		for head in self.preview_list:
			body = [ head ]
			self.paktrace.write(self.file_path, head, body)

			unit = {
				"head": head,
				"body": body,
				"action": self.keyword
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

	def effective_run(self):
		source_path = self.getSourcePath()

		self.slothrun = Texset.SlothRun(self.source_tree, source_path)
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

		# No need for stub configuration in dummy pak anymore.
		builder = Pak.Builder(file_tree, self.stage_name, self.build_dir, disabled_action_list=disabled_action_list, is_nested=True, is_parallel=False)
		# keep track of built files
		produced_unit_list = builder.build()

		self.body = []
		for unit in produced_unit_list:
			self.body.extend(unit["body"])

		shutil.rmtree(self.transient_path)


class CopyBsp(DumbTransient):
	keyword = "copy_bsp"
	description = "copy bsp file"

	def effective_run(self):
		source_path = self.getSourcePath()
		build_path = self.getTargetPath()
		self.createSubdirs()

		self.createTransientPath()
		bsp_path = self.getFileNewName()
		bsp_transient_path = os.path.join(self.transient_path, bsp_path)

		Ui.laconic("Copy bsp: " + self.file_path)
		shutil.copyfile(source_path, bsp_transient_path)
		# TODO: isn't it done in setTimeStamp()?
		shutil.copystat(source_path, bsp_transient_path)

		map_compiler = MapCompiler.Compiler(self.source_tree, map_profile=self.map_profile, is_parallel=self.is_parallel)
		map_compiler.compile(bsp_transient_path, self.transient_maps_path, stage_done=["copy", "bsp", "vis", "light"])

		self.buildTransientPath(disabled_action_list=["copy_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()


class MergeBsp(DumbTransient):
	keyword = "merge_bsp"
	description = "merge into a bsp file"
	is_parallel = False

	def effective_run(self):
		# HACK: it's called on all the files but called for every file
		# that's why this action is not callable in parallel:
		# once the first run is done for one file, it's done
		# for others files too

		# FIXME: Add other files to the paktrace.

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

		Ui.laconic("Merging to bsp: " + bspdir_path)

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

		map_compiler = MapCompiler.Compiler(self.source_tree, map_profile=self.map_profile)
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

	def effective_run(self):
		source_path = self.getSourcePath()
		copy_path = self.getTargetPath()
		build_path = self.getTargetPath()
		bsp_path = self.getFileNewName()
		self.createSubdirs()

		self.createTransientPath()

		Ui.laconic("Compiling to bsp: " + self.file_path)

		map_compiler = MapCompiler.Compiler(self.source_tree, map_profile=self.map_profile)
		map_compiler.compile(source_path, self.transient_maps_path)

		self.buildTransientPath(disabled_action_list=["copy_bsp", "compile_bsp"])

		self.setTimeStamp()

		return self.getProducedUnitList()

	def getFileNewName(self):
		return self.switchExtension("bsp")
