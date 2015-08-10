#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

from pak_profiles.common import *

# TODO: navmeshes

file_unvanquished_script = {
	"inherit": "file_common_script",
	"dir_ancestor_name": "scripts",
	"description": "Script",
}

file_unvanquished_texture = {
	"inherit": "file_common_texture",
	"dir_ancestor_name": [
		"textures",
		"models",
		"gfx",
		"env",
	],
	"description": "Texture",
	"action": "convert_crn",
}

file_unvanquished_crn = {
	"inherit": "file_unvanquished_texture",
	"file_ext": "crn",
	"description": "Crunch Texture",
	"action": "copy",
}

file_unvanquished_dds = {
	"inherit": "file_unvanquished_texture",
	"file_ext": "dds",
	"description": "Direct Draw Surface",
	"action": "copy",
}

file_unvanquished_skybox = {
	"inherit": "file_unvanquished_texture",
	"file_suffix": [
		"bk",
		"dn",
		"ft",
		"lf",
		"rt",
		"up",
	],
	"dir_ancestor_name": "env",
	"description": "Skybox",
	"action": "convert_jpg",
}

file_unvanquished_jpg_skybox = {
	"inherit": "file_unvanquished_skybox",
	"file_ext": "jpg",
	"action": "copy",
}

file_unvanquished_lightmap = {
	"inherit": "file_common_texture",
	"file_prefix": "lm",
	"dir_ancestor_name": "maps",
	"dir_grand_father_name": "maps",
	"description": "LightMap",
	"action": "convert_png",
}

file_unvanquished_png_lightmap = {
	"inherit": "file_unvanquished_lightmap",
	"ext": "png",
	"action": "copy",
}

file_unvanquished_preview = {
	"inherit": "file_common_texture",
	"file_suffix": "p",
	"description": "Editor preview image",
	"action": "convert_jpg",
}

file_unvanquished_jpg_preview = {
	"inherit": "file_unvanquished_preview",
	"ext": "jpg",
	"action": "copy",
}

file_unvanquished_minimap = {
	"file_ext": "minimap",
	"dir_ancestor_name": "minimaps",
	"description": "MiniMap",
	"action": "copy",
}

file_unvanquished_minimap_image = {
	"inherit": "file_common_texture",
	"dir_ancestor_name": "minimaps",
	"description": "MiniMap image",
	"action": "convert_crn",
}

file_unvanquished_crn_minimap_image = {
	"inherit": "file_unvanquished_minimap_image",
	"ext": [
		"crn",
		"dds",
	],
	"action": "copy",
}

file_unvanquished_colorgrade = {
	"inherit": "file_unvanquished_texture",
	"dir_ancestor_name": "gfx",
	"file_base": "colorgrading",
	"description": "ColorGrade",
	"action": "convert_png",
}

file_unvanquished_png_colorgrade = {
	"inherit": "file_unvanquished_colorgrade",
	"ext": "png",
	"action": "copy",
}

file_unvanquished_arena = {
	"file_ext": "arena",
	"dir_ancestor_name": "meta",
	"description": "Arena file",
	"action": "copy",
}

file_unvanquished_levelshot = {
	"inherit": "file_common_texture",
	"dir_ancestor_name": "meta",
	"description": "LevelShot",
	"action": "convert_jpg",
}

file_unvanquished_about = {
	"dir_ancestor_name": "about",
	"description": "About file",
	"action": "copy",
}

file_unvanquished_map = {
	"file_ext": "map",
	"dir_ancestor_name": "maps",
	"description": "Map",
	"action": "compile_bsp",
}

file_unvanquished_bspdir_lump = {
	"dir_ancestor_name": "maps",
	"dir_father_ext": "bspdir",
	"description": "BSP Lump",
	"action": "merge_bsp",
}

file_unvanquished_bspdir_lightmap = {
	"inherit": "file_unvanquished_lightmap",
	"dir_ancestor_name": "maps",
	"father_name": "lightmaps.d",
	"dir_grandfather_ext": "bspdir",
	"description": "BSP LightMap",
	"action": "merge_bsp",
}

file_unvanquished_bsp = {
	"dir_ancestor_name": "maps",
	"file_ext": "bsp",
	"description": "BSP",
	"action": "copy",
}

file_unvanquished_sound = {
	"inherit": "file_common_sound",
	"dir_ancestor_name": [
		"models",
		"sound",
	],
	"description": "Sound File",
	"action": "convert_opus",
}

file_unvanquished_opus = {
	"inherit": "file_unvanquished_sound",
	"file_ext": "opus",
	"description": "Opus Sound File",
	"action": "copy",
}

file_unvanquished_vorbis = {
	"inherit": "file_unvanquished_sound",
	"file_ext": "ogg",
	"description": "Vorbis Sound File",
	"action": "copy",
}

file_unvanquished_model = {
	"inherit": "file_common_model",
	"dir_ancestor_name": "models",
	"description": "Model File",
}
