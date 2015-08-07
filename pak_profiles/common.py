#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

file_common_external_editor = {
	"file_ext": [
		"xcf",
		"psd",
		"ora",
	],
	"description": "External Editor File",
	"action": "ignore",
}

file_common_texture = {
	"file_ext": [
		"jpg", 
		"jpeg",
		"png",
		"tga",
		"bmp",
		"webp",
		"crn",
		"dds",
	],
	"description": "Texture",
	"action": "copy",
}

file_common_sound = {
	"file_ext": [
		"wav",
		"ogg",
		"opus",
	],
	"description": "Sound File",
	"action": "copy",
}

file_common_script = {
	"file_ext": [
		"shader",
		"particle",
		"trail",
	],
	"dir_ancestor_name": "scripts",
	"description": "Common Script",
	"action": "copy",
}

file_common_model = {
	"file_ext": [
		"qc",
		"ase",
		"md3",
	],
	"description": "Common Model File",
	"action": "copy",
}

file_common_text = {
	"file_ext": [
		"txt",
		"md",
	],
	"description": "Common Text file",
	"action": "copy",
}

file_common_readme = {
	"inherit": "file_common_text",
	"file_base": "README",
	"description": "Common ReadMe file",
}

file_common_nullwav = {
	"dir_ancestor_name": "file_common_sound",
	"file_name": "null.wav",
	"description": "Common NULL Sound File",
	"action": "copy",
}
