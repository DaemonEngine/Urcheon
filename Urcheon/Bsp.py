#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

from Urcheon import Map
from Urcheon import Ui
import __main__ as m
import argparse
import glob
import json
import logging
import os
import struct
import sys
from collections import OrderedDict
from logging import debug
from PIL import Image


class Lump():
	bsp_parser_dict = None

	def readBspDirLump(self, dir_name, lump_name):
		file_list = glob.glob(dir_name + os.path.sep + lump_name + os.path.extsep + "*")

		if len(file_list) > 1:
			# TODO: handle that
			Ui.error("more than one " + lump_name + " lump in bspdir")
		if len(file_list) == 0:
			# TODO: warning?
			return

		file_path = file_list[0]
		file_ext = os.path.splitext(file_path)[-1][1:]
		file_name = os.path.splitext(os.path.basename(file_path))[0]

		if file_ext == "bin":
			if file_name in self.bsp_parser_dict["lump_name_list"]:
				blob_file = open(file_path, "rb")
				self.importLump(blob_file.read())
				blob_file.close()
			else:
				Ui.error("unknown lump file: " + file_name)

		elif not self.validateExtension(file_ext):
			Ui.error("unknown lump format: " + file_path)

		if file_ext == "d":
			self.readDir(file_path)
		else:
			self.readFile(file_path)


class Blob(Lump):
	blob_stream = None

	def isEmpty(self):
		return not self.blob_stream

	def readFile(self, file_name):
		blob_file = open(file_name, "rb")
		self.importLump(blob_file.read())
		blob_file.close()
		return True

	def writeFile(self, file_name):
		blob_file = open(file_name, "wb")
		blob_file.write(self.exportLump())
		blob_file.close()

	def writeBspDirLump(self, dir_name, lump_name):
		self.writeFile(dir_name + os.path.sep + lump_name + os.path.extsep + "bin")

	def importLump(self, blob):
		self.blob_stream = blob

	def exportLump(self):
		return self.blob_stream


class Q3Entities(Lump):
	entites_as_map = None

	def isEmpty(self):
		return not self.entities_as_map

	def validateExtension(self, file_ext):
		return file_ext == "txt"

	def readFile(self, file_name):
		entities_file = open(file_name, "rb")
		self.importLump(entities_file.read())
		entities_file.close()
		return True

	def writeFile(self, file_name):
		entities_file = open(file_name, "wb")
		entities_file.write(self.exportLump().split(b'\0', 1)[0])
		entities_file.close()
		return True

	def writeBspDirLump(self, dir_name, lump_name):
		self.writeFile(dir_name + os.path.sep + lump_name + os.path.extsep + "txt")

	def printString(self):
		print("*** Entities")
		print(bytes.decode(self.exportLump().split(b'\0', 1)[0]))

	def printList(self):
		print("*** Entities")
		i = 0
		for entity in self.entities_as_map.entity_list:
			string = ""
			for thing in entity.thing_list:
				if isinstance(thing, Map.KeyValue):
					string += "\"" + thing.key + "\": \"" + thing.value + "\", "

			print(str(i) + ": [" + string[:-2] + "]")
			i += 1

		print("")
		return True

	def printSoundList(self):
		print("*** Entities")
		i = 0
		for entity in self.entities_as_map.entity_list:
			found = False
			for thing in entity.thing_list:
				if isinstance(thing, Map.KeyValue):
					for sound_keyword in Map.q3_sound_keyword_list:
						if thing.key.lower() == sound_keyword.lower():
							print(str(i) + ": " + thing.value + " [" + sound_keyword + "]")
							i += 1

		print("")
		return True

	def substituteKeywords(self, substitution):
		self.entities_as_map.substituteKeywords(substitution)

	def lowerCaseFilePaths(self):
		self.entities_as_map.lowerCaseFilePaths()

	def importLump(self, blob):
		self.entity_list = []
		entities_bstring = blob.split(b'\0', 1)[0]

		self.entities_as_map = Map.Map()
		self.entities_as_map.numbering_enabled = False
		self.entities_as_map.readBlob(entities_bstring)

	def exportLump(self):
		blob = b''
		blob += self.entities_as_map.exportFile().encode()
		blob += b'\0'
		return blob


class Q3Textures(Lump):
	texture_list = None

	def int2bstr(self, i):
		return "{0:b}".format(i).zfill(30)

	def bstr2int(self, s):
		return int(s, 2)

	def isEmpty(self):
		return not self.texture_list

	def validateExtension(self, file_ext):
		return file_ext == "csv"

	def readFile(self, file_name):
		# TODO: check
		textures_file = open(file_name, 'rb')

		textures_file_bstring = textures_file.read()
		self.texture_list = []

		for texture_line_bstring in textures_file_bstring.split(b'\n'):
			# TODO: check 3 comma minimum
			# TODO: allow string path with comma
			if texture_line_bstring != b'':
				bstring_list = texture_line_bstring.split(b',')
				flags = self.bstr2int(bstring_list[0])
				contents = self.bstr2int(bstring_list[1])
				name = bytes.decode(bstring_list[2])
				self.texture_list.append({"name": name, "flags": flags, "contents": contents})

		textures_file.close()

		return True

	def writeFile(self, file_name):
		textures_string = ""
		for i in range(0, len(self.texture_list)):
			textures_string += self.int2bstr(self.texture_list[i]["flags"]) + ","
			textures_string += self.int2bstr(self.texture_list[i]["contents"]) + ","
			textures_string += self.texture_list[i]["name"] + "\n"

		# TODO: check
		textures_file = open(file_name, "wb")
		textures_file.write(textures_string.encode())
		textures_file.close()

	def writeBspDirLump(self, dir_name, lump_name):
		self.writeFile(dir_name + os.path.sep + lump_name + os.path.extsep + "csv")

	def printList(self):
		# TODO: check

		print("*** Textures:")
		for i in range(0, len(self.texture_list)):
			print(str(i) + ": " + self.texture_list[i]["name"] + " [" + self.int2bstr(self.texture_list[i]["flags"]) + ", " + self.int2bstr(self.texture_list[i]["contents"]) + "]")
		print("")

	def lowerCaseFilePaths(self):
		textures_count = len(self.texture_list)

		for i in range(0, textures_count):
			self.texture_list[i]["name"] = self.texture_list[i]["name"].lower()

	def importLump(self, blob):
		# TODO: check exists

		# 64 bytes string name
		# 4 bytes integer flags
		# 4 bytes integer contents
		textures_count = int(len(blob) / 72)

		self.texture_list = []

		# TODO: check

		for i in range(0, textures_count):
			offset = i * 72
			bstring = blob[offset:offset + 64]
			name = bytes.decode(bstring.split(b'\0', 1)[0])
			flags, contents = struct.unpack('<II', blob[offset + 64: offset + 72])
			self.texture_list.append({})
			self.texture_list[i]["name"] = name
			self.texture_list[i]["flags"] = flags
			self.texture_list[i]["contents"] = contents

	def exportLump(self):
		blob = b''

		for i in range(0, len(self.texture_list)):

				flags_buint=(self.texture_list[i]["flags"]).to_bytes(4, "little")
				contents_buint=(self.texture_list[i]["contents"]).to_bytes(4, "little")

				# Always add \x00, then pad
				name_bstring = (self.texture_list[i]["name"]).encode() + b'\0'

				# TODO: check < 64
				for i in range(0, (64 - len(name_bstring))):
					name_bstring += b'\0'

				blob += name_bstring + flags_buint + contents_buint

		return blob


class Q3Lightmaps(Lump):
	lightmap_list = []
	lightmap_colorspace = "RGB"
	lightmap_width = 128
	lightmap_height = 128
	lightmap_depth = 3
	lightmap_size = lightmap_width * lightmap_height * lightmap_depth
	lightmap_line_size = lightmap_width * lightmap_depth
	lightmap_resolution = str(lightmap_width) + "x" + str(lightmap_height) + "x" + str(lightmap_depth)

	def printList(self):
		print("*** Lightmaps:")
		for i in range(0, len(self.lightmap_list)):
			print("#" + str(i) + ": [" + self.lightmap_resolution + ", " + self.lightmap_colorspace + ", " + str(len(self.lightmap_list[i])) + "]")
		print("")
		return True

	def isEmpty(self):
		return not self.lightmap_list

	def validateExtension(self, file_ext):
		return file_ext == "d"

	def readDir(self, dir_name):
		# TODO: check if a dir, perhaps argparse can do
		self.lightmap_list = []
		file_list = sorted(glob.glob(dir_name + os.path.sep + "lm_*" + os.path.extsep + "*"))
		for file_name in file_list:
			debug("loading lightmap: " + file_name)
			image = Image.open(file_name)
			lightmap = image.convert(self.lightmap_colorspace).tobytes()

			lightmap_size = int(len(lightmap))
			if lightmap_size != self.lightmap_size:
				Ui.error("bad file " + file_name + ", must be a " + self.lightmap_resolution + " picture, found " + str(lightmap_size) + ", expected " + str(self.lightmap_size))

			self.lightmap_list.append(lightmap)

	def writeDir(self, dir_name):
		if not os.path.exists(dir_name):
			os.makedirs(dir_name, exist_ok=True)

		for i in range(0, len(self.lightmap_list)):
			file_name = "lm_" + str(i).zfill(4) + os.path.extsep + "tga"

			# TODO: os independent:
			file_path = dir_name + os.path.sep + file_name
			# TODO: check
			lightmap_file = open(file_path, "wb")

			# 1: Identification field length (see later for my arbitrary 18 chars string, here 18, up to 255)
			# 1: No color map
			# 1: Type 2 (RGB)
			# 5: Color map spec (ignored)
			header = b'\x12\0\x02\0\0\0\0\0'
			# 2: Origin X
			# 2: Origin Y
			header += b'\0\0\0\0'
			# 2: Width
			# 2: Height
			header += self.lightmap_width.to_bytes(2, "little")
			header += self.lightmap_height.to_bytes(2, "little")
			# 1: Bits per pixels (24)
			header += (self.lightmap_depth * 8).to_bytes(1, "little")
			# 1: Attribute bits (0 for 24)
			header += b'\0'
			header += b'Granger loves you\0'

			raw = self.lightmap_list[i]

			data = b''
			# Last line is first line
			for j in range(0, self.lightmap_size, self.lightmap_line_size):
				line = raw[self.lightmap_size - self.lightmap_line_size - j : self.lightmap_size - j]

				# RGB → BGR
				for k in range(0, self.lightmap_line_size, self.lightmap_depth):
					data += line[k : k + self.lightmap_depth][::-1]

			debug("header length: " + str(len(header)))
			debug("data length: " + str(len(data)))

			blob = header + data

			lightmap_file.write(blob)
			lightmap_file.close()

	def writeBspDirLump(self, dir_name, lump_name):
		self.writeDir(dir_name + os.path.sep + lump_name + os.path.extsep + "d")

	def importLump(self, blob):
		self.lightmap_list = []
		lump_count = int(len(blob) / self.lightmap_size)

		for i in range(0, lump_count):
			self.lightmap_list.append(blob[i * self.lightmap_size : (i + 1) * self.lightmap_size])

		return True

	def exportLump(self):
		blob = b''
		# TODO: better
		for i in range(0, len(self.lightmap_list)):
			blob += self.lightmap_list[i]

		return blob


class QFLightmaps(Q3Lightmaps):
	lightmap_list = []
	lightmap_colorspace = "RGB"
	lightmap_width = 512
	lightmap_height = 512
	lightmap_depth = 3
	lightmap_size = lightmap_width * lightmap_height * lightmap_depth
	lightmap_line_size = lightmap_width * lightmap_depth
	lightmap_resolution = str(lightmap_width) + "x" + str(lightmap_height) + "x" + str(lightmap_depth)


class Bsp():
	def __init__(self, bsp_magic_number=None, bsp_version=None):
		self.bsp_file = None
		self.bsp_file_name = None

		# metadata for printing purpose
		self.lump_directory = {}
		self.sound_list = None

		# lumps are stored here
		self.lump_dict = {}

		if bsp_magic_number and bsp_version:
			self.bsp_magic_number = bsp_magic_number
			self.bsp_version = bsp_version
			self.bsp_parser_dict = bsp_dict[bsp_magic_number][bsp_version]

		else:
			self.bsp_magic_number = None
			self.bsp_version = None
			self.bsp_parser_dict = None

	def readFile(self, bsp_file_name):
		# TODO: check
		self.bsp_file_name = bsp_file_name
		self.bsp_file = open(self.bsp_file_name, 'rb')

		# FIXME: check file length
		read_bsp_magic_number = self.bsp_file.read(4).decode()
		for bsp_magic_number in bsp_dict.keys():
			if bsp_magic_number == read_bsp_magic_number:
				self.bsp_magic_number = bsp_magic_number
				break

		if not self.bsp_magic_number:
			self.bsp_file.close()
			self.bsp_file = None
			Ui.error(": unknown BSP magic number " + str(read_bsp_magic_number))

		self.bsp_file.seek(len(self.bsp_magic_number))

		# FIXME: check file length
		read_bsp_version = struct.unpack('<I', self.bsp_file.read(4))[0]
		for bsp_version in bsp_dict[self.bsp_magic_number].keys():
			if bsp_version == read_bsp_version:
				self.bsp_version = bsp_version
				break

		if not self.bsp_version:
			self.bsp_file.close()
			self.bsp_file = None
			Ui.error(": unknown BSP version " + str(read_bsp_version))

		self.bsp_parser_dict = bsp_dict[self.bsp_magic_number][self.bsp_version]
		self.readLumpList()

		for lump_name in self.bsp_parser_dict["lump_name_list"]:
			self.readLump(lump_name)

		self.bsp_file.close()

	def readDir(self, dir_name):
		# TODO: check if a dir, perhaps argparse can do

		bsp_description_file_path = os.path.join(dir_name, "bsp.json")

		if os.path.isfile(bsp_description_file_path):
			bsp_description_file = open(bsp_description_file_path, "r")
			bsp_json_dict = json.loads(bsp_description_file.read())
			bsp_description_file.close()

			self.bsp_magic_number = bsp_json_dict["bsp_magic_number"]
			self.bsp_version = bsp_json_dict["bsp_version"]
		else:
			# backward compatibility with early bspdir
			self.bsp_magic_number = "IBSP"
			self.bsp_version = 46

		self.bsp_parser_dict = bsp_dict[self.bsp_magic_number][self.bsp_version]

		for lump_name in self.bsp_parser_dict["lump_name_list"]:
			file_list = glob.glob(dir_name + os.path.sep + lump_name + os.path.extsep + "*")

			if len(file_list) > 1:
				# TODO: handling
				Ui.error("more than one " + lump_name + " lump in bspdir")
			if len(file_list) == 0:
				# TODO: warning?
				continue

			file_path = file_list[0]
			file_ext = os.path.splitext(file_path)[-1][1:]
			file_name = os.path.splitext(os.path.basename(file_path))[0]

			lump = self.bsp_parser_dict["lump_dict"][lump_name]()
			lump.bsp_parser_dict = self.bsp_parser_dict

			lump.readBspDirLump(dir_name, lump_name)
			self.lump_dict[lump_name] = lump.exportLump()

			self.lump_directory[lump_name] = {}
			self.lump_directory[lump_name]["offset"] = None
			self.lump_directory[lump_name]["length"] = None

	def printFileName(self):
		print("*** File:")
		print(self.bsp_file_name)
		print("")


	def substituteKeywords(self, substitution):
		for lump_name in ["entities"]:
			if lump_name in self.lump_dict:
				lump = self.bsp_parser_dict["lump_dict"][lump_name]()
				lump.importLump(self.lump_dict[lump_name])
				lump.substituteKeywords(substitution)
				self.lump_dict[lump_name] = lump.exportLump()

	def lowerCaseFilePaths(self):
		for lump_name in ["entities", "textures"]:
			if lump_name in self.lump_dict:
				lump = self.bsp_parser_dict["lump_dict"][lump_name]()
				lump.importLump(self.lump_dict[lump_name])
				lump.lowerCaseFilePaths()
				self.lump_dict[lump_name] = lump.exportLump()


	def readLumpList(self):
		self.lump_directory = {}

		# TODO: check

		larger_offset = 0
		ql_advertisements_offset = 0
		for lump_name in self.bsp_parser_dict["lump_name_list"]:
			# FIXME: q3 centric
			# 4 bytes string magic number (IBSP)
			# 4 bytes integer version
			# 4 bytes integer lump offset
			# 4 bytes integer lump size
			self.bsp_file.seek(8 + (self.bsp_parser_dict["lump_name_list"].index(lump_name) * 8))

			self.lump_directory[lump_name] = {}

			offset, length = struct.unpack('<II', self.bsp_file.read(8))

			# QuakeLive Hack, an extra advertisement lump is added
			# at the end of IBSP 47 but original IBSP 47 (RTCW) does
			# not have it.
			# It looks like there is no way to test its presence other
			# than testing if read value is garbage or not and praying
			# for not getting garbage value that would be coincidentally
			# equal to the largest offset encountered, basically pray for
			# map compilers to not write the first characters of the
			# optional custom string the way they form a number equal to
			# the largest offset of legit lumps.
			# Also, pray for advertised last lump length being properly
			# 4-bytes aligned.

			if lump_name == "advertisements":
				if offset != ql_advertisements_offset:
					offset, length = (larger_offset, 0)
			else:
				if offset > larger_offset:
					larger_offset = offset
					ql_advertisements_offset = offset + length

			self.lump_directory[lump_name]["offset"], self.lump_directory[lump_name]["length"] = (offset, length)
			self.lump_dict[lump_name] = None

	def printLumpList(self):
		# TODO: check

		print("*** Lumps:")
		for i in range(0, len(self.bsp_parser_dict["lump_name_list"])):
			lump_name = self.bsp_parser_dict["lump_name_list"][i]
			if lump_name in self.lump_directory:
				if not self.lump_directory[lump_name]["offset"]:
					# bspdir, length is also unknown
					print(str(i) + ": " + lump_name )
				else:
					print(str(i) + ": " + lump_name + " [" + str(self.lump_directory[lump_name]["offset"]) + ", " + str(self.lump_directory[lump_name]["length"]) + "]")
		print("")

	def readLump(self, lump_name):
		# TODO: check

		# 4 bytes string magic number (IBSP)
		# 4 bytes integer version
		# 4 bytes integer lump offset
		# 4 bytes integer lump size
		self.bsp_file.seek(8 + (self.bsp_parser_dict["lump_name_list"].index(lump_name) * 8))
		offset, length = struct.unpack('<II', self.bsp_file.read(8))

		self.bsp_file.seek(offset)
		self.lump_dict[lump_name] = self.bsp_file.read(length)


	def writeFile(self, bsp_file_name):
		bsp_file = open(bsp_file_name, "wb")

		# Must be a multiple of 4
		metadata_blob = b'Granger loves you!\0\0'

		lumps_blob = b''
		directory_blob = b''

		# FIXME: q3-centric
		# 4 bytes string magic number (IBSP)
		# 4 bytes integer version
		# 4 bytes integer lump offset per lump
		# 4 bytes integer lump size per lump
		# 17 lumps + 1 extra empty lump (Quake Live advertisements)

		lump_count = len(self.bsp_parser_dict["lump_name_list"])
		# Hack: if IBSP 46 (Quake 3), add extra empty lump because q3map2 loads
		# advertisements lump from Quake Live even if not there, mistakenly
		# computing lump offset from random data (usually from custom string).
		# This way we ensure q3map2 will not load garbage by mistake
		# and produced bsp are always fine even when read by broken tools.
		if self.bsp_magic_number == "IBSP" and self.bsp_version == 46:
			lump_count += 1

		lump_start = 8 + lump_count * 8 + len(metadata_blob)
		for lump_name in self.bsp_parser_dict["lump_name_list"]:
			if lump_name in self.lump_dict:
				lump_content = self.lump_dict[lump_name]
				lump_length = len(self.lump_dict[lump_name])
			else:
				lump_content = b""
				lump_length = 0

			print(str(self.bsp_parser_dict["lump_name_list"].index(lump_name)) + ": " + lump_name + " [" + str(lump_start) + ", " + str(lump_length) + "]")
			directory_blob += lump_start.to_bytes(4, "little")
			directory_blob += lump_length.to_bytes(4, "little")
			lump_start += lump_length

			lumps_blob += lump_content

			# Align lump to 4 bytes if not empty
			# For reference, q3map2 does not count these extra bytes in lump length
			# This happens for entities string for example
			if lump_length != 0 and lump_length % 4 != 0:
				for missing_byte in range(0, 4 - (lump_length % 4)):
					lumps_blob += b'\0'
					lump_start += 1
					# silence pylint on unused variable
					missing_byte

		# Hack: see above for more explanations,
		# if IBSP 46 (Quake 3), add extra empty lump because q3map2 loads
		# advertisements lump from Quake Live even if not there.
		if self.bsp_magic_number == "IBSP" and self.bsp_version == 46:
			directory_blob += lump_start.to_bytes(4, "little") + b"\0\0\0\0"

		blob = self.bsp_magic_number.encode()
		blob += self.bsp_version.to_bytes(4, "little")
		blob += directory_blob
		blob += metadata_blob
		blob += lumps_blob

		bsp_file.write(blob)
		bsp_file.close()

	def writeDir(self, dir_name):
		if not os.path.exists(dir_name):
			os.makedirs(dir_name, exist_ok=True)

		for lump_name in self.bsp_parser_dict["lump_name_list"]:
			lump = self.bsp_parser_dict["lump_dict"][lump_name]()

			if lump_name in self.lump_dict:
				lump.importLump(self.lump_dict[lump_name])
				if not lump.isEmpty():
					lump.writeBspDirLump(dir_name, lump_name)

		bsp_json_dict = {
			"bsp_magic_number": self.bsp_magic_number,
			"bsp_version": self.bsp_version,
		}

		bsp_description_file_path = os.path.join(dir_name, "bsp.json")
		bsp_description_file = open(bsp_description_file_path, "w")
		bsp_description_file.write(json.dumps(bsp_json_dict, sort_keys=True, indent="\t"))
		bsp_description_file.close()

	def importLump(self, lump_name, blob):
		self.lump_dict[lump_name] = blob

	def exportLump(self, lump_name):
		if lump_name in self.lump_dict.keys():
			return self.lump_dict[lump_name]
		else:
			return b""


# must be defined after classes otherwise Python will not find references

# see http://www.mralligator.com/q3/
q3_lump_dict = OrderedDict()
q3_lump_dict["entities"] = Q3Entities
q3_lump_dict["textures"] = Q3Textures
q3_lump_dict["planes"] = Blob
q3_lump_dict["nodes"] = Blob
q3_lump_dict["leafs"] = Blob
q3_lump_dict["leaffaces"] = Blob
q3_lump_dict["leafbrushes"] = Blob
q3_lump_dict["models"] = Blob
q3_lump_dict["brushes"] = Blob
q3_lump_dict["brushsides"] = Blob
q3_lump_dict["vertexes"] = Blob
q3_lump_dict["meshverts"] = Blob
q3_lump_dict["effects"] = Blob
q3_lump_dict["faces"] = Blob
q3_lump_dict["lightmaps"] = Q3Lightmaps
q3_lump_dict["lightvols"] = Blob
q3_lump_dict["visdata"] = Blob
q3_lump_name_list = list(q3_lump_dict.keys())

ql_lump_dict = q3_lump_dict.copy()
ql_lump_dict["advertisements"] = Blob
ql_lump_name_list = list(ql_lump_dict.keys())

ja_lump_dict = q3_lump_dict.copy()
ja_lump_dict["lightarray"] = Blob
ja_lump_name_list = list(ja_lump_dict.keys())

qf_lump_dict = q3_lump_dict.copy()
qf_lump_dict["lightmaps"] = QFLightmaps
qf_lump_dict["lightarray"] = Blob
qf_lump_name_list = list(qf_lump_dict.keys())

fbsp_dict = {
	# Warsow uses version 1
	# it's an RBSP derivative with larger lightmaps
	1: {
		"lump_dict": qf_lump_dict,
		"lump_name_list": qf_lump_name_list,
	}
}

ibsp_dict = {
	# Quake 2, not supported yet
	# 19: {},

	# Quake 3 Arena, Tremulous, World of Padman, Xonotic, Unvanquished, etc.
	46: {
		"lump_dict": q3_lump_dict,
		"lump_name_list": q3_lump_name_list,
	},

	# RCTW, Wolf:ET, Quake Live, etc.
	47: {
		"lump_dict": ql_lump_dict,
		"lump_name_list": ql_lump_name_list,
	},
}

rbsp_dict = {
	# Both JA, JK2, Soldier of Fortune use version 1
	1: {
		"lump_dict": ja_lump_dict,
		"lump_name_list": ja_lump_name_list,
	}
}

bsp_dict = {
	# QFusion
	"FBSP": fbsp_dict,

	# id Tech 3
	"IBSP": ibsp_dict,

	# Raven
	"RBSP": rbsp_dict,

	# Valve/Source, not supported yet
	# see https://developer.valvesoftware.com/wiki/Source_BSP_File_Format
	# "VBSP": {},
}


def main(stage=None):
	# TODO: check files

	if stage:
		prog_name = os.path.basename(m.__file__) + " " + stage
	else:
		prog_name = os.path.basename(m.__file__)

	description="%(prog)s is a BSP parser for my lovely granger."

	args = argparse.ArgumentParser(description=description, prog=prog_name)
	args.add_argument("-D", "--debug", help="print debug information", action="store_true")
	args.add_argument("-ib", "--input-bsp", dest="input_bsp_file", metavar="FILENAME",  help="read from .bsp file %(metavar)s")
	args.add_argument("-id", "--input-bspdir", dest="input_bsp_dir", metavar="DIRNAME", help="read from .bspdir directory %(metavar)s")
	args.add_argument("-ob", "--output-bsp", dest="output_bsp_file", metavar="FILENAME", help="write to .bsp file %(metavar)s")
	args.add_argument("-od", "--output-bspdir", dest="output_bsp_dir", metavar="DIRNAME", help="write to .bspdir directory %(metavar)s")
	args.add_argument("-ie", "--input-entities", dest="input_entities_file", metavar="FILENAME",  help="read from entities .txt file %(metavar)s")
	args.add_argument("-oe", "--output-entities", dest="output_entities_file", metavar="FILENAME", help="write to entities .txt file %(metavar)s")
	args.add_argument("-it", "--input-textures", dest="input_textures_file", metavar="FILENAME",  help="read rom textures .csv file %(metavar)s")
	args.add_argument("-ot", "--output-textures", dest="output_textures_file", metavar="FILENAME", help="write to textures .csv file %(metavar)s")
	args.add_argument("-il", "--input-lightmaps", dest="input_lightmaps_dir", metavar="DIRNAME",  help="read from lightmaps directory %(metavar)s")
	args.add_argument("-ol", "--output-lightmaps", dest="output_lightmaps_dir", metavar="DIRNAME", help="write to lightmaps directory %(metavar)s")
	args.add_argument("-sl", "--strip-lightmaps", help="empty the lightmap lump", action="store_true")
	args.add_argument("-sk", "--substitute-keywords", dest="substitute_keywords", metavar="FILENAME", help="use entity keyword substitution rules from .csv file %(metavar)s")
	args.add_argument("-Lf', '--lowercase-filepaths", dest="lowercase_filepaths", help="lowercase file paths", action="store_true")
	args.add_argument("-la", "--list-all", help="list all", action="store_true")
	args.add_argument("-lL", "--list-lumps", help="list lumps", action="store_true")
	args.add_argument("-le", "--list-entities", help="list entities", action="store_true")
	args.add_argument("-ls", "--list-sounds", help="list sounds", action="store_true")
	args.add_argument("-lt", "--list-textures", help="list textures", action="store_true")
	args.add_argument("-ll", "--list-lightmaps", help="list lightmaps", action="store_true")
	args.add_argument("-pe", "--print-entities", help="print entities", action="store_true")

	args = args.parse_args()
	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		debug("Debug logging activated")
		debug("args: " + str(args))

	bsp = Bsp()

	if args.input_bsp_file:
		bsp.readFile(args.input_bsp_file)

	# TODO: must conflict with input_bsp_file
	if args.input_bsp_dir:
		bsp.readDir(args.input_bsp_dir)

	if args.input_entities_file:
		entities = Q3Entities()
		entities.readFile(args.input_entities_file)
		bsp.importLump("entities", entities.exportLump())

	if args.input_textures_file:
		textures = Q3Textures()
		textures.readFile(args.input_textures_file)
		bsp.importLump("textures", textures.exportLump())

	if args.input_lightmaps_dir:
		lightmaps = Q3Lightmaps()
		lightmaps.readDir(args.input_lightmaps_dir)
		bsp.importLump("lightmaps", lightmaps.exportLump())

	# TODO: perhaps it must conflict with input_lightmaps_file
	if args.strip_lightmaps:
		lightmaps = Q3Lightmaps()
		bsp.importLump("lightmaps", lightmaps.exportLump())

	if args.substitute_keywords:
		substitution = Map.KeyValueSubstitution()
		substitution.readFile(args.substitute_keywords)
		bsp.substituteKeywords(substitution)

	if args.lowercase_filepaths:
		bsp.lowerCaseFilePaths()

	if args.output_bsp_file:
		bsp.writeFile(args.output_bsp_file)

	if args.output_bsp_dir:
		bsp.writeDir(args.output_bsp_dir)

	entities = bsp.bsp_parser_dict["lump_dict"]["entities"]()
	entities.importLump(bsp.exportLump("entities"))

	textures = bsp.bsp_parser_dict["lump_dict"]["textures"]()
	textures.importLump(bsp.exportLump("textures"))

	lightmaps = bsp.bsp_parser_dict["lump_dict"]["lightmaps"]()
	lightmaps.importLump(bsp.exportLump("lightmaps"))

	if args.output_entities_file:
		entities.writeFile(args.output_entities_file)

	if args.output_textures_file:
		textures.writeFile(args.output_textures_file)

	if args.output_lightmaps_dir:
		lightmaps.writeDir(args.output_lightmaps_dir)

	if args.list_all:
		args.list_lumps = True

		if not entities.isEmpty():
			args.list_entities = True
			args.list_sounds = True

		if not textures.isEmpty():
			args.list_textures = True

		if not lightmaps.isEmpty():
			args.list_lightmaps = True

	if args.list_lumps:
		bsp.printLumpList()

	if args.list_entities:
		entities.printList()

	if args.list_textures:
		textures.printList()

	if args.list_lightmaps:
		lightmaps.printList()

	if args.list_sounds:
		entities.printSoundList()

	if args.print_entities:
		entities.printString()


if __name__ == "__main__":
	main()
