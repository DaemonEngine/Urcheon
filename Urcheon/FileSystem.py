#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#


from Urcheon import Ui
import logging
import os


def cleanRemoveFile(file_name):
	os.remove(file_name)
	dir_name = os.path.dirname(file_name)
	removeEmptyDir(dir_name)


def removeEmptyDir(dir_name):
	if os.path.isdir(dir_name):
		if os.listdir(dir_name) == []:
			os.rmdir(dir_name)


def makeFileSubdirs(file_name):
	os.makedirs(os.path.dirname(file_name), exist_ok=True)


def getNewer(file_path_list):
	# TODO: remove files that does not exist before checking

	if file_path_list == []:
		Ui.error("can't find newer file if file list is empty")

	newer_path = file_path_list[0]

	for file_path in file_path_list:
		if os.stat(file_path).st_mtime > os.stat(newer_path).st_mtime:
			newer_path = file_path

	logging.debug("newer file: " + newer_path)
	return newer_path


def isSame(file_path, reference_path):
	if not os.path.isfile(file_path):
		logging.debug("file does not exist, can't have same timestamp: " + file_path)
		return False

	if os.stat(file_path).st_mtime == os.stat(reference_path).st_mtime:
		logging.debug("timestamp for file “" + file_path + "” is the same to reference one: " + reference_path)
		return True
	else:
		logging.debug("timestap for file “" + file_path + "”is not same to reference one: " + reference_path)
		return False

def isDifferent(file_path, reference_path):
	return not isSame(file_path, reference_path)
