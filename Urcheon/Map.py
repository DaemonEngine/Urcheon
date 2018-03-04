#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

from Urcheon import Ui
import __main__ as m
import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from logging import debug


# see http://forums.ubergames.net/topic/2658-understanding-the-quake-3-map-format/

class File():
	def __init__(self):
		self.entity_list = None
		# write entity numbers or not
		self.numbering = True

	def readFile(self, file_name):
		input_map_file = open(file_name, "rb")

		map_bstring = input_map_file.read()
		input_map_file.close()

		map_lines = str.splitlines(bytes.decode(map_bstring))

		in_entity = False
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

		# generic comment
		generic_comment_pattern = re.compile("[ \t]*//.*$")

		# entity comment
		# // entity num
		# entity_comment_pattern = re.compile(r"^[ \t]*//[ \t]+entity[ \t]+(?P<entity_num>[0-9]+)[ \t]*$")

		# block opening
		# {
		block_opening_pattern = re.compile(r"^[ \t]*{[ \t]*$")

		# keyvalue pair
		# "key" "value"
		keyvalue_pattern = re.compile(r"^[ \t]*\"(?P<key>[^\"]*)\"[ \t]+\"(?P<value>[^\"]*)\"[ \t]*$")

		# shape comment
		# // brush num
		# shape_comment_pattern = re.compile(r"^[ \t]*//[ \t]+brush[ \t]+(?P<brush_num>[0-9]+)[ \t]*$")

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
			[ \t]*$
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

		# vertex matrix ending
		# )
		vertex_matrix_ending_pattern = re.compile(r"^[ \t]*\)[ \t]*$")

		# block ending
		# }
		block_ending_pattern = re.compile(r"^[ \t]*}[ \t]*$")

		entity_num = -1;

		for line in map_lines:
			debug("Reading: " + line)

			# Empty lines
			if empty_line_pattern.match(line):
				debug("Empty line")
				continue

			# Comments
			if generic_comment_pattern.match(line):
				debug("Comment")
				continue

			# Entity start
			if not in_entity:
				match = block_opening_pattern.match(line)
				if match:
					entity_num += 1
					debug("Start Entity #" + str(entity_num))
					self.entity_list.append(Entity())
					in_entity = True
					brush_num = -1;
					continue

			# In Entity

			# We can only find KeyValue Pair or Shape opening block yet
			if not in_shape and not in_brush and not start_patch and not in_patch:
				# KeyValue pair
				match = keyvalue_pattern.match(line)
				if match:
					key = match.group("key")
					value = match.group("value")
					debug("KeyValue pair [“" + key + "”, “" + value + "”]")
					self.entity_list[-1].keyvalue_dict[key] = value
					continue

				# Shape start
				match = block_opening_pattern.match(line)
				if match:
					brush_num += 1
					debug("Start Shape #" + str(brush_num))
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
			Ui.error("Unknown line: " + line)

		if len(self.entity_list) == 0:
			Ui.error("Empty file")


	def exportFile(self):
		if self.entity_list == None:
			Ui.error("No map loaded")

		map_string = ""

		for i in range(0, len(self.entity_list)):
			debug("Exporting Entity #" + str(i))
			if self.numbering == True:
				map_string += "// entity " + str(i) + "\n"

			map_string += "{\n"
			if len(self.entity_list[i].keyvalue_dict) > 0:
				for key in self.entity_list[i].keyvalue_dict:
					debug("Exporting KeyValue pair")
					map_string += "\"" + key + "\" \"" + self.entity_list[i].keyvalue_dict[key] + "\"" + "\n"
			if len(self.entity_list[i].shape_list) > 0:
				shape_count = 0
				for shape in self.entity_list[i].shape_list:
					if self.numbering == True:
						map_string += "// brush " + str(shape_count) + "\n"

					map_string += "{\n"
					debug("Exporting Shape #" + str(shape_count))
					if type(shape) is Brush:
						debug("Exporting Brush")
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
						Ui.error("This Shape is not a Brush and not a Patch")
						return False

					map_string += "}\n"
					shape_count += 1
			map_string += "}\n"

		return map_string

	def writeFile(self, file_name):
		map_string = self.exportFile()
		if map_string:
			input_map_file = open(file_name, 'wb')
			input_map_file.write(str.encode(map_string))
			input_map_file.close()

	def exportBspEntities(self):
		if self.entity_list == None:
			Ui.error("No map loaded")

		map_string = ""

		for i in range(0, len(self.entity_list)):
			map_string += "{\n"
			if len(self.entity_list[i].keyvalue_dict) > 0:
				for key in self.entity_list[i].keyvalue_dict:
					map_string += "\"" + key + "\" \"" + self.entity_list[i].keyvalue_dict[key] + "\"" + "\n"
			map_string += "}\n"
		return map_string

	def writeBspEntities(self, file_name):
		bsp_entities_string = self.exportBspEntities()
		if bsp_entities_string:
			bsp_entities_file = open(file_name, 'wb')
			bsp_entities_file.write(str.encode(bsp_entities_string))
			bsp_entities_file.close()


	def substituteEntities(self, substitution):
		if not self.entity_list:
			Ui.error("No map loaded")

		for entity in self.entity_list:
			if not entity.substituteKeys(substitution):
				# TODO: what is it?
				return False

			if not entity.substituteValues(substitution):
				# TODO: what is it?
				return False

		return True


class Entity():
	def __init__(self):
		self.keyvalue_dict = OrderedDict()
		self.shape_list = []

	def substituteKeys(self, substitution):
		for old_key, new_key in substitution.key_dict.items():
			# rename the key in place
			self.keyvalue_dict = OrderedDict((new_key if str.lower(key) == str.lower(old_key) else key, value) for key, value in self.keyvalue_dict.items())
		return True

	def substituteValues(self, substitution):
		for old_value, new_value in substitution.value_dict.items():
			for key, value in self.keyvalue_dict.items():
				if str.lower(value) == str.lower(old_value):
					self.keyvalue_dict[key] = new_value
		return True


class Brush():
	def __init__(self):
		self.plane_list = []


class Patch():
	def __init__(self):
		self.shader = None
		self.vertex_matrix_info = {}
		self.raw_vertex_matrix_line_list = []


class KeyValueSubstitution():
	def __init__(self):
		self.key_dict = {}
		self.value_dict = {}


	def readFile(self, file_name):
		substitution_file = open(file_name, "rb")

		if not substitution_file:
			Ui.error("failed to open file: " + file_name)

		substitution_bstring = substitution_file.read()
		substitution_file.close()

		substitution_pattern = re.compile(r"""
			^[ \t]*
			(?P<value_type>key|value)[ \t]*,[ \t]*
			"(?P<old_value>[^\"]*)"[ \t]*,[ \t]*
			"(?P<new_value>[^\"]*)"[ \t]*$
			""", re.VERBOSE)

		substitution_lines = str.splitlines(bytes.decode(substitution_bstring))

		for line in substitution_lines:
			debug("Reading: " + line)
			match = substitution_pattern.match(line)
			if match:
				debug("Matched")
				value_type = match.group("value_type")
				old_value = match.group("old_value")
				new_value = match.group("new_value")
				if value_type == "key":
					debug("Add Key Substitution [ " + old_value + ", " + new_value + " ]")
					self.key_dict[old_value] = new_value
				elif value_type == "value":
					debug("Add Value Substitution [ " + old_value + ", " + new_value + " ]")
					self.value_dict[old_value] = new_value


def main(stage=None):

	if stage:
		prog_name = os.path.basename(m.__file__) + " " + stage
	else:
		prog_name = os.path.basename(m.__file__)

	description="%(prog)s is a map parser for my lovely granger."

	args = argparse.ArgumentParser(description=description, prog=prog_name)
	args.add_argument("-D", "--debug", help="print debug information", action="store_true")
	args.add_argument("-im", "--input-map", dest="input_map_file", metavar="FILENAME", help="read from .map file %(metavar)s")
	args.add_argument("-ob", "--output-bsp-entities", dest="output_bsp_entities", metavar="FILENAME", help="dump entities to .bsp entities format to .txt file %(metavar)s")
	args.add_argument("-se", "--substitute-entities", dest="substitute_entities", metavar="FILENAME", help="use entitie substitution rules from .csv file %(metavar)s")
	args.add_argument("-dn", "--disable-numbering", dest="disable_numbering", help="disable entity and shape numbering", action="store_true")
	args.add_argument("-om", "--output-map", dest="output_map_file", metavar="FILENAME", help="write to .map file %(metavar)s")

	args = args.parse_args()
	if args.debug:
		logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
		debug("Debug logging activated")
		debug("args: " + str(args))

	map = File()

	if args.input_map_file:
		map.readFile(args.input_map_file)

		debug("File " + args.input_map_file + " read")

	if args.substitute_entities:
		substitution = KeyValueSubstitution()
		substitution.readFile(args.substitute_entities)
		map.substituteEntities(substitution)

	if args.disable_numbering:
		map.numbering = False

	if args.output_bsp_entities:
		map.writeBspEntities(args.output_bsp_entities)

	if args.output_map_file:
		map.writeFile(args.output_map_file)


if __name__ == "__main__":
	main()
