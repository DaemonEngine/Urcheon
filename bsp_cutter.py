#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import struct
import re
import sys
import os

# see http://www.mralligator.com/q3/
lump_name_list = [
	"Entities",
	"Textures",
	"Planes",
	"Nodes",
	"Leafs",
	"Leaffaces",
	"Leafbrushes",
	"Models",
	"Brushes",
	"Brushsides",
	"Vertexes",
	"Meshverts",
	"Effects",
	"Faces",
	"Lightmaps",
	"Lightvols",
	"Visdata",
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
		for i in range(0, len(self.entity_list)):
			string = ""
			for keyword in self.entity_list[i].keys():
				string += '\"' + keyword + "\": \"" + self.entity_list[i][keyword] + "\", "
			print(str(i) + ": [" + string[:-2] + "]")
		return True

	def print_sounds_list(self):
		print("*** Sounds")
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
			entity_dict = {}
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
		textures_file = open(file_name, 'wb')
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
	def __init_(self):
		self.ligthmap_list = None


	def list_lightmaps(self):
		print("*** Lightmaps:")
		for i in range(0, len(self.lightmap_list)):
			print("#" + str(i) + ": [128x128x24, RGB, " + str(len(self.lightmap_list[i])) + "]")
		print("")
		return True

	def write_dir(self, dir_name):
		if not os.path.exists(dir_name):
		    os.makedirs(dir_name)

		for i in range(0, len(self.lightmap_list)):
			file_name = "lm_" + str(i).zfill(4) + ".tga"

			# TODO: os independent:
			file_path = dir_name + "/" + file_name
			# TODO: check
			lightmap_file = open(file_path, 'wb')

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
			header += b'\x18\0\0\0'
			header += b'Granger loves you\0'

			blob = header + self.lightmap_list[i]

			lightmap_file.write(blob)
			lightmap_file.close()

	def import_lump(self, blob):
		# 128*128*3
		lightmap_size = 49152
		lump_count = int(len(blob) / lightmap_size)

		self.lightmap_list = []
		for i in range(0, lump_count):
			self.lightmap_list.append(blob[i * lightmap_size:(i + 1) * lightmap_size])
		return True

	def export_lump(self):
		# STUB
		return False

class BSP():
	def __init__(self):
		self.bsp_file = None
		self.bsp_file_name = None

		# only one version supported for the moment
		self.bsp_version = bsp_version

		self.lump_directory = None
		self.sound_list = None

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
		bsp_file = open(bsp_file_name, 'wb')

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
		directory_blob += lump_start.to_bytes(4, "little") + b'\0\0\0\0'

		blob = bsp_magic_number
		blob += self.bsp_version.to_bytes(4, "little")
		blob += directory_blob
		blob += metadata_blob
		blob += lumps_blob
		
		bsp_file.write(blob)
		bsp_file.close()

	def import_lump(self, lump_name, blob):
		self.lump_dict[lump_name] = blob

	def export_lump(self, lump_name):
		return self.lump_dict[lump_name]

def main(argv):
	bsp = BSP()
	textures = Textures()
	entities = Entities()
	lightmaps = Lightmaps()

	# CLI Proof of concept

	# TODO: rewrite all this part
	# TODO: check files

	if len(argv) == 0:
		print("ERR: missing command")
		return False
	elif len(argv) == 1:
		print("ERR: missing filename")
		return False

	if argv[0] == "list_lumps":
		if bsp.read_file(argv[1]):
			if bsp.print_lump_list():
				return True
		return False
	elif argv[0] == "print_entities":
		if bsp.read_file(argv[1]):
			entities.import_lump(bsp.export_lump("Entities"))
			if entities.print_string():
				return True
		return False
	elif argv[0] == "list_entities":
		if bsp.read_file(argv[1]):
			entities.import_lump(bsp.export_lump("Entities"))
			if entities.print_list():
				return True
		return False
	elif argv[0] == "list_sounds":
		if bsp.read_file(argv[1]):
			entities.import_lump(bsp.export_lump("Entities"))
			if entities.print_sounds_list():
				return True
		return False
	elif argv[0] == "list_textures":
		if bsp.read_file(argv[1]):
			textures.import_lump(bsp.export_lump("Textures"))
			if textures.print_list():
				return True
		return False
	elif argv[0] == "list_lightmaps":
		if bsp.read_file(argv[1]):
			if lightmaps.import_lump(bsp.export_lump("Lightmaps")):
				lightmaps.list_lightmaps()
				return True
		return False
	elif argv[0] == "print_all":
		if bsp.read_file(argv[1]):
			bsp.print_file_name()
			bsp.print_lump_list()
			entities.import_lump(bsp.export_lump("Entities"))
			entities.print_string()
			textures.import_lump(bsp.export_lump("Textures"))
			textures.print_list()
			return True
		return False
	elif argv[0] == "dump_entities":
		if bsp.read_file(argv[1]):
			entities.import_lump(bsp.export_lump("Entities"))
			if entities.write_file(argv[1].split(".bsp")[0] + ".entities"):
				return True
		return False
	elif argv[0] == "dump_textures":
		if bsp.read_file(argv[1]):
			textures.import_lump(bsp.export_lump("Textures"))
			if textures.write_file(argv[1].split(".bsp")[0] + ".textures"):
				return True
		return False
	elif argv[0] == "dump_lightmaps":
		if bsp.read_file(argv[1]):
			lightmaps.import_lump(bsp.export_lump("Lightmaps"))
			if lightmaps.write_dir(argv[1].split(".bsp")[0]):
				return True
		return False
	elif argv[0] == "patch_entities":
		if bsp.read_file(argv[1]):
			if entities.read_file(argv[1].split(".bsp")[0] + ".entities"):
				bsp.import_lump("Entities", entities.export_lump())
				if bsp.write_file(argv[1]):
					return True
		return False
	elif argv[0] == "patch_textures":
		# TODO: verify number of lines in textures list
		if bsp.read_file(argv[1]):
			if textures.read_file(argv[1].split(".bsp")[0] + ".textures"):
				bsp.import_lump("Textures", textures.export_lump())
				if bsp.write_file(argv[1]):
					return True
		return False
	else:
		print("ERR: Unknown command")
		return False

if __name__ == "__main__":
	main(sys.argv[1:])
