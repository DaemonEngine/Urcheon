#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import os
import struct
import sys
import re
import argparse
import logging
import glob
from logging import debug, error
from collections import OrderedDict
from PIL import Image


# see http://www.mralligator.com/q3/
lump_name_list = [
	"entities",
	"textures",
	"planes",
	"nodes",
	"leafs",
	"leaffaces",
	"leafbrushes",
	"models",
	"brushes",
	"brushsides",
	"vertexes",
	"meshverts",
	"effects",
	"faces",
	"lightmaps",
	"lightvols",
	"visdata",
]

# see https://github.com/Unvanquished/Unvanquished/blob/master/src/gamelogic/game/g_spawn.cpp
sound_keyword_list = [
	"noise",
	"sound1to2",
	"sound2to1",
	"soundPos1",
	"soundPos2",
]

# only one version supported at this time
bsp_version = 46
bsp_magic_number = b"IBSP"

class Entities():
	def __init__(self):
		self.entity_list = None

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

	def printString(self):
		print("*** Entities")
		print(bytes.decode(self.exportLump().split(b'\0', 1)[0]))
		print("")

	def printList(self):
		print("*** Entities")
		for i in range(0, len(self.entity_list)):
			string = ""
			for keyword in self.entity_list[i].keys():
				string += '\"' + keyword + "\": \"" + self.entity_list[i][keyword] + "\", "
			print(str(i) + ": [" + string[:-2] + "]")
		print("")
		return True

	def printSoundList(self):
		print("*** Sounds:")
		i = 0
		for entity in self.entity_list:
			for entity_keyword in entity.keys():
				for sound_keyword in sound_keyword_list:
					if entity_keyword.lower() == sound_keyword.lower():
						print(str(i) + ": " + entity[entity_keyword] + " [" + entity_keyword + "]")
						i += 1
		print("")
		return True

	# TODO: sanitize input
	# s/^[ \t]*{[ \t]*$/{/
	# s/^[ \t]*}[ \t]*$/{/
	# s/^[ \t]*"\(.*\)"[ \t]+[ \t]*"\(.*\)"[ \t]*$/"\1" "\2"/

	def importLump(self, blob):
		self.entity_list = []
		entities_bstring = blob.split(b'\0', 1)[0]
		for almost_entity in entities_bstring.split(b"{\n")[1:]:
			entity = almost_entity.split(b'\n}')[:-1][0]
			entity_dict = OrderedDict()
			for line in entity.split(b'\n'):
				almost_keyword, almost_value = line.split(b"\" \"")
				keyword = bytes.decode(almost_keyword.split(b'\"')[1:2][0])
				value = bytes.decode(almost_value.split(b'\"')[0:1][0])
				# TODO: do not use a dictionary in the future: each time we write down the entities the order change
				entity_dict[keyword] = value
			self.entity_list.append(entity_dict)

	def exportLump(self):
		blob = b''

		for entity in self.entity_list:
			blob += b'{\n'
			for keyword in entity.keys():
				blob += b'\"' + str.encode(keyword) + b"\" \"" + str.encode(entity[keyword]) + b"\"\n"
			blob += b'}\n'

		blob += b'\0'		
		return blob


class Textures():
	def __init__(self):
		self.texture_list = None

	def int2bstr(self, i):
		return "{0:b}".format(i).zfill(30)

	def bstr2int(self, s):
		return int(s, 2)

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

	def printList(self):
		# TODO: check

		print("*** Textures:")
		for i in range(0, len(self.texture_list)):
			print(str(i) + ": " + self.texture_list[i]["name"] + " [" + self.int2bstr(self.texture_list[i]["flags"]) + ", " + self.int2bstr(self.texture_list[i]["contents"]) + "]")
		print("")

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


class Lightmaps():
	def __init__(self):
		self.lightmap_list = []

	def printList(self):
		print("*** Lightmaps:")
		for i in range(0, len(self.lightmap_list)):
			print("#" + str(i) + ": [128x128x24, RGB, " + str(len(self.lightmap_list[i])) + "]")
		print("")
		return True

	def readDir(self, dir_name):
		# TODO: check if a dir, perhaps argparse can do
		self.lightmap_list = []
		file_list = sorted(glob.glob(dir_name + os.path.sep + "lm_*" + os.path.extsep + "*"))
		for file_name in file_list:
			debug("loading lightmap: " + file_name)
			image = Image.open(file_name)
			lightmap = image.convert("RGB").tobytes()

			# 49152: Lightmap size (128x128x3 bytes)
			# 128: Number of lines
			# 3: Bytes per pixels
			# 384: Lightmap line size (128x3 bytes)

			if int(len(lightmap) != 49152):
				error("bad file, must be a 128x128x3 picture")

			self.lightmap_list.append(lightmap)

	def writeDir(self, dir_name):
		if not os.path.exists(dir_name):
			os.makedirs(dir_name)

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
			# 2: Width (128)
			# 2: Height (128)
			header += b'\x80\0\x80\0'
			# 2: Bits per pixels (24)
			# 2: Attribute bits (0 for 24)
			header += b'\x18\0'
			header += b'Granger loves you\0'

			raw = self.lightmap_list[i]

			# 49152: Size (128x128x3 bytes)
			# 384: Line size (128x3 bytes)
			# 3: Bits per pixels

			data = b''
			# Last line is first line
			for j in range(0, 49152, 384):
				line = raw[49152 - 384 - j : 49152 - j]

				# RGB → BGR
				for k in range(0, 384, 3):
					data += line[k : k + 3][::-1]

			debug("header length: " + str(len(header)))
			debug("data length: " + str(len(data)))

			blob = header + data

			lightmap_file.write(blob)
			lightmap_file.close()

	def importLump(self, blob):
		self.lightmap_list = []
		# 49152: Size (128x128x3 bytes)
		lightmap_size = 49152
		lump_count = int(len(blob) / lightmap_size)

		for i in range(0, lump_count):
			self.lightmap_list.append(blob[i * lightmap_size:(i + 1) * lightmap_size])
		return True

	def exportLump(self):
		blob = b''
		# TODO: better
		for i in range(0, len(self.lightmap_list)):
			blob += self.lightmap_list[i]

		return blob

class Bsp():
	def __init__(self):
		self.bsp_file = None
		self.bsp_file_name = None

		# only one version supported for the moment
		self.bsp_version = bsp_version

		# metadata for printing purpose
		self.lump_directory = None
		self.sound_list = None

		# lumps are stored here
		self.lump_dict = {}
		for lump_name in lump_name_list:
			self.lump_dict[lump_name] = b""

	def readFile(self, bsp_file_name):
		# TODO: check
		self.bsp_file_name = bsp_file_name
		self.bsp_file = open(self.bsp_file_name, 'rb')

		if self.bsp_file.read(4) != bsp_magic_number:
			print("ERR: bad file format")
			self.bsp_file.close()
			self.bsp_file = None
			return False

		self.bsp_file.seek(4)
		self.bsp_version, = struct.unpack('<I', self.bsp_file.read(4))
		if self.bsp_version != bsp_version:
			print("ERR: Unknown BSP version")
			self.bsp_file.close()
			self.bsp_file = None
			return False

		if not self.readLumpList():
			print("ERR: Can't read lump list")
			return False

		for lump_name in lump_name_list:
			if not self.readLump(lump_name):
				print("ERR: Can't read lump: " + lump_name)
				return False

		self.bsp_file.close()
		return True

	def readDir(self, dir_name):
		# TODO: check if a dir, perhaps argparse can do
		for lump_name in lump_name_list:
			file_list = glob.glob(dir_name + os.path.sep + lump_name + os.path.extsep + "*")

			if len(file_list) > 1:
				error("more than one " + lump_name + " lump in bspdir")
				# TODO: handling
				return
			if len(file_list) == 0:
				# TODO: warning?
				continue

			file_path = file_list[0]
			file_ext = os.path.splitext(file_path)[-1][1:]
			file_name = os.path.splitext(os.path.basename(file_path))[0]

			if file_ext == "bin":
				if file_name in lump_name_list:
					lump_file = open(file_path, "rb")
					self.lump_dict[file_name] = lump_file.read()
				else:
					error("unknown lump format: " + filename)
					return

			elif file_ext == "csv":
				if file_name == "textures":
					textures = Textures()
					textures.readFile(file_path)
					self.lump_dict[file_name] = textures.exportLump()
				else:
					error("unknown lump format: " + file_path)
					return

			elif file_ext == "txt":
				if file_name == "entities":
					entities = Entities()
					entities.readFile(file_path)
					self.lump_dict[file_name] = entities.exportLump()
				else:
					error("unknown lump format: " + file_path)
					return

			elif file_ext == "d":
				if file_name == "lightmaps":
					lightmaps = Lightmaps()
					lightmaps.readDir(file_path)
					self.lump_dict[file_name] = lightmaps.exportLump()
				else:
					error("unknown lump format: " + file_path)
					return

			else:
				error("unknown lump format: " + file_path)
				return

	def printFileName(self):
		print("*** File:")
		print(self.bsp_file_name)
		print("")

	def readLumpList(self):
		if (self.lump_directory != None):
			return False

		self.lump_directory = {}

		# TODO: check

		for lump_name in lump_name_list:
			# 4 bytes string magic number (IBSP)
			# 4 bytes integer version
			# 4 bytes integer lump offset
			# 4 bytes integer lump size
			self.bsp_file.seek(8 + (lump_name_list.index(lump_name) * 8))

			self.lump_directory[lump_name] = {}

			self.lump_directory[lump_name]["offset"], self.lump_directory[lump_name]["length"] = struct.unpack('<II', self.bsp_file.read(8))
			self.lump_dict[lump_name] = None

		return True

	def printLumpList(self):
		# TODO: check

		print("*** Lumps:")
		for i in range(0, len(lump_name_list)):
			lump_name = lump_name_list[i]
			print(str(i) + ": " + lump_name + " [" + str(self.lump_directory[lump_name]["offset"]) + ", " + str(self.lump_directory[lump_name]["length"]) + "]")
		print("")

	def readLump(self, lump_name):
		# TODO: check

		# 4 bytes string magic number (IBSP)
		# 4 bytes integer version
		# 4 bytes integer lump offset
		# 4 bytes integer lump size
		self.bsp_file.seek(8 + (lump_name_list.index(lump_name) * 8))
		offset, length = struct.unpack('<II', self.bsp_file.read(8))

		self.bsp_file.seek(offset)
		self.lump_dict[lump_name] = self.bsp_file.read(length)

		return True


	def writeFile(self, bsp_file_name):
		bsp_file = open(bsp_file_name, "wb")

		# Must be a multiple of 4
		metadata_blob = b'Granger loves you!\0\0'

		lumps_blob = b''
		directory_blob = b''

		# 4 bytes string magic number (IBSP)
		# 4 bytes integer version
		# 4 bytes integer lump offset per lump
		# 4 bytes integer lump size per lump
		# 17 lumps + 1 extra empty lump (Quake Live advertisements)

		lump_start = 152 + len(metadata_blob)
		for lump_name in lump_name_list:
			lump_length = len(self.lump_dict[lump_name])
			print(str(lump_name_list.index(lump_name)) + ": " + lump_name + " [" + str(lump_start) + ", " + str(lump_length) + "]")
			directory_blob += lump_start.to_bytes(4, "little")
			directory_blob += lump_length.to_bytes(4, "little")
			lump_start += lump_length

			lumps_blob += self.lump_dict[lump_name]

			# Align lump to 4 bytes
			# For reference, q3map2 does not count these extra bytes in lump length
			# This happen for entities string for example
			if (lump_length % 4 != 0):
				for missing_byte in range(0, 4 - (lump_length % 4)):
					lumps_blob += b'\0'
					lump_start += 1

		# extra empty lump
		directory_blob += lump_start.to_bytes(4, "little") + b"\0\0\0\0"

		blob = bsp_magic_number
		blob += self.bsp_version.to_bytes(4, "little")
		blob += directory_blob
		blob += metadata_blob
		blob += lumps_blob

		bsp_file.write(blob)
		bsp_file.close()

	def writeDir(self, dir_name):
		if not os.path.exists(dir_name):
			os.makedirs(dir_name)

		for entity in lump_name_list:
			if entity == "entities":
				entities = Entities()
				entities.importLump(self.lump_dict["entities"])
				entities.writeFile(dir_name + os.path.sep + "entities" + os.path.extsep + "txt")
			elif entity == "textures":
				textures = Textures()
				textures.importLump(self.lump_dict["textures"])
				textures.writeFile(dir_name + os.path.sep + "textures" + os.path.extsep + "csv")
			elif entity == "lightmaps":
				lightmaps = Lightmaps()
				lightmaps.importLump(self.lump_dict["lightmaps"])
				lightmaps.writeDir(dir_name + os.path.sep + "lightmaps" + os.path.extsep + "d")
			else:
				blob_file = open(dir_name + os.path.sep + entity + os.path.extsep + "bin", "wb")
				blob_file.write(self.lump_dict[entity])
				blob_file.close()

	def importLump(self, lump_name, blob):
		self.lump_dict[lump_name] = blob

	def exportLump(self, lump_name):
		return self.lump_dict[lump_name]

def main(argv):
	# TODO: check files

	args = argparse.ArgumentParser(description="%(prog)s is a BSP parser for my lovely granger.")
	args.add_argument("-D", "--debug", help="print debug information", action="store_true")
	args.add_argument("-ib", "--input-bsp", dest="input_bsp_file", metavar="FILENAME",  help="read from .bsp file %(metavar)s")
	args.add_argument("-id", "--input-bsp-dir", dest="input_bsp_dir", metavar="DIRNAME", help="read from .bspdir directory %(metavar)s")
	args.add_argument("-ob", "--output-bsp", dest="output_bsp_file", metavar="FILENAME", help="write to .bsp file %(metavar)s")
	args.add_argument("-od", "--output-bsp-dir", dest="output_bsp_dir", metavar="DIRNAME", help="write to .bspdir directory %(metavar)s")
	args.add_argument("-ie", "--input-entities", dest="input_entities_file", metavar="FILENAME",  help="read from entities .txt file %(metavar)s")
	args.add_argument("-oe", "--output-entities", dest="output_entities_file", metavar="FILENAME", help="write to entities .txt file %(metavar)s")
	args.add_argument("-it", "--input-textures", dest="input_textures_file", metavar="FILENAME",  help="read rom textures .csv file %(metavar)s")
	args.add_argument("-ot", "--output-textures", dest="output_textures_file", metavar="FILENAME", help="write to textures .csv file %(metavar)s")
	args.add_argument("-il", "--input-lightmaps", dest="input_lightmaps_dir", metavar="DIRNAME",  help="read from lightmaps directory %(metavar)s")
	args.add_argument("-ol", "--output-lightmaps", dest="output_lightmaps_dir", metavar="DIRNAME", help="write to lightmaps directory %(metavar)s")
	args.add_argument("-sl", "--strip-lightmaps", help="empty the lightmap lump", action="store_true")
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

	bsp = None
	entities = None
	textures = None
	lightmaps = None

	if args.input_bsp_file:
		bsp = Bsp()
		bsp.readFile(args.input_bsp_file)
		entities = Entities()
		entities.importLump(bsp.exportLump("entities"))
		textures = Textures()
		textures.importLump(bsp.exportLump("textures"))
		lightmaps = Lightmaps()
		lightmaps.importLump(bsp.exportLump("lightmaps"))

	if args.input_bsp_dir:
		bsp = Bsp()
		bsp.readDir(args.input_bsp_dir)

	if args.input_entities_file:
		entities = Entities()
		entities.readFile(args.input_entities_file)

	if args.input_textures_file:
		textures = Textures()
		textures.readFile(args.input_textures_file)

	if args.input_lightmaps_dir:
		lightmaps = Lightmaps()
		lightmaps.readDir(args.input_lightmaps_dir)

	# TODO: perhaps it must conflict with input_lightmaps_file
	if args.strip_lightmaps:
		lightmaps = Lightmaps()
	#	lightmaps.importLump(b'')

	if args.output_bsp_file:
		if lightmaps:
			bsp.importLump("lightmaps", lightmaps.exportLump())
		if entities:
			bsp.importLump("entities", entities.exportLump())
		if textures:
			bsp.importLump("textures", textures.exportLump())
		bsp.writeFile(args.output_bsp_file)

	if args.output_bsp_dir:
		if lightmaps:
			bsp.importLump("lightmaps", lightmaps.exportLump())
		if entities:
			bsp.importLump("entities", entities.exportLump())
		if textures:
			bsp.importLump("textures", textures.exportLump())
		bsp.writeDir(args.output_bsp_dir)

	if args.output_entities_file:
		if entities:
			entities.writeFile(args.output_entities_file)
		else:
			debug("TODO: ERR: no entities lump loaded")

	if args.output_textures_file:
		if textures:
			textures.writeFile(args.output_textures_file)
		else:
			debug("TODO: ERR: no textures lump loaded")

	if args.output_lightmaps_dir:
		if lightmaps:
			lightmaps.writeDir(args.output_lightmaps_dir)

	if args.list_all:
		if bsp:
			args.list_lumps = True
			args.list_entities = True
			args.list_textures = True
			args.list_lightmaps = True
			args.list_sounds = True

		if entities:
			args.list_entities = True
			args.list_sounds = True

		if textures:
			args.list_textures = True

		if lightmaps:
			args.list_lightmaps = True

	if args.list_lumps:
		if bsp:
			bsp.printLumpList()
		else:
			error("BSP file missing")

	if args.list_entities:
		if entities:
			entities.printList()
		else:
			error("Entities lump missing")

	if args.list_textures:
		if textures:
			textures.printList()
		else:
			error("Textures lump missing")

	if args.list_lightmaps:
		if lightmaps:
			lightmaps.printList()
		else:
			error("Lightmaps lump missing")

	if args.list_sounds:
		if entities:
			entities.printSoundList()
		else:
			error("Entities lump missing")

	if args.print_entities:
		if entities:
			entities.printString()
		else:
			error("Entities lump missing")


if __name__ == "__main__":
	main(sys.argv[1:])
