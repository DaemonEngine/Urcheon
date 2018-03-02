#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

import psutil

getProcess = psutil.Process

countCPU = psutil.cpu_count

def countThread(process):
	# process can disappear between the time
	# this function is called and the num_threads()
	# one is called, in this case return 0
	try:
		return process.num_threads()
	except:
		return 0

def countChildThread(process):
	# process can disappear between the time
	# this function is called and the children()
	# one is called, in this case return 0
	try:
		thread_count = 0
		for subprocess in process.children():
			thread_count = thread_count + countThread(subprocess) + countChildThread(subprocess)
		return thread_count
	except:
		return 0
