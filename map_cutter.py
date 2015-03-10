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

		map_lines = str.splitlines(bytes.decode(map_bstring))

		start_entity = False
		in_entity = False

		start_brush = False
		in_brush = False

		start_patch = False
		in_patch = False

		self.entity_list = []

		# empty line
		empty_line_pattern = re.compile(r"^[ ]*$")

		# entity start
		# // entity num
		entity_start_pattern = re.compile(r"^[ ]*//[ ]+entity[ ]+(?P<entity_num>[0-9]*)[ ]*$")

		# block opening
		# {
		block_opening_pattern = re.compile(r"^[ ]*{[ ]*$")

		# keyvalue pair
		# "key" "value"
		keyvalue_pattern = re.compile(r"^[ ]*\"(?P<key>.*)\"[ ]+\"(?P<value>.*)\"[ ]*$")

		# brush start
		# // brush num
		brush_start_pattern = re.compile(r"^[ ]*//[ ]+brush[ ]+(?P<brush_num>[0-9]*)[ ]*$")

		# patch start
		# patchDef2
		patch_start_pattern = re.compile(r"^[ ]*patchDef2[ ]*$")

		# block ending
		# }
		block_ending_pattern = re.compile(r"^[ ]*}[ ]*$")

		# plane
		# coord, textures
		# (orig_x orig_y orig_z) (orig_x orig_y orig_z) (orig_x orig_y orig_z) shader shift_x shift_y rotation scale_x scale_y flags_content flags_surface value
		plane_pattern = re.compile(r"""
			[ ]*\([ ]+
			(?P<coord1_x>-*[0-9.]+)[ ]+
			(?P<coord1_y>-*[0-9.]+)[ ]+
			(?P<coord1_z>-*[0-9.]+)[ ]+
			\)[ ]+
			\([ ]+
			(?P<coord2_x>-*[0-9.]+)[ ]+
			(?P<coord2_y>-*[0-9.]+)[ ]+
			(?P<coord2_z>-*[0-9.]+)[ ]+
			\)[ ]+
			\([ ]+
			(?P<coord3_x>-*[0-9.]+)[ ]+
			(?P<coord3_y>-*[0-9.]+)[ ]+
			(?P<coord3_z>-*[0-9.]+)[ ]+
			\)[ ]+
			(?P<shader>[^ ]+)[ ]+
			(?P<shift_x>-*[0-9.]+)[ ]+
			(?P<shift_y>-*[0-9.]+)[ ]+
			(?P<scale_x>-*[0-9.]+)[ ]+
			(?P<scale_y>-*[0-9.]+)[ ]+
			(?P<rotation>-*[0-9.]+)[ ]+
			(?P<flag_content>[0-9]+)[ ]+
			(?P<flag_surface>[0-9]+)[ ]+
			(?P<value>[0-9]+)
			[ ]*
			""", re.VERBOSE)

		for line in map_lines:
			debug("reading: " + line)

			# Empty lines
			if empty_line_pattern.match(line):
				debug("Empty line")
				continue

			# Entity start
			if not in_entity:
				if not start_entity:
					match = entity_start_pattern.match(line)
					if match:
						entity_num = int(match.group("entity_num"))
						debug("Start Entity #" + str(entity_num))
						self.entity_list.append(Entity())
						start_entity = True
						continue

				# Entity opening
				if start_entity:
					if block_opening_pattern.match(line):
						debug("In Entity")
						start_entity = False
						in_entity = True
						continue

			if in_entity:

				# KeyValue pair
				match = keyvalue_pattern.match(line)
				if match and not start_brush and not in_brush and not start_patch and not in_patch:
					key = match.group("key")
					value = match.group("value")
					debug("KeyValue pair [“" + key + "”, “" + value + "”]")
					self.entity_list[-1].key_dict[key] = value
					continue

				# Brush start
				if not start_brush and not in_brush:
					match = brush_start_pattern.match(line)
					if match:
						brush_num = match.group("brush_num")
						debug("Start Brush #" + str(brush_num))
						self.entity_list[-1].brush_list.append(Brush())
						start_brush = True
						continue

				# Brush opening
				if start_brush and not in_brush and block_opening_pattern.match(line):
					debug("In Brush")
					start_brush = False
					in_brush = True
					continue

				# Patch start
				if in_brush and not start_patch and not in_patch and patch_start_pattern.match(line):
					debug("Start Patch")
					self.entity_list[-1].brush_list[-1].patch_list.append(Patch())
					start_patch = True
					continue
			
				# Patch opening
				if start_patch and not in_patch and block_opening_pattern.match(line):
					debug("In Patch")
					start_patch = False
					in_patch = True
					continue

				# Brush content
				if in_brush and not in_patch:
				
					# Plane content
					match = plane_pattern.match(line)
					if match:
						plane = OrderedDict()
						plane["coord1_x"] = match.group("coord1_x")
						plane["coord1_y"] = match.group("coord1_y")
						plane["coord1_z"] = match.group("coord1_z")
						plane["coord2_x"] = match.group("coord2_x")
						plane["coord2_y"] = match.group("coord2_y")
						plane["coord2_z"] = match.group("coord2_z")
						plane["coord3_x"] = match.group("coord3_x")
						plane["coord3_y"] = match.group("coord3_y")
						plane["coord3_z"] = match.group("coord3_z")
						plane["shader"] = match.group("shader")
						plane["shift_x"] = match.group("shift_x")
						plane["shift_y"] = match.group("shift_y")
						plane["scale_x"] = match.group("scale_x")
						plane["scale_y"] = match.group("scale_y")
						plane["rotation"] = match.group("rotation")
						plane["flag_content"] = match.group("flag_content")
						plane["flag_surface"] = match.group("flag_surface")
						plane["value"] = match.group("value")

						debug("Add plane to brush")
						self.entity_list[-1].brush_list[-1].plane_list.append(plane)
						continue

					# Brush End
					if block_ending_pattern.match(line):
						debug("End Brush")
						in_brush = False
						continue

				# Patch content
				if in_brush and in_patch:
					# Stub
					# vertexe: ( orig_x orig_y orig_z texcoord_x texcoord_y )
					if not block_ending_pattern.match(line):
						debug("Add line to patch")
						self.entity_list[-1].brush_list[-1].patch_list[-1].raw_line_list.append(line)
						continue

					# Patch End
					if block_ending_pattern.match(line):
						debug("End Patch")
						in_patch = False
						continue

				# Entity End
				if block_ending_pattern.match(line):
					debug("End Entity")
					in_entity = False
					continue

			# No match
			error("Unknown line: " + line)
			return False

		if len(self.entity_list) == 0:
			error("Empty file")
			self.entity_list = None
			return False

		return True


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
					for plane in brush.plane_list:
						map_string += "( " + plane["coord1_x"] + " " + plane["coord1_y"] + " " + plane["coord1_z"] + " ) "
						map_string += "( " + plane["coord2_x"] + " " + plane["coord2_y"] + " " + plane["coord2_z"] + " ) "
						map_string += "( " + plane["coord3_x"] + " " + plane["coord3_y"] + " " + plane["coord3_z"] + " ) "
						map_string += plane["shader"] + " "
						map_string += plane["shift_x"] + " " + plane["shift_y"] + " "
						map_string += plane["scale_x"] + " " + plane["scale_y"] + " "
						map_string += plane["rotation"] + " "
						map_string += plane["flag_content"] + " " + plane["flag_surface"] + " "
						map_string += plane["value"]
						map_string += "\n"
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

	def export_bsp_entities(self):
		if self.entity_list == None:
			error("No map loaded")

		map_string = ""

		for i in range(0, len(self.entity_list)):
			map_string += "{\n"
			if len(self.entity_list[i].key_dict) > 0:
				for key in self.entity_list[i].key_dict:
					map_string += "\"" + key + "\" \"" + self.entity_list[i].key_dict[key] + "\"" + "\n"
			map_string += "}\n"
		return map_string

	def print_map(self):
		print(self.export_map())

	def print_bsp_entities(self):
		print(self.export_bsp_entities())

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
		self.plane_list = []
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
	elif argv[0] == "print_bsp_entities":
		qmap.read_file(argv[1])
		qmap.print_bsp_entities()

if __name__ == "__main__":
	main(sys.argv[1:])
