#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
# 

file_common_deps = {
	"file_base": "DEPS",
	"description": "Package DEPS File",
	"action": "copy",
}

file_common_pixmap_editor = {
	"file_ext": [
		"xcf",
		"psd",
		"ora",
	],
	"description": "Pixmap Editor File",
	"action": "ignore",
}

file_common_vector_picture = {
	"file_ext": [
		"svg",
		"svgz",
	],
	"description": "Vector picture",
	"action": "ignore"
}

file_common_metada_sidecar = {
	"file_ext": [
		"vorbiscomment",
	],
	"description": "Metadata Sidecar",
	"action": "ignore",
}

file_common_pixmap = {
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
		"flac",
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
		"ase",
		"iqm",
		"iqe",
		"md3",
		"md5anim",
		"md5mesh",
		"qc",
	],
	"description": "Common Model File",
	"action": "copy",
}

file_common_iqe_model = {
	"inherit": "file_common_model",
	"file_ext": "iqe",
	"description": "Common IQE Model File",
	"action": "compile_iqm",
}

file_common_model_source = {
	"file_ext": [
		"blend",
	],
	"description": "Common Model Source",
	"action": "ignore",
}

file_common_text = {
	"file_ext": [
		"txt",
		"md",
	],
	"description": "Common Text File",
	"action": "copy",
}

file_common_sloth = {
	"file_ext": "sloth",
	"description": "Common Sloth Description File",
	"action": "ignore",
}

file_common_readme = {
	"inherit": "file_common_text",
	"file_base": "README",
	"description": "Common ReadMe File",
}

file_common_nullwav = {
	"inherit": "file_common_sound",
	"file_ext": "wav",
	"file_base": "null",
	"description": "Common NULL Sound File",
	"action": "copy",
}
