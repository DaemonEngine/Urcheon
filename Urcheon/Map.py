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

# see https://github.com/Unvanquished/Unvanquished/blob/master/src/gamelogic/game/g_spawn.cpp
q3_sound_keyword_list = [
	"noise",
	"sound1to2",
	"sound2to1",
	"soundPos1",
	"soundPos2",
]

# Two kinds of Quake 3 brush formats are known:
# - Q3 Brush, also known as “Axial Projection” or AP, sometime referred to as Q3 Legacy Brush, the historical and most used format, seems to be derived from Quake format.
# - Q3 BP Brush, also known as “Brush Primitives” or BP, sometime referred to as “Alternate Texture Projection”, also very old but less old (introduced in Q3Radiant 192).

# For Quake 3 brush and patch format, see:
# see https://web.archive.org/web/20160316213335/http://forums.ubergames.net/topic/2658-understanding-the-quake-3-map-format/

class Map():
	def __init__(self):
		self.entity_list = None

		# write entity numbers or not
		self.numbering_enabled = True

	def readFile(self, file_name):
		input_map_file = open(file_name, "rb")

		map_bstring = input_map_file.read()

		self.readBlob(map_bstring)

		input_map_file.close()

	def readBlob(self, map_bstring):
		map_lines = str.splitlines(bytes.decode(map_bstring))

		in_entity = False
		in_shape = False

		in_q3brush = False

		start_q3bpbrush = False
		in_q3bpbrush = False

		start_q3patch = False
		in_q3patch = False

		in_q3patch_material = False

		start_q3patch_matrix = False
		in_q3patch_matrix = False

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
		# shape_comment_pattern = re.compile(r"^[ \t]*//[ \t]+brush[ \t]+(?P<shape_num>[0-9]+)[ \t]*$")

		# q3 brush plane line
		# coord, textures
		# ( coord0_x coord0_y coord0_z ) ( coord1_x coord1_y coord1_z ) ( coord2_x coord2_y coord2_z ) material shift_x shift_y rotation scale_x scale_y flags_content flags_surface value
		q3brush_plane_pattern = re.compile(r"""
			[ \t]*\([ \t]*
			(?P<coord0_x>-?[0-9.]+)[ \t]+
			(?P<coord0_y>-?[0-9.]+)[ \t]+
			(?P<coord0_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			(?P<coord1_x>-?[0-9.]+)[ \t]+
			(?P<coord1_y>-?[0-9.]+)[ \t]+
			(?P<coord1_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			(?P<coord2_x>-?[0-9.]+)[ \t]+
			(?P<coord2_y>-?[0-9.]+)[ \t]+
			(?P<coord2_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			(?P<material>[^ \t]+)[ \t]+
			(?P<shift_x>-?[0-9.]+)[ \t]+
			(?P<shift_y>-?[0-9.]+)[ \t]+
			(?P<rotation>-?[0-9.]+)[ \t]+
			(?P<scale_x>-?[0-9.]+)[ \t]+
			(?P<scale_y>-?[0-9.]+)[ \t]+
			(?P<flag_content>[0-9]+)[ \t]+
			(?P<flag_surface>[0-9]+)[ \t]+
			(?P<value>[0-9]+)
			[ \t]*$
			""", re.VERBOSE)

		# q3 bp brush start
		# brushDef
		q3bpbrush_start_pattern = re.compile(r"^[ \t]*brushDef[ \t]*$")

		# q3 bp brush plane line
		# coord, textures
		# ( coord0_x coord0_y coord0_z ) ( coord1_x coord1_y coord1_z ) ( coord2_x coord2_y coord2_z ) ( ( texdef_xx texdef_yx texdef_tx ) ( texdef_xy texdef_yy texdef_ty ) ) material flag_content flag_surface value
		q3bpbrush_plane_pattern = re.compile(r"""
			[ \t]*\([ \t]*
			(?P<coord0_x>-?[0-9.]+)[ \t]+
			(?P<coord0_y>-?[0-9.]+)[ \t]+
			(?P<coord0_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			(?P<coord1_x>-?[0-9.]+)[ \t]+
			(?P<coord1_y>-?[0-9.]+)[ \t]+
			(?P<coord1_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			(?P<coord2_x>-?[0-9.]+)[ \t]+
			(?P<coord2_y>-?[0-9.]+)[ \t]+
			(?P<coord2_z>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			\([ \t]*
			(?P<texdef_xx>-?[0-9.]+)[ \t]+
			(?P<texdef_yx>-?[0-9.]+)[ \t]+
			(?P<texdef_tx>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\([ \t]*
			(?P<texdef_xy>-?[0-9.]+)[ \t]+
			(?P<texdef_yy>-?[0-9.]+)[ \t]+
			(?P<texdef_ty>-?[0-9.]+)[ \t]*
			\)[ \t]*
			\)[ \t]*
			(?P<material>[^ \t]+)[ \t]+
			(?P<flag_content>[0-9]+)[ \t]+
			(?P<flag_surface>[0-9]+)[ \t]+
			(?P<value>[0-9]+)
			[ \t]*$
			""", re.VERBOSE)

		# q3 patch start
		# patchDef2
		q3patch_start_pattern = re.compile(r"^[ \t]*patchDef2[ \t]*$")

		# q3 patch material
		# somename
		q3patch_material_pattern = re.compile(r"^[ \t]*(?P<material>[^ \t]+)[ \t]*$")

		# vertex matrix info
		# ( width height reserved0 reserved1 reserved2 )
		q3patch_vertex_q3patch_matrix_info_pattern = re.compile(r"""
			^[ \t]*\([ \t]*
			(?P<width>[0-9]+)[ \t]+
			(?P<height>[0-9]+)[ \t]+
			(?P<reserved0>[0-9]+)[ \t]+
			(?P<reserved1>[0-9]+)[ \t]+
			(?P<reserved2>[0-9]+)[ \t]*
			\)[ \t]*$
			""", re.VERBOSE)

		# vertex matrix opening
		# (
		q3patch_vertex_q3patch_matrix_opening_pattern = re.compile(r"^[ \t]*\([ \t]*$")

		# vertex line
		q3patch_vertex_line_pattern = re.compile(r"""
			^[ \t]*\([ \t]*
			(?P<q3patch_vertex_list>\([ \t]*[ \t0-9.\(\)-]+[ \t]*\))[ \t]*
			\)[ \t]*$
			""", re.VERBOSE)

		# vertex list
		q3patch_vertex_list_pattern = re.compile(r"""
			^[ \t]*\([ \t]*
			(?P<origin_x>-?[0-9.]+)[ \t]*
			(?P<origin_y>-?[0-9.]+)[ \t]*
			(?P<origin_z>-?[0-9.]+)[ \t]*
			(?P<texcoord_x>-?[0-9.]+)[ \t]*
			(?P<texcoord_y>-?[0-9.]+)[ \t]*
			\)[ \t]*
			(?P<remaining>\(?[ \t]*[ \t0-9().-]*[ \t]*\)?)
			[ \t]*$
			""", re.VERBOSE)

		# vertex matrix ending
		# )
		q3patch_vertex_q3patch_matrix_ending_pattern = re.compile(r"^[ \t]*\)[ \t]*$")

		# block ending
		# }
		block_ending_pattern = re.compile(r"^[ \t]*}[ \t]*$")

		entity_num = -1

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
					shape_num = -1
					continue

			# In Entity

			if not in_q3brush and not start_q3bpbrush and not in_q3bpbrush and not start_q3patch and not in_q3patch:
				# We can only find KeyValue or Shape opening block at this point
				if not in_shape:
					# KeyValue pair
					match = keyvalue_pattern.match(line)
					if match:
						key = match.group("key")
						value = match.group("value")
						debug("KeyValue pair [“" + key + "”, “" + value + "”]")
						self.entity_list[-1].thing_list.append(KeyValue())
						self.entity_list[-1].thing_list[-1].key = key
						self.entity_list[-1].thing_list[-1].value = value
						continue

					# Shape start
					match = block_opening_pattern.match(line)
					if match:
						shape_num += 1
						debug("Start Shape #" + str(shape_num))
						in_shape = True
						continue

				# Brush/Patch start
				else: # in_shape
					if q3bpbrush_start_pattern.match(line):
						debug("Start Q3 BP Brush")
						self.entity_list[-1].thing_list.append(Q3BPBrush())
						in_q3bpbrush = False
						start_q3bpbrush = True
						continue

					if q3patch_start_pattern.match(line):
						debug("Start Q3 Patch")
						self.entity_list[-1].thing_list.append(Q3Patch())
						in_shape = False
						start_q3patch = True
						continue

					# if we are not a brush or patch, and not a ending brush or patch (ending shape)
					if not block_ending_pattern.match(line):
						debug("In Q3Brush")
						self.entity_list[-1].thing_list.append(Q3Brush())
						in_shape = False
						in_q3brush = True
						# do not continue! this line must be read one more time!
						# this is brush content!

			# Q3 Patch opening
			if start_q3patch and not in_q3patch:
				if block_opening_pattern.match(line):
					debug("In Q3 Patch")
					start_q3patch = False
					in_q3patch = True
					in_q3patch_material = True
					continue

			# Q3 BP Brush opening
			if start_q3bpbrush and not in_q3bpbrush:
				if block_opening_pattern.match(line):
					debug("In Q3 BP Brush")
					start_q3bpbrush = False
					in_q3bpbrush = True
					continue

			# Q3Brush content
			if in_q3brush:

				# Plane content
				match = q3brush_plane_pattern.match(line)
				if match:
					debug("Add Plane to Q3Brush")
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
					plane["material"] = match.group("material")
					plane["shift_x"] = match.group("shift_x")
					plane["shift_y"] = match.group("shift_y")
					plane["rotation"] = match.group("rotation")
					plane["scale_x"] = match.group("scale_x")
					plane["scale_y"] = match.group("scale_y")
					plane["flag_content"] = match.group("flag_content")
					plane["flag_surface"] = match.group("flag_surface")
					plane["value"] = match.group("value")

					self.entity_list[-1].thing_list[-1].plane_list.append(plane)
					continue

				# Q3Brush End
				if block_ending_pattern.match(line):
					debug("End Q3Brush")
					in_q3brush = False
					continue

			# Q3 BP Brush content
			if in_q3bpbrush:
				# Plane content
				match = q3bpbrush_plane_pattern.match(line)
				if match:
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
					plane["texdef_xx"] = match.group("texdef_xx")
					plane["texdef_yx"] = match.group("texdef_yx")
					plane["texdef_tx"] = match.group("texdef_tx")
					plane["texdef_xy"] = match.group("texdef_xy")
					plane["texdef_yy"] = match.group("texdef_yy")
					plane["texdef_ty"] = match.group("texdef_ty")
					plane["material"] = match.group("material")
					plane["flag_content"] = match.group("flag_content")
					plane["flag_surface"] = match.group("flag_surface")
					plane["value"] = match.group("value")

					self.entity_list[-1].thing_list[-1].plane_list.append(plane)
					continue

				# Q3 BP Brush End
				if block_ending_pattern.match(line):
					debug("End Q3Brush")
					in_q3bpbrush = False
					in_shape = True
					continue

			# Q3 Patch content
			if in_q3patch:
				# Q3 Patch material
				if in_q3patch_material:
					match = q3patch_material_pattern.match(line)
					if match:
						debug("Add Material name to Q3 Patch")
						self.entity_list[-1].thing_list[-1].q3patch_material = match.group("material")
						in_q3patch_material = False
						in_q3patch_matrix_info = True
						continue

				if in_q3patch_matrix_info:
					match = q3patch_vertex_q3patch_matrix_info_pattern.match(line)
					if match:
						debug("Add Vertex matrix info to Q3 Patch")
						self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix_info["width"] = match.group("width")
						self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix_info["height"] = match.group("height")
						self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix_info["reserved0"] = match.group("reserved0")
						self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix_info["reserved1"] = match.group("reserved1")
						self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix_info["reserved2"] = match.group("reserved2")
						in_q3patch_matrix_info = False
						start_q3patch_matrix = True
						continue

				if start_q3patch_matrix:
					if q3patch_vertex_q3patch_matrix_opening_pattern.match(line):
						start_q3patch_matrix = False
						in_q3patch_matrix = True
						continue

				if in_q3patch_matrix:
					if not q3patch_vertex_q3patch_matrix_ending_pattern.match(line):
						match = q3patch_vertex_line_pattern.match(line)
						if match:
							debug("Add line to patch")
							q3patch_vertex_list = []
							q3patch_vertex_list_string = match.group("q3patch_vertex_list")

							debug("Reading substring: " + q3patch_vertex_list_string)
							match = q3patch_vertex_list_pattern.match(q3patch_vertex_list_string)
							while match:
								debug("Add vertex to patch line")
								vertex = {}
								vertex["origin_x"] = match.group("origin_x")
								vertex["origin_y"] = match.group("origin_y")
								vertex["origin_z"] = match.group("origin_z")
								vertex["texcoord_x"] = match.group("texcoord_x")
								vertex["texcoord_y"] = match.group("texcoord_y")

								q3patch_vertex_list.append(vertex)

								remaining = match.group("remaining")
								debug("Reading substring: " + remaining)
								match = q3patch_vertex_list_pattern.match(remaining)

							self.entity_list[-1].thing_list[-1].q3patch_vertex_q3patch_matrix.append(q3patch_vertex_list)

						continue

					if q3patch_vertex_q3patch_matrix_ending_pattern.match(line):
						in_q3patch_matrix = False
						continue

				# Q3 Patch End
				if block_ending_pattern.match(line):
					debug("End Q3 Patch")
					in_q3patch = False
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

		# an empty file is not an error

	def exportFile(self, bsp_entities_only=False):
		if self.entity_list == None:
			Ui.error("No map loaded")

		numbering_enabled = self.numbering_enabled and not bsp_entities_only

		map_string = ""
		model_count = 0

		for i in range(0, len(self.entity_list)):
			debug("Exporting Entity #" + str(i))

			entity_string = ""

			if len(self.entity_list[i].thing_list) > 0:
				entity_printable = True
				has_classname = False
				has_shape = False;
				is_model = False;
				keyvalue_count = 0
				shape_count = 0

				thing_list = self.entity_list[i].thing_list

				if bsp_entities_only:
					thing_list.reverse()

				for thing in thing_list:
					if isinstance(thing, KeyValue):
						if bsp_entities_only:
							if thing.key == "classname":
								if thing.value in [ "func_group", "light", "misc_model" ]:
									entity_printable = False
									continue

							if thing.key == "classname":
								has_classname = True
								if has_classname and has_shape:
									is_model = True

						debug("Exporting KeyValue pair")

						entity_string += "\"" + thing.key + "\" \"" + thing.value + "\"" + "\n"
						keyvalue_count += 1

						continue

					if isinstance(thing, Shape):
						has_shape = True

						if has_classname and has_shape:
							is_model = True

						if bsp_entities_only:
							continue

						shape = thing

						if numbering_enabled:
							entity_string += "// brush " + str(shape_count) + "\n"

						entity_string += "{\n"
						debug("Exporting Shape #" + str(shape_count))

						if isinstance(shape, Q3Brush):
							debug("Exporting Q3Brush")

							for plane in shape.plane_list:
								entity_string += "( "
								entity_string += plane["coord0_x"] + " "
								entity_string += plane["coord0_y"] + " "
								entity_string += plane["coord0_z"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += plane["coord1_x"] + " "
								entity_string += plane["coord1_y"] + " "
								entity_string += plane["coord1_z"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += plane["coord2_x"] + " "
								entity_string += plane["coord2_y"] + " "
								entity_string += plane["coord2_z"] + " "
								entity_string += ") "
								entity_string += plane["material"] + " "
								entity_string += plane["shift_x"] + " "
								entity_string += plane["shift_y"] + " "
								entity_string += plane["rotation"] + " "
								entity_string += plane["scale_x"] + " "
								entity_string += plane["scale_y"] + " "
								entity_string += plane["flag_content"] + " "
								entity_string += plane["flag_surface"] + " "
								entity_string += plane["value"]
								entity_string += "\n"

						elif isinstance(shape, Q3BPBrush):
							debug("Exporting Q3 BP Brush")
							entity_string += "brushDef\n"
							entity_string += "{\n"

							for plane in shape.plane_list:
								entity_string += "( "
								entity_string += plane["coord0_x"] + " "
								entity_string += plane["coord0_y"] + " "
								entity_string += plane["coord0_z"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += plane["coord1_x"] + " "
								entity_string += plane["coord1_y"] + " "
								entity_string += plane["coord1_z"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += plane["coord2_x"] + " "
								entity_string += plane["coord2_y"] + " "
								entity_string += plane["coord2_z"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += "( "
								entity_string += plane["texdef_xx"] + " "
								entity_string += plane["texdef_yx"] + " "
								entity_string += plane["texdef_tx"] + " "
								entity_string += ") "
								entity_string += "( "
								entity_string += plane["texdef_xy"] + " "
								entity_string += plane["texdef_yy"] + " "
								entity_string += plane["texdef_ty"] + " "
								entity_string += ") "
								entity_string += ") "
								entity_string += plane["material"] + " "
								entity_string += plane["flag_content"] + " "
								entity_string += plane["flag_surface"] + " "
								entity_string += plane["value"]
								entity_string += "\n"

							entity_string += "}\n"

						elif isinstance(shape, Q3Patch):
							debug("Exporting Q3 Patch")
							entity_string += "patchDef2\n"
							entity_string += "{\n"
							entity_string += shape.q3patch_material + "\n"
							entity_string += "( "
							entity_string += shape.q3patch_vertex_q3patch_matrix_info["width"] + " "
							entity_string += shape.q3patch_vertex_q3patch_matrix_info["height"] + " "
							entity_string += shape.q3patch_vertex_q3patch_matrix_info["reserved0"] + " "
							entity_string += shape.q3patch_vertex_q3patch_matrix_info["reserved1"] + " "
							entity_string += shape.q3patch_vertex_q3patch_matrix_info["reserved2"] + " "
							entity_string += ")\n"
							entity_string += "(\n"

							for q3patch_vertex_line in shape.q3patch_vertex_q3patch_matrix:
								entity_string += "( "
								for vertex in q3patch_vertex_line:
									entity_string += "( "
									entity_string += vertex["origin_x"] + " "
									entity_string += vertex["origin_y"] + " "
									entity_string += vertex["origin_z"] + " "
									entity_string += vertex["texcoord_x"] + " "
									entity_string += vertex["texcoord_y"] + " "
									entity_string += ") "
								entity_string += ")\n"
							entity_string += ")\n"
							entity_string += "}\n"

						else:
							Ui.error("Unknown Entity Shape")
							return False

						entity_string += "}\n"
						shape_count += 1

						continue

					Ui.error("Unknown Entity Thing")

			if numbering_enabled:
				entity_string += "// entity " + str(i) + "\n"

			if entity_printable:
				map_string += "{\n"

				if is_model:
					if model_count > 0:
						map_string += "\"model\" \"*" + str(model_count) + "\"\n"

					model_count += 1

				map_string += entity_string
				map_string += "}\n"

		return map_string

	def writeFile(self, file_name):
		map_string = self.exportFile()
		if map_string:
			input_map_file = open(file_name, 'wb')
			input_map_file.write(str.encode(map_string))
			input_map_file.close()

	def exportBspEntities(self):
		return self.exportFile(bsp_entities_only=True)

	def writeBspEntities(self, file_name):
		bsp_entities_string = self.exportBspEntities()
		if bsp_entities_string:
			bsp_entities_file = open(file_name, 'wb')
			bsp_entities_file.write(str.encode(bsp_entities_string))
			bsp_entities_file.close()

	def substituteKeywords(self, substitution):
		if not self.entity_list:
			Ui.error("No map loaded")

		for entity in self.entity_list:
			entity.substituteKeys(substitution)
			entity.substituteValues(substitution)

	def lowerCaseFilePaths(self):
		for entity in self.entity_list:
			for thing in entity.thing_list:
				if isinstance(thing, KeyValue):
					if thing.key in [ "model", "targetShaderName" ] + q3_sound_keyword_list:
						thing.value = thing.value.lower()

				elif isinstance(thing, Q3Brush):
					for plane in thing.plane_list:
						plane["material"] = plane["material"].lower()

				elif isinstance(thing, Q3BPBrush):
					for plane in thing.plane_list:
						plane["material"] = plane["material"].lower()

				elif isinstance(thing, Q3Patch):
					thing.q3patch_material = thing.q3patch_material.lower()

class Entity():
	def __init__(self):
		self.thing_list = []

	def substituteKeys(self, substitution):
		for old_key, new_key in substitution.key_dict.items():
			# rename the key in place
			for thing in self.thing_list:
				if isinstance(thing, KeyValue):
					if str.lower(thing.key) == str.lower(old_key):
						thing.key = new_key

	def substituteValues(self, substitution):
		for old_value, new_value in substitution.value_dict.items():
			for thing in self.thing_list:
				if isinstance(thing, KeyValue):
					if str.lower(thing.value) == str.lower(old_value):
						thing.value = new_value

class KeyValue():
	def __init__(self):
		self.key = ""
		self.value = ""

class Shape():
	pass

class Q3Brush(Shape):
	def __init__(self):
		self.plane_list = []

class Q3BPBrush(Shape):
	def __init__(self):
		self.plane_list = []

class Q3Patch(Shape):
	def __init__(self):
		self.q3patch_material = None
		self.q3patch_vertex_q3patch_matrix_info = {}
		self.q3patch_vertex_q3patch_matrix = []

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
			debug("Reading line: " + line)
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

def add_arguments(parser):
	parser.add_argument("-im", "--input-map", dest="input_map_file", metavar="FILENAME", help="read from .map file %(metavar)s")
	parser.add_argument("-oe", "--output-bsp-entities", dest="output_bsp_entities", metavar="FILENAME", help="dump entities to .bsp entities format to .txt file %(metavar)s")
	parser.add_argument("-sk", "--substitute-keywords", dest="substitute_keywords", metavar="FILENAME", help="use entity keyword substitution rules from .csv file %(metavar)s")
	parser.add_argument("-Lf", "--lowercase-filepaths", dest="lowercase_filepaths", help="lowercase file paths", action="store_true")
	parser.add_argument("-dn", "--disable-numbering", dest="disable_numbering", help="disable entity and shape numbering", action="store_true")
	parser.add_argument("-om", "--output-map", dest="output_map_file", metavar="FILENAME", help="write to .map file %(metavar)s")

def main(args=None):
	if not args:
		description="Esquirel bsp is a map parser for my lovely granger."
		parser = argparse.ArgumentParser(description=description)
		parser.add_argument("-D", "--debug", help="print debug information", action="store_true")
		add_arguments(parser)
		args = parser.parse_args()

	map = Map()

	if args.input_map_file:
		map.readFile(args.input_map_file)

		debug("File " + args.input_map_file + " read")

	if args.substitute_keywords:
		substitution = KeyValueSubstitution()
		substitution.readFile(args.substitute_keywords)
		map.substituteKeywords(substitution)

	if args.lowercase_filepaths:
		map.lowerCaseFilePaths()

	if args.disable_numbering:
		map.numbering_enabled = False

	if args.output_bsp_entities:
		map.writeBspEntities(args.output_bsp_entities)

	if args.output_map_file:
		map.writeFile(args.output_map_file)

if __name__ == "__main__":
	main()
