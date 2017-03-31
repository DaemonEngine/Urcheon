#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


import os

def cleanRemoveFile(file_name):
	os.remove(file_name)
	dir_name = os.path.dirname(file_name)
	removeEmptyDir(dir_name)

def removeEmptyDir(dir_name):
	if os.path.isdir(dir_name):
		if os.listdir(dir_name) == []:
			os.rmdir(dir_name)
