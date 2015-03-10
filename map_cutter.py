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

		start_shape = False
		in_shape = False

		in_brush = False

		start_patch = False
		in_patch = False

		in_shader = False

		start_matrix = False
		in_matrix = False

		self.entity_list = []

		# empty line
		empty_line_pattern = re.compile(r"^[ \t]*$")

		# entity start
		# // entity num
		entity_start_pattern = re.compile(r"^[ \t]*//[ \t]+entity[ \t]+(?P<entity_num>[0-9]+)[ \t]*$")

		# block opening
		# {
		block_opening_pattern = re.compile(r"^[ \t]*{[ \t]*$")

		# keyvalue pair
		# "key" "value"
		keyvalue_pattern = re.compile(r"^[ \t]*\"(?P<key>.*)\"[ \t]+\"(?P<value>.*)\"[ \t]*$")

		# shape start
		# // brush num
		shape_start_pattern = re.compile(r"^[ \t]*//[ \t]+brush[ \t]+(?P<brush_num>[0-9]+)[ \t]*$")

		# plane line
		# coord, textures
		# (orig_x orig_y orig_z) (orig_x orig_y orig_z) (orig_x orig_y orig_z) shader shift_x shift_y rotation scale_x scale_y flags_content flags_surface value
		plane_pattern = re.compile(r"""
			[ \t]*\([ \t]+
			(?P<coord0_x>-?[0-9.]+)[ \t]+
			(?P<coord0_y>-?[0-9.]+)[ \t]+
			(?P<coord0_z>-?[0-9.]+)[ \t]+
			\)[ \t]+
			\([ \t]+
			(?P<coord1_x>-?[0-9.]+)[ \t]+
			(?P<coord1_y>-?[0-9.]+)[ \t]+
			(?P<coord1_z>-?[0-9.]+)[ \t]+
			\)[ \t]+
			\([ \t]+
			(?P<coord2_x>-?[0-9.]+)[ \t]+
			(?P<coord2_y>-?[0-9.]+)[ \t]+
			(?P<coord2_z>-?[0-9.]+)[ \t]+
			\)[ \t]+
			(?P<shader>[^ \t]+)[ \t]+
			(?P<shift_x>-?[0-9.]+)[ \t]+
			(?P<shift_y>-?[0-9.]+)[ \t]+
			(?P<scale_x>-?[0-9.]+)[ \t]+
			(?P<scale_y>-?[0-9.]+)[ \t]+
			(?P<rotation>-?[0-9.]+)[ \t]+
			(?P<flag_content>[0-9]+)[ \t]+
			(?P<flag_surface>[0-9]+)[ \t]+
			(?P<value>[0-9]+)
			[ \t]*
			""", re.VERBOSE)

		# patch start
		# patchDef2
		patch_start_pattern = re.compile(r"^[ \t]*patchDef2[ \t]*$")

		# shader
		# somename
		patch_shader_pattern = re.compile(r"^[ \t]*(?P<shader>[^ \t]+)[ \t]*$")

		# vertex matrix info
		# ( width height reserved0 reserved1 reserved2 )
		vertex_matrix_info_pattern = re.compile(r"""
			^[ \t]*\([ \t]+
			(?P<width>[0-9]+)[ \t]+
			(?P<height>[0-9]+)[ \t]+
			(?P<reserved0>[0-9]+)[ \t]+
			(?P<reserved1>[0-9]+)[ \t]+
			(?P<reserved2>[0-9]+)[ \t]+
			\)[ \t]*$
			""", re.VERBOSE)

		# vertex matrix opening
		# (
		vertex_matrix_opening_pattern = re.compile(r"^[ \t]*\([ \t]*$")

		# vertex matrix line
#		vertex_matrix_line_pattern = re.compile(r"^[ \t]*\([ \t]+( [ \t]*.*")

		# vertex matrix ending
		# )
		vertex_matrix_ending_pattern = re.compile(r"^[ \t]*\)[ \t]*$")

		# block ending
		# }
		block_ending_pattern = re.compile(r"^[ \t]*}[ \t]*$")

		for line in map_lines:
			debug("reading: " + line)
#			for i in (in_entity, start_shape, in_shape, in_brush, start_patch, in_patch):
#				debug(str(i))

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
				if not start_shape and not  in_shape and not in_brush and not start_patch and not in_patch:
					match = keyvalue_pattern.match(line)
					if match:
						key = match.group("key")
						value = match.group("value")
						debug("KeyValue pair [“" + key + "”, “" + value + "”]")
						self.entity_list[-1].key_dict[key] = value
						continue

				# Shape start
				if not start_shape and not in_shape and not in_brush and not in_patch:
					match = shape_start_pattern.match(line)
					if match:
						brush_num = match.group("brush_num")
						debug("Start Shape #" + str(brush_num))
						start_shape = True
						continue

				# Shape opening
				if start_shape and not in_shape and not in_brush and not in_patch:
					if block_opening_pattern.match(line):
						debug("In Shape")
						start_shape = False
						in_shape = True
						continue

				# Patch start
				if in_shape and not in_brush and not start_patch and not in_patch:
					if patch_start_pattern.match(line):
						debug("Start Patch")
						self.entity_list[-1].shape_list.append(Patch())
						in_shape = False
						start_patch = True
						continue

					# if we are not a patch, and not a ending patch (ending shape)
					if not block_ending_pattern.match(line):
						debug("In Brush")
						self.entity_list[-1].shape_list.append(Brush())
						in_shape = False
						in_brush = True
						# do not continue! this line must be read one more time!
						# this is brush content!
			
				# Patch opening
				if start_patch and not in_patch:
					if block_opening_pattern.match(line):
						debug("In Patch")
						start_patch = False
						in_patch = True
						in_shader = True
						continue

				# Brush content
				if in_brush:
				
					# Plane content
					match = plane_pattern.match(line)
					if match:
						debug("Add Plane to Brush")
						plane = OrderedDict()
						plane["coord0_x"] = match.group("coord0_x")
						plane["coord0_y"] = match.group("coord0_y")
						plane["coord0_z"] = match.group("coord0_z")
						plane["coord1_x"] = match.group("coord1_x")
						plane["coord1_y"] = match.group("coord1_y")
						plane["coord1_z"] = match.group("coord1_z")
						plane["coord2_x"] = match.group("coord2_x")
						plane["coord2_y"] = match.group("coord2_y")
						plane["coord2_z"] = match.group("coord2_z")
						plane["shader"] = match.group("shader")
						plane["shift_x"] = match.group("shift_x")
						plane["shift_y"] = match.group("shift_y")
						plane["scale_x"] = match.group("scale_x")
						plane["scale_y"] = match.group("scale_y")
						plane["rotation"] = match.group("rotation")
						plane["flag_content"] = match.group("flag_content")
						plane["flag_surface"] = match.group("flag_surface")
						plane["value"] = match.group("value")

						self.entity_list[-1].shape_list[-1].plane_list.append(plane)
						continue

					# Brush End
					if block_ending_pattern.match(line):
						debug("End Brush")
						in_brush = False
						continue

				# Patch content
				if in_patch:
					# Stub
					# vertexe: ( orig_x orig_y orig_z texcoord_x texcoord_y )

					# Patch shader
					if in_shader:
						match = patch_shader_pattern.match(line)
						if match:
							debug("Add Shader name to Patch")
							self.entity_list[-1].shape_list[-1].shader = match.group("shader")
							in_shader = False
							in_matrix_info = True
							continue

					if in_matrix_info:
						match = vertex_matrix_info_pattern.match(line)
						if match:
							debug("Add Vertex matrix info to Patch")
							self.entity_list[-1].shape_list[-1].vertex_matrix_info["width"] = match.group("width")
							self.entity_list[-1].shape_list[-1].vertex_matrix_info["height"] = match.group("height")
							self.entity_list[-1].shape_list[-1].vertex_matrix_info["reserved0"] = match.group("reserved0")
							self.entity_list[-1].shape_list[-1].vertex_matrix_info["reserved1"] = match.group("reserved1")
							self.entity_list[-1].shape_list[-1].vertex_matrix_info["reserved2"] = match.group("reserved2")
							in_matrix_info = False
							start_matrix = True
							continue

					if start_matrix:
						if vertex_matrix_opening_pattern.match(line):
							start_matrix = False
							in_matrix = True
							continue

					if in_matrix:
						if not vertex_matrix_ending_pattern.match(line):
							# Stub
							debug("Add line to patch")
							self.entity_list[-1].shape_list[-1].raw_vertex_matrix_line_list.append(line)
							continue

						if vertex_matrix_ending_pattern.match(line):
							in_matrix = False
							continue

					# Patch End
					if block_ending_pattern.match(line):
						debug("End Patch")
						in_patch = False
						in_shape = True
						continue

				if in_shape:
					# Shape End
					if block_ending_pattern.match(line):
						debug("End Shape")
						in_shape = False
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
		shape_count = 0

		for i in range(0, len(self.entity_list)):
			debug("Exporting Entity #" + str(i))
			map_string += "// entity " + str(i) + "\n"
			map_string += "{\n"
			if len(self.entity_list[i].key_dict) > 0:
				for key in self.entity_list[i].key_dict:
					debug("Exporting KeyValue pair")
					map_string += "\"" + key + "\" \"" + self.entity_list[i].key_dict[key] + "\"" + "\n"
			if len(self.entity_list[i].shape_list) > 0:
				for shape in self.entity_list[i].shape_list:
					map_string += "// brush " + str(shape_count) + "\n"
					map_string += "{\n"
					debug("Exporting Shape #" + str(shape_count))
					if type(shape) is Brush:
						debug("Exporting Prush")
						for plane in shape.plane_list:
							map_string += "( "
							map_string += plane["coord0_x"] + " "
							map_string += plane["coord0_y"] + " "
							map_string += plane["coord0_z"]
							map_string += " ) "
							map_string += "( "
							map_string += plane["coord1_x"] + " "
							map_string += plane["coord1_y"] + " "
							map_string += plane["coord1_z"]
							map_string += " ) "
							map_string += "( "
							map_string += plane["coord2_x"] + " "
							map_string += plane["coord2_y"] + " "
							map_string += plane["coord2_z"]
							map_string += " ) "
							map_string += plane["shader"] + " "
							map_string += plane["shift_x"] + " "
							map_string += plane["shift_y"] + " "
							map_string += plane["scale_x"] + " "
							map_string += plane["scale_y"] + " "
							map_string += plane["rotation"] + " "
							map_string += plane["flag_content"] + " "
							map_string += plane["flag_surface"] + " "
							map_string += plane["value"]
							map_string += "\n"

					elif type(shape) is Patch:
						debug("Exporting Patch")
						map_string += "patchDef2\n"
						map_string += "{\n"
						map_string += shape.shader + "\n"
						map_string += "( "
						map_string += shape.vertex_matrix_info["width"] + " "
						map_string += shape.vertex_matrix_info["height"] + " "
						map_string += shape.vertex_matrix_info["reserved0"] + " "
						map_string += shape.vertex_matrix_info["reserved1"] + " "
						map_string += shape.vertex_matrix_info["reserved2"]
						map_string += " )\n"
						map_string += "(\n"
						for line in shape.raw_vertex_matrix_line_list:
							debug(line)
							map_string += line + "\n"
						map_string += ")\n"
						map_string += "}\n"

					else:
						error("This Shape is not a Brush and not a Patch")
						return False

					map_string += "}\n"
					shape_count += 1
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
		qmap = self.export_map()
		if qmap:
			print(qmap)

	def print_bsp_entities(self):
		entities = self.export_bsp_entities()
		if entities:
			print(entities)
			

	def write_file(self, file_name):
		qmap = self.export_map()
		if qmap:
			map_file = open(file_name, 'wb')
			map_file.write(qmap.encode())
			map_file.close
			

class Entity():
	def __init__(self):
		self.key_dict = OrderedDict()
		self.shape_list = []


class Brush():
	def __init__(self):
		self.plane_list = []


class Patch():
	def __init__(self):
		self.shader = None
		self.vertex_matrix_info = {}
		self.raw_vertex_matrix_line_list = []


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
