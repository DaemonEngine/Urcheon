#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import os
import sys
import shutil
import subprocess
import operator
import importlib
import argparse
import logging
import fnmatch
import zipfile
from collections import OrderedDict

import bsp_cutter

# TODO: replace with / os.path.sep when reading then replace os.path.sep to / when writing# TODO: comment out missing files
# TODO: comment out missing files


class Log():
	# This is NOT the runtime logging, it's the package build logging
	def __init__(self):
		self.verbosely = False

	def print(self, message):
		# I duplicate print() because I will add color support and verbose/quiet support in the future
		print(message)

	def verbose(self, message):
		if self.verbosely:
			print(message)

	def warning(self, message):
		print("Warning: " + message)

	def notice(self, message):
		print("Notice: " + message)

	def error(self, message):
		print("Error: " + message)

log = Log()

class Config():
	def __init__(self, game_name):
		self.game = importlib.import_module("pak_profiles." + game_name)
		self.config_file_type_dict = [variable for variable in dir(self.game) if variable.startswith("file_")]
		self.file_type_dict = {}
		self.file_type_weight_dict = {}
		self.expandFileTypes()

	def inheritFileType(self, config_file_type_dict):
		if "inherit" in config_file_type_dict.keys():
			logging.debug("inherit from file type: " + config_file_type_dict["inherit"])
			inherited_file_type, weight = self.inheritFileType(getattr(self.game, config_file_type_dict["inherit"]))
		else:
			inherited_file_type, weight = {}, 0

		inspector = Inspector(None)

		for keyword in list(inspector.inspector_name_dict.keys()) + [
			"description",
			"action",
		]:
			if keyword in config_file_type_dict.keys():
				inherited_file_type[keyword] = config_file_type_dict[keyword]
			elif keyword not in inherited_file_type.keys():
				inherited_file_type[keyword] = None
		
		for keyword in inspector.inspector_name_dict.keys():
			if isinstance(inherited_file_type[keyword], str):
				inherited_file_type[keyword] = [ inherited_file_type[keyword] ]

		return inherited_file_type, weight + 1

	def expandFileTypes(self):
		for file_type in self.config_file_type_dict:
			logging.debug("expanding file type: " + file_type)
			self.file_type_dict[file_type] = []
			self.file_type_dict[file_type], self.file_type_weight_dict[file_type] = self.inheritFileType(getattr(self.game, file_type))


class Inspector():
	def __init__(self, game_name):
		if game_name:
			self.config = Config(game_name)
		else:
			self.config = None
		self.inspector_name_dict = {
			"file_name":			self.inspectFileName,
			"file_ext":				self.inspectFileExt,
			"file_base":			self.inspectFileBase,
			"file_prefix":			self.inspectFilePrefix,
			"file_suffix":			self.inspectFileSuffix,
			"dir_ancestor_name":	self.inspectDirAncestorName,
			"dir_father_name":		self.inspectDirFatherName,
			"dir_father_ext":		self.inspectDirFatherExt,
			"dir_grandfather_name":	self.inspectDirGrandFatherName,
			"dir_grandfather_ext":	self.inspectDirGrandFatherExt,
		}
		# I want lines printed in this order
		self.action_name_dict = OrderedDict()
		self.action_name_dict["copy"] =			"copy file"
		self.action_name_dict["merge_bsp"] =	"merge into a bsp file"
		self.action_name_dict["build_bsp"] =	"compile to bsp format"
		self.action_name_dict["convert_crn"] =	"convert to crn format"
		self.action_name_dict["convert_jpg"] =	"convert to jpg format"
		self.action_name_dict["convert_png"] =	"convert to png format"
		self.action_name_dict["convert_opus"] =	"convert to opus format"
		self.action_name_dict["keep"] = 		"keep file"
		self.action_name_dict["ignore"] =	 	"ignore file"
	
	def inspectFileName(self, file_path, file_name):
		name = os.path.basename(file_path)
		return name in file_name

	def inspectFileExt(self, file_path, file_ext):
		ext = os.path.splitext(file_path)[1][len(os.path.extsep):]
		return ext in file_ext

	def inspectFileBase(self, file_path, file_base):
		base = os.path.splitext(os.path.basename(file_path))[0]
		return base in file_base

	def inspectFilePrefix(self, file_path, file_prefix):
		suffix = os.path.basename(file_path).split('_')[0]
		return suffix in file_prefix

	def inspectFileSuffix(self, file_path, file_suffix):
		suffix = os.path.splitext(os.path.basename(file_path))[0].split('_')[-1]
		return suffix in file_suffix

	def inspectDirAncestorName(self, file_path, dir_name):
		previous = file_path
		while file_path != "":
			previous = file_path
			file_path = os.path.split(file_path)[0]
		return previous in dir_name

	def inspectDirFatherName(self, file_path, dir_name):
		father = os.path.split(file_path)[0]
		return father in dir_name

	def inspectDirFatherExt(self, file_path, dir_ext):
		ext = os.path.splitext(os.path.split(file_path)[0])[1][len(os.path.extsep):]
		return ext in dir_ext

	def inspectDirGrandFatherName(self, file_path, dir_name):
		grandfather = os.path.split(os.path.split(file_path)[0])[0]
		return grandfather in dir_name

	def inspectDirGrandFatherExt(self, file_path, dir_ext):
		ext = os.path.splitext(os.path.split(os.path.split(file_path)[0])[0])[1][len(os.path.extsep):]
		return ext in dir_ext

	def inspect(self, file_path):
		file_type_ordered_list = [x[0] for x in sorted(self.config.file_type_weight_dict.items(), key=operator.itemgetter(1), reverse=True)]
		logging.debug("looking for file path:" + file_path)
#		logging.debug("will try file types in this order: ", str(file_type_ordered_list))

		action = "keep"
		for file_type_name in file_type_ordered_list:
			logging.debug("trying file type:" + file_type_name)
			criteria_dict = self.config.file_type_dict[file_type_name].copy()
			file_type_action = criteria_dict.pop("action")
			file_type_description = criteria_dict.pop("description")

			matched_file_type = True
			for criteria in criteria_dict.keys():
				logging.debug("trying criteria: " + criteria + ", value: " + str(criteria_dict[criteria]))
				if criteria_dict[criteria] != None:
					matched_criteria = self.inspector_name_dict[criteria](file_path, criteria_dict[criteria])
					logging.debug("matched criteria: " + str(matched_criteria))
					if not matched_criteria:
						matched_file_type = False
						break

			if matched_file_type:
				action = file_type_action
				description  = file_type_description
				break

		if action == "keep":
			log.warning(file_path + ": unknown file found, will " + self.action_name_dict[action] + ".")
		else:
			log.print(file_path + ": " + description + " found, will " + self.action_name_dict[action] + ".")

		return action


class PakList():
	def __init__(self, file_dir, game_name):
		self.file_dir = file_dir
		self.pak_list_file_name = ".pakinfo/paklist"

		self.blacklist = [
			"Thumbs.db",
			"Makefile",
			"CMakeLists.txt",
			"__MACOSX",
			"*.DS_Store",
			"*.autosave",
			"*.bak",
			"*~",
			".*.swp",
			".git*",
			".pakinfo",
			"build",
		]

		pak_ignore_list_file_name = ".pakinfo/pakignore"
		if os.path.isfile(pak_ignore_list_file_name):
			pak_ignore_list_file = open(pak_ignore_list_file_name, "r")
			line_list = [line.strip() for line in pak_ignore_list_file]
			pak_ignore_list_file.close()
			for pattern in line_list:
				self.blacklist.append(pattern)

		logging.debug("blacklist: " + str(self.blacklist))

		self.inspector = Inspector(game_name)
		self.active_action_dict = OrderedDict()
		self.inactive_action_dict = OrderedDict()
		self.computed_active_action_dict = OrderedDict()
		self.computed_inactive_action_dict = OrderedDict()
		# I want lines printed in this order
		for action_name in self.inspector.action_name_dict.keys():
			self.active_action_dict[action_name] = []
			self.inactive_action_dict[action_name] = []
			self.computed_active_action_dict[action_name] = []
			self.computed_inactive_action_dict[action_name] = []

	def readActions(self):
		if os.path.isfile(self.pak_list_file_name):
			pak_list_file = open(self.pak_list_file_name, "r")
			line_list = [line.strip() for line in pak_list_file]
			pak_list_file.close()
			for line in line_list:
				# TODO: regex
				action = line.split(" ")[0]
				file_path = line[len(action) + 1:]
				if action[0] == '#':
					inactive_action = action[1:]
					logging.debug("known inactive action: " + inative_action + " for file: " + file_path)
					self.inactive_action_dict[inactive_action].append(file_path)
				else:
					if os.path.isfile(file_path):
						logging.debug("known action: " + action + " for file: " + file_path)
						self.active_action_dict[action].append(file_path)
					else:
						log.print("Disabling action: " + action + " for missing file: " + file_path)
						self.computed_inactive_action_dict[action].append(file_path)
						
		else:
			log.print("List .pakinfo/paklist not found: " + self.pak_list_file_name)

	def computeActions(self):
		for dir_name, subdir_name_list, file_name_list in os.walk(self.file_dir):
			dir_name = dir_name[len(os.path.curdir + os.path.sep):]
			for file_name in file_name_list:
				file_path = os.path.join(dir_name, file_name)
				for subdir_name in subdir_name_list:
					for pattern in self.blacklist:
						logging.debug("comparing subdir path: " + subdir_name + " with blacklist pattern: " + pattern)
						if fnmatch.fnmatch(subdir_name, pattern):
							logging.debug("found blacklisted directory: " + subdir_name)
							subdir_name_list.remove(subdir_name)

				blacklisted_file = False
				for pattern in self.blacklist:
					base_path = os.path.basename(file_path)
					logging.debug("comparing file path: " + base_path + " with blacklist pattern: " + pattern)
					if fnmatch.fnmatch(base_path, pattern):
						logging.debug("found blacklisted file: " + file_path)
						blacklisted_file = True
						break

				if not blacklisted_file:
					unknown_file_path = True
					logging.debug("active actions: " + str(self.active_action_dict))
					logging.debug("inactive actions:" + str(self.inactive_action_dict))
					for read_action in self.active_action_dict.keys():
						if file_path in self.active_action_dict[read_action]:
							log.print(file_path + ": Known file, will " + self.inspector.action_name_dict[read_action] + ".")
							self.computed_active_action_dict[read_action].append(file_path)
							unknown_file_path = False
						elif file_path in self.inactive_action_dict[read_action]:
							log.print(file_path + ": Disabled known file, will ignore it.")
							self.computed_inactive_action_dict[read_action].append(file_path)
							unknown_file_path = False
					if unknown_file_path:
						action = self.inspector.inspect(file_path)
						self.computed_active_action_dict[action].append(file_path)

	def writeActions(self):
		pak_list_file = open(self.pak_list_file_name, "w")
		for action in self.computed_active_action_dict.keys():
			for file_path in sorted(self.computed_active_action_dict[action]):
				line = action + " " + file_path
				pak_list_file.write(line + "\n")
		for action in self.computed_inactive_action_dict.keys():
			for file_path in sorted(self.computed_inactive_action_dict[action]):
				line = "#" + action + " " + file_path
				pak_list_file.write(line + "\n")
		pak_list_file.close()
	

class Builder():
	def __init__(self, source_dir, build_dir, game_name):
		self.source_dir = source_dir
		self.build_dir = build_dir
		self.game_name = game_name
		self.pak_list = PakList(source_dir, game_name)
		self.pak_list.readActions()
		self.bsp_list = []
		# I want actions executed in this order
		self.builder_name_dict = OrderedDict()
		self.builder_name_dict["copy"] = 			self.copyFile
		self.builder_name_dict["merge_bsp"] =		self.mergeBsp
		self.builder_name_dict["build_bsp"] =		self.buildBsp
		self.builder_name_dict["convert_jpg"] = 	self.convertJpg
		self.builder_name_dict["convert_png"] = 	self.convertPng
		self.builder_name_dict["convert_crn"] = 	self.convertCrn
		self.builder_name_dict["convert_opus"] =	self.convertOpus
		self.builder_name_dict["keep"] = 			self.keepFile
		self.builder_name_dict["ignore"] =			self.ignoreFile

	def getSourcePath(self, file_path):
		return self.source_dir + os.path.sep + file_path

	def getBuildPath(self, file_path):
		return self.build_dir + os.path.sep + file_path

	def isOlder(self, source_path, build_path):
		if not os.path.isfile(build_path):
			logging.debug("build file not found, acting like if older than source file: " + build_path)
			return True
		if os.stat(build_path).st_mtime < os.stat(source_path).st_mtime:
			logging.debug("build file older than source file: " + build_path)
			return True
		logging.debug("build file is not older than source file: " + build_path)
		return False

	def createSubdirs(self, build_path):
		build_subdir = os.path.dirname(build_path)
		if os.path.isdir(build_subdir):
			logging.debug("found build subdir: " +  build_subdir)
		else:
			logging.debug("create build subdir: " + build_subdir)
			os.makedirs(build_subdir)

	# TODO: buildpack
	def build(self):
		# TODO: check if not a directory
		if os.path.isdir(self.build_dir):
			logging.debug("found build dir: " + self.build_dir)
		else:
			logging.debug("create build dir: " + self.build_dir)
			os.makedirs(self.build_dir)

		logging.debug("reading build list from source dir: " + self.source_dir)

		# TODO: if already exist and older
		for action in self.builder_name_dict.keys():
			for file_path in self.pak_list.active_action_dict[action]:

				#TODO: if not source_path

				source_path = self.getSourcePath(file_path)
				self.builder_name_dict[action](file_path)

		logging.debug("bsp list: " + str(self.bsp_list))
		for bsp_path in self.bsp_list:
			self.createMiniMap(bsp_path)
			self.createNavMeshes(bsp_path)

	def ignoreFile(self, file_path):
		logging.debug("ignoring: " + file_path)

	def keepFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		log.print("Keeping: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)

	def copyFile(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		log.print("Copying: " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)
		ext = os.path.splitext(build_path)[1][len(os.path.extsep):]
		if ext == "bsp":
			self.bsp_list.append(file_path)

	def convertJpg(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileJpgNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) in ("jpg", "jpeg"):
			log.print("File already in jpg, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to jpg: " + file_path)
			subprocess.call(["convert", "-verbose", source_path, build_path])
		shutil.copystat(source_path, build_path)

	def convertPng(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFilePngNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "png":
			log.print("File already in png, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to png: " + file_path)
			subprocess.call(["convert", "-verbose", source_path, build_path])

	# TODO: convertDDS
	def convertCrn(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileCrnNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "crn":
			log.print("File already in crn, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to crn: " + file_path)
			subprocess.call(["crunch", "-file", source_path, "-out", build_path, "-quality", "255"])
		shutil.copystat(source_path, build_path)

	# TODO: convertVorbis
	def convertOpus(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(self.getFileOpusNewName(file_path))
		self.createSubdirs(build_path)
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		if self.getExt(file_path) == "opus":
			log.print("File already in opus, copying: " + file_path)
			shutil.copyfile(source_path, build_path)
		else:
			log.print("Convert to opus: " + file_path)
			subprocess.call(["opusenc", source_path, build_path])
		shutil.copystat(source_path, build_path)

	def mergeBsp(self, file_path):
		source_path = self.getSourcePath(self.getDirBspDirNewName(file_path))
		build_path = self.getBuildPath(self.getDirBspNewName(file_path))
		self.createSubdirs(build_path)
		bspdir_path = self.getDirBspDirNewName(file_path)
		bsp_path = self.getDirBspNewName(file_path)
		if bspdir_path in self.bsp_list:
			warning("Bsp file already there, will do nothing with: " + build_path)
			return
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		logging.debug("looking for file in same bspdir than: " + file_path)
		for sub_path in self.pak_list.active_action_dict["merge_bsp"]:
			if sub_path.startswith(bspdir_path):
				log.print("Merge to bsp: " + sub_path)
				self.pak_list.active_action_dict["merge_bsp"].remove(sub_path)
			else:
				logging.debug("file not from same bspdir: " + sub_path)
		bsp = bsp_cutter.Bsp()
		bsp.readDir(source_path)
		# TODO: if verbose
		bsp.writeFile(build_path)
		shutil.copystat(source_path, build_path)
		self.bsp_list.append(bsp_path)

	def buildBsp(self, file_path):
		source_path = self.getSourcePath(file_path)
		build_path = self.getBuildPath(file_path)
		bsp_path = self.getDirBspNewName(file_path)
		self.createSubdirs(build_path)
		if build_path in self.bsp_list:
			warning("Bsp file already there, will do nothing with: " + build_path)
			return
		if not self.isOlder(source_path, build_path):
			log.verbose("Unmodified file, do nothing: " + file_path)
			return
		log.print("Build to bsp " + file_path)
		shutil.copyfile(source_path, build_path)
		shutil.copystat(source_path, build_path)
		self.bsp_list.append(bsp_path)

	def createMiniMap(self, file_path):
		build_path = self.getBuildPath(file_path)
		# TODO: if minimap not newer
		# TODO: put q3map2 profile in game profile
		log.print("Creating MiniMap for: " + file_path)
	#	subprocess.call(["q3map2", "-game", "unv", "-minimap", build_path])
		subprocess.call(["q3map2_helper.sh", "--minimap", build_path])

	def createNavMeshes(self, file_path):
		build_path = self.getBuildPath(file_path)
		log.print("Creating NavMeshes for: " + file_path)
	#	subprocess.call(["q3map2", "-game", "unv", "-nav", build_path])
		subprocess.call(["q3map2_helper.sh", "--navmesh", build_path])
	
	def getExt(self, file_path):
		return os.path.splitext(file_path)[1][len(os.path.extsep):].lower()

	def getFileJpgNewName(self, file_path):
		return os.path.splitext(file_path)[0] + ".jpg"

	def getFilePngNewName(self, file_path):
		return os.path.splitext(file_path)[0] + ".png"

	def getFileCrnNewName(self, file_path):
		return os.path.splitext(file_path)[0] + ".crn"

	def getFileOpusNewName(self, file_path):
		return os.path.splitext(file_path)[0] + ".opus"

	def getFileBspNewName(self, file_path):
		return os.path.splitext(file_path)[0] + ".bsp"

	def getDirBspDirNewName(self, file_path):
		return file_path.split(".bspdir")[0] + ".bspdir"

	def getDirBspNewName(self, file_path):
		return file_path.split(".bspdir")[0] + ".bsp"


class Packer():
	def __init__(self, pk3dir, pk3):
		self.pk3dir_path = pk3dir
		self.pk3_path = pk3

	def createSubdirs(self, pack_path):
		pack_subdir = os.path.dirname(pack_path)
		if os.path.isdir(pack_subdir):
			logging.debug("found pack subdir: " +  pack_subdir)
		else:
			logging.debug("create pack subdir: " + pack_subdir)
			os.makedirs(pack_subdir)

	def pack(self):
		log.print("Packing " + self.pk3dir_path + " to: " + self.pk3_path)
		self.createSubdirs(self.pk3_path)
		logging.debug("opening: " + self.pk3_path)
		pk3 = zipfile.ZipFile(self.pk3_path, "w")
		
		orig_dir = os.getcwd()
		os.chdir(self.pk3dir_path)
		for dirname, subdirname_list, file_name_list in os.walk('.'):
			for file_name in file_name_list:
				file_path = os.path.join(dirname, file_name)[len(os.path.curdir + os.path.sep):]
				log.print("adding file to archive: " + file_path)
				pk3.write(file_path)
			
		logging.debug("closing: " + self.pk3_path)
		pk3.close()

		log.print("Package written: " + self.pk3_path)


class PakInfo():
	def __init__(self, source_dir):
		pak_info_path = source_dir + os.path.sep + ".pakinfo" + os.path.sep + "pakinfo"
		logging.debug("reading pakinfo: " + pak_info_path)

		if not os.path.isfile(pak_info_path):
			log.error("Missing pakinfo file")
			return None

		pak_info_file = open(pak_info_path, "r")
		line_list = [line.strip() for line in pak_info_file]
		pak_info_file.close()

		self.key_dict = {}
		for line in line_list:
			# TODO: regex
			key, value = line.split(": ")
			self.key_dict[key] = value

	def getKey(self, key_name):
		if key_name in self.key_dict.keys():
			return self.key_dict[key_name]
		else:
			log.error("Unknown key in pakinfo file: " + key_name)
			return None


def main():

	args = argparse.ArgumentParser(description="%(prog)s is a pak builder for my lovely granger.")
	args.add_argument("-D", "--debug", dest="debug", help="print debug information", action="store_true")
	args.add_argument("-v", "--verbose", dest="verbose", help="print verbose information", action="store_true")
	args.add_argument("-g", "--game-profile", dest="game_profile", metavar="GAMENAME", default="unvanquished", help="use game profile %(metavar)s, default: %(default)s")
	args.add_argument("-id", "--input-pk3dir", dest="input_pk3dir", metavar="DIRNAME", default=".", help="build from directory %(metavar)s, default: %(default)s")
	args.add_argument("-pd", "--output-prefix-pk3dir", dest="output_prefix_pk3dir", metavar="DIRNAME", default="build" + os.path.sep + "test", help="build pk3dir in directory %(metavar)s, default: %(default)s")
	args.add_argument("-pp", "--output-prefix-pk3", dest="output_prefix_pk3", metavar="DIRNAME", default="build" + os.path.sep + "pkg", help="build pk3 in directory %(metavar)s, default: %(default)s")
	args.add_argument("-od", "--output-pk3dir", dest="output_pk3dir", metavar="DIRNAME", help="build pk3dir as directory %(metavar)s")
	args.add_argument("-op", "--output-pk3", dest="output_pk3", metavar="FILENAME", help="build pk3 as file %(metavar)s")
	args.add_argument("-ev", "--extra-version", dest="extra_version", metavar="VERSION", help="add %(metavar)s to pk3 version string")
	args.add_argument("-u", "--update", dest="update", help="update paklist", action="store_true")
	args.add_argument("-b", "--build", dest="build", help="build pak", action="store_true")
	args.add_argument("-p", "--package", dest="package", help="compress pak", action="store_true")


	args = args.parse_args()

	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		logging.debug("Debug logging activated")
		logging.debug("args: " + str(args))
	
	if args.verbose:
		log.verbosely = True

	if args.update:
		pak_list = PakList(args.input_pk3dir, args.game_profile)
		pak_list.readActions()
		pak_list.computeActions()
		pak_list.writeActions()

	if args.package or args.build:
		if args.output_pk3dir:
			output_pk3dir = args.output_pk3dir
		else:
			pak_info = PakInfo(args.input_pk3dir)
			if not pak_info:
				return
			pak_pakname = pak_info.getKey("pakname")
			if not pak_pakname:
				return
			output_pk3dir = args.output_prefix_pk3dir + os.path.sep + pak_pakname + "_test.pk3dir"

	if args.build:
		builder = Builder(args.input_pk3dir, output_pk3dir, args.game_profile)
		builder.build()

	if args.package:
		if args.output_pk3:
			output_pk3 = args.output_pk3
		else:
			pak_info = PakInfo(args.input_pk3dir)
			if not pak_info:
				return
			pak_pakname = pak_info.getKey("pakname")
			pak_version = pak_info.getKey("version")
			if not pak_pakname or not pak_version:
				return
			if args.extra_version:
				pak_version += args.extra_version
			output_pk3 = args.output_prefix_pk3 + os.path.sep + pak_pakname + "_" + pak_version + ".pk3"

		packer = Packer(output_pk3dir, output_pk3)
		packer.pack()
		

if __name__ == "__main__":
	main()
