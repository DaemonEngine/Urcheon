#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

import sys
import re

from collections import OrderedDict

import logging
from logging import debug, error
#logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


# http://forums.ubergames.net/topic/2658-understanding-the-quake-3-map-format/

class Map():
	def __init__(self):
		self.entity_list = None

	def read_file(self, file_name):
		map_file = open(file_name, "rb")

		map_bstring = map_file.read()
		map_file.close()

		map_lines = bytes.decode(map_bstring).splitlines()

		start_entity = False
		in_entity = False

		start_brush = False
		in_brush = False

		start_patch = False
		in_patch = False

		self.entity_list = []

		for line in map_lines:
			debug("reading: " + line)

			# Empty lines
			if re.search("^[ ]*$", line):
				debug("Empty line")
				None

			# Entity start
			elif re.search(r"^[ ]*//[ ]+entity[ ]+[0-9]*[ ]*$", line) and not start_entity and not in_entity:
				entity_num = int(re.sub(r"^[ ]*//[ ]+entity[ ]+([0-9]*)[ ]*$", r"\1", line))
				debug("Start Entity #" + str(entity_num))
				self.entity_list.append(Entity())
				start_entity = True

			# Entity opening
			elif re.search(r"^[ ]*{[ ]*$", line) and start_entity and not in_entity:
				debug("In Entity")
				start_entity = False
				in_entity = True

			# KeyValue pair
			elif re.search(r"^[ ]*\".*\"[ ]+\".*\"[ ]*$", line) and in_entity:
				key = re.sub(r"^[ ]*\"(.*)\"[ ]+\".*\"[ ]*$", r"\1", line)
				value = re.sub(r"^[ ]*\".*\"[ ]+\"(.*)\"[ ]*$", r"\1", line)
				debug("KeyValue pair [" + key + ", " + value + "]")
				self.entity_list[-1].key_dict[key] = value

			# Brush start
			elif re.search(r"^[ ]*//[ ]+brush[ ]+[0-9]*[ ]*$", line) and in_entity and not start_brush and not in_brush:
				brush_num = int(re.sub(r"^[ ]*//[ ]+brush[ ]+([0-9]*)[ ]*$", r"\1", line))
				debug("Start Brush #" + str(brush_num))
				self.entity_list[-1].brush_list.append(Brush())
				start_brush = True

			# Brush opening
			elif re.search(r"^[ ]*{[ ]*$", line) and start_brush and not in_brush:
				debug("In Brush")
				start_brush = False
				in_brush = True

			# Patch start
			elif re.search(r"^[ ]*patchDef2[ ]*$", line) and in_brush and not start_patch and not in_patch:
				debug("Start Patch")
				self.entity_list[-1].brush_list[-1].patch_list.append(Patch())
				start_patch = True
			
			# Patch opening
			elif re.search(r"^[ ]*{[ ]*$", line) and start_patch and not in_patch:
				debug("In Patch")
				start_patch = False
				in_patch = True

			# Block End
			elif re.search(r"^[ ]*}[ ]*$", line):

				# Patch End
				if in_brush and in_patch:
					debug("End Patch")
					in_patch = False

				# Brush End
				elif in_brush and not in_patch:
					debug("End Brush")
					in_brush = False

				# Entity End
				elif in_entity:
					debug("End Entity")
					in_entity = False

			# Patch content
			elif in_brush and in_patch:
				debug("Add line to patch")
				self.entity_list[-1].brush_list[-1].patch_list[-1].raw_line_list.append(line)

			# Brush content
			elif in_brush and not in_patch:
				debug("Add line to brush")
				self.entity_list[-1].brush_list[-1].raw_line_list.append(line)

			else:
				debug("Error, unknown line: " + line)

		if len(self.entity_list) == 0:
			error("Empty file")
			self.entity_list = None

	def export_map(self):
		if self.entity_list == None:
			error("No map loaded")

		map_string = ""
		brush_count = 0

		for i in range(0, len(self.entity_list)):
			map_string += "// entity " + str(i) + "\n"
			map_string += "{\n"
			if len(self.entity_list[i].key_dict) > 0:
				for key in self.entity_list[i].key_dict:
					map_string += "\"" + key + "\" \"" + self.entity_list[i].key_dict[key] + "\"" + "\n"
			if len(self.entity_list[i].brush_list) > 0:
				for brush in self.entity_list[i].brush_list:
					map_string += "// brush " + str(brush_count) + "\n"
					map_string += "{\n"
					for line in brush.raw_line_list:
						map_string += line + "\n"
					for patch in brush.patch_list:
						map_string += "patchDef2\n"
						map_string += "{\n"
						for line in patch.raw_line_list:
							map_string += line + "\n"
						map_string += "}\n"
					map_string += "}\n"
					brush_count += 1
			map_string += "}\n"

			return map_string

	def print_map(self):
		print(self.export_map())

	def write_file(self, file_name):
		map_file = open(file_name, 'wb')
		map_file.write(self.export_map().encode())
		map_file.close
			

class Entity():
	def __init__(self):
		self.key_dict = OrderedDict()
		self.brush_list = []

class Brush():
	def __init__(self):
		self.raw_line_list = []
		self.patch_list = []

class Patch():
	def __init__(self):
		self.raw_line_list = []

def main(argv):
	qmap = Map()

	if len(argv) == 0:
		print("ERR: missing command")
		return False
	elif len(argv) == 1:
		print("ERR: missing filename")
		return False

	if argv[0] == "rewrite_map":
		qmap.read_file(argv[1])
		qmap.write_file(argv[1] + ".new")
	elif argv[0] == "print_map":
		qmap.read_file(argv[1])
		qmap.print_map()

if __name__ == "__main__":
	main(sys.argv[1:])
