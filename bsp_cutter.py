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

	def read_file(self, file_name):
		entities_file = open(file_name, "rb")
		self.import_lump(entities_file.read())
		entities_file.close()
		return True

	def write_file(self, file_name):
		entities_file = open(file_name, "wb")
		entities_file.write(self.export_lump().split(b'\0', 1)[0])
		entities_file.close()
		return True

	def print_string(self):
		print("*** Entities")
		print(bytes.decode(self.export_lump().split(b'\0', 1)[0]))
		print("")

	def print_list(self):
		print("*** Entities")
		for i in range(0, len(self.entity_list)):
			string = ""
			for keyword in self.entity_list[i].keys():
				string += '\"' + keyword + "\": \"" + self.entity_list[i][keyword] + "\", "
			print(str(i) + ": [" + string[:-2] + "]")
		print("")
		return True

	def print_sound_list(self):
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

	def import_lump(self, blob):
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

	def export_lump(self):
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

	def read_file(self, file_name):
		# TODO: check
		textures_file = open(file_name, 'rb')

		textures_file_bstring = textures_file.read()
		self.texture_list = []

		for texture_line_bstring in textures_file_bstring.split(b'\n'):
			# TODO: check 3 comma minimum
			# TODO: allow string path with comma
			if texture_line_bstring != b'':
				bstring_list = texture_line_bstring.split(b',')
				flags = int(bstring_list[0])
				contents = int(bstring_list[1])
				name = bytes.decode(bstring_list[2])
				self.texture_list.append({"name": name, "flags": flags, "contents": contents})

		textures_file.close()

		return True

	def write_file(self, file_name):

		textures_string = ""
		for i in range(0, len(self.texture_list)):
			textures_string += str(self.texture_list[i]["flags"]) + ","
			textures_string += str(self.texture_list[i]["contents"]) + ","
			textures_string += self.texture_list[i]["name"] + "\n"

		# TODO: check
		textures_file = open(file_name, "wb")
		textures_file.write(textures_string.encode())
		textures_file.close()

	def print_list(self):
		# TODO: check

		print("*** Textures:")
		for i in range(0, len(self.texture_list)):
			print(str(i) + ": " + self.texture_list[i]["name"] + " [" + str(self.texture_list[i]["flags"]) + ", " + str(self.texture_list[i]["contents"]) + "]")
		print("")

	def import_lump(self, blob):
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


	def export_lump(self):
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

	def print_list(self):
		print("*** Lightmaps:")
		for i in range(0, len(self.lightmap_list)):
			print("#" + str(i) + ": [128x128x24, RGB, " + str(len(self.lightmap_list[i])) + "]")
		print("")
		return True

	def read_dir(self, dir_name):
		self.lightmap_list = []
		file_list = sorted(glob.glob(dir_name + "/lm_*.tga"))
		for file_name in file_list:
			debug("loading lightmap: " + file_name)
			image = Image.open(file_name)
			lightmap = image.convert("RGB").tostring()

			# 49152: Size (128x128x3 bits)
			# 128: Lines
			# 3: Bits per pixels
			# lightmap_size = 49152		# 128*128*3
			# lightmap_line_size = 384	# 128*3
			# lightmap_num_lines = 128

			if int(len(lightmap) != 49152):
				error("bad file, must be a 128x128x3 picture")

			self.lightmap_list.append(lightmap)

	def write_dir(self, dir_name):
		if not os.path.exists(dir_name):
		    os.makedirs(dir_name)

		for i in range(0, len(self.lightmap_list)):
			file_name = "lm_" + str(i).zfill(4) + ".tga"

			# TODO: os independent:
			file_path = dir_name + "/" + file_name
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

			# 49152: Size (128x128x3 bits)
			# 384: Line size (128x3 bits)
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

	def import_lump(self, blob):
		self.lightmap_list = []
		# 59152: Size (128x128x83 bits)
		lightmap_size = 49152
		lump_count = int(len(blob) / lightmap_size)

		for i in range(0, lump_count):
			self.lightmap_list.append(blob[i * lightmap_size:(i + 1) * lightmap_size])
		return True

	def export_lump(self):
		blob = b''
		# TODO: better
		for i in range(0, len(self.lightmap_list)):
			blob += self.lightmap_list[i]

		return blob

class BSP():
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
			self.lump_dict[lump_name] = None

	def read_file(self, bsp_file_name):
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

		if not self.read_lump_list():
			print("ERR: Can't read lump list")
			return False

		for lump_name in lump_name_list:
			if not self.read_lump(lump_name):
				print("ERR: Can't read lump: " + lump_name)
				return False

		self.bsp_file.close()
		return True

	def print_file_name(self):
		print("*** File:")
		print(self.bsp_file_name)
		print("")

	def read_lump_list(self):
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
	
	def print_lump_list(self):
		# TODO: check

		print("*** Lumps:")
		for i in range(0, len(lump_name_list)):
			lump_name = lump_name_list[i]
			print(str(i) + ": " + lump_name + " [" + str(self.lump_directory[lump_name]["offset"]) + ", " + str(self.lump_directory[lump_name]["length"]) + "]")
		print("")

	def read_lump(self, lump_name):
		if (self.lump_dict[lump_name] != None):
			return False

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


	def write_file(self, bsp_file_name):
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

	def write_dir(self, dir_name):
		if not os.path.exists(dir_name):
		    os.makedirs(dir_name)

		for entity in lump_name_list:
			if entity == "entities":
				entities = Entities()
				entities.import_lump(self.lump_dict["entities"])
				# TODO: sanitize '/'
				entities.write_file(dir_name + "/entities.txt")
			elif entity == "textures":
				textures = Textures()
				textures.import_lump(self.lump_dict["textures"])
				textures.write_file(dir_name + "/textures.csv")
			elif entity == "lightmaps":
				lightmaps = Lightmaps()
				lightmaps.import_lump(self.lump_dict["lightmaps"])
				lightmaps.write_dir(dir_name + "/lightmaps.d")
			else:
				blob_file = open(dir_name + '/' + entity + ".bin", "wb")
				blob_file.write(self.lump_dict[entity])
				blob_file.close()

	def import_lump(self, lump_name, blob):
		self.lump_dict[lump_name] = blob

	def export_lump(self, lump_name):
		return self.lump_dict[lump_name]

def main(argv):
	# TODO: check files

	args = argparse.ArgumentParser(description="%(prog)s is a BSP parser for my lovely granger.")
	args.add_argument("-D", "--debug", help="print debug information", action="store_true")
	args.add_argument("-ib", "--input-bsp", dest="input_bsp_file", metavar="FILENAME",  help="read from .bsp file %(metavar)s")
#	args.add_argument("-id", "--input-bsp-dir", dest="input_bsp_dir", metavar="DIRNAME", help="read from .bspdir directory %(metavar)s")
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
		bsp = BSP()
		bsp.read_file(args.input_bsp_file)
		entities = Entities()
		entities.import_lump(bsp.export_lump("entities"))
		textures = Textures()
		textures.import_lump(bsp.export_lump("textures"))
		lightmaps = Lightmaps()
		lightmaps.import_lump(bsp.export_lump("lightmaps"))

	if args.input_bsp_dir:
		bsp = BSP()
		bsp.read_dir(args.input_bsp_dir)

	if args.input_entities_file:
		entities = Entities()
		entities.read_file(args.input_entities_file)

	if args.input_textures_file:
		textures = Textures()
		textures.read_file(args.input_textures_file)

	if args.input_lightmaps_dir:
		lightmaps = Lightmaps()
		lightmaps.read_dir(args.input_lightmaps_dir)

	# TODO: perhaps it must conflict with input_lightmaps_file
	if args.strip_lightmaps:
		lightmaps = Lightmaps()
	#	lightmaps.import_lump(b'')

	if args.output_bsp_file:
		if lightmaps:
			bsp.import_lump("lightmaps", lightmaps.export_lump())
		if entities:
			bsp.import_lump("entities", entities.export_lump())
		if textures:
			bsp.import_lump("textures", textures.export_lump())
		bsp.write_file(args.output_bsp_file)

	if args.output_bsp_dir:
		if lightmaps:
			bsp.import_lump("lightmaps", lightmaps.export_lump())
		if entities:
			bsp.import_lump("entities", entities.export_lump())
		if textures:
			bsp.import_lump("textures", textures.export_lump())
		bsp.write_dir(args.output_bsp_dir)

	if args.output_entities_file:
		if entities:
			entities.write_file(args.output_entities_file)
		else:
			debug("TODO: ERR: no entities lump loaded")

	if args.output_textures_file:
		if textures:
			textures.write_file(args.output_textures_file)
		else:
			debug("TODO: ERR: no textures lump loaded")

	if args.output_lightmaps_dir:
		if lightmaps:
			lightmaps.write_dir(args.output_lightmaps_dir)

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
			bsp.print_lump_list()
		else:
			error("BSP file missing")

	if args.list_entities:
		if entities:
			entities.print_list()
		else:
			error("Entities lump missing")

	if args.list_textures:
		if textures:
			textures.print_list()
		else:
			error("Textures lump missing")

	if args.list_lightmaps:
		if lightmaps:
			lightmaps.print_list()
		else:
			error("Lightmaps lump missing")

	if args.list_sounds:
		if entities:
			entities.print_sound_list()
		else:
			error("Entities lump missing")

	if args.print_entities:
		if entities:
			entities.print_string()
		else:
			error("Entities lump missing")


if __name__ == "__main__":
	main(sys.argv[1:])
