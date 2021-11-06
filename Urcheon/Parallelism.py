#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

import psutil
import subprocess
import threading


getProcess = psutil.Process


def countCPU():
	# Reuse computed value
	if not hasattr(countCPU, "count"):

		try:
			# On Linux, psutil.cpu_count() and “nproc” may only return the
			# amount of currently enabled core while the system may disable
			# or disable them according to the current load, meaning the
			# reported cpu count may be far lower to what's available.
			# If we don't ask for the amount of available the present software
			# may limit itself to a small amount of cores if the system was
			# idling at the time the present software is called.
			# The ”nproc --all” command is known to report the amount of
			# available cores.
			result = subprocess.run(['nproc', '--all'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

			if result.stdout != b'':
				countCPU.count = int(result.stdout)
			else:
				countCPU.count = psutil.cpu_count()
		except:
			countCPU.count = psutil.cpu_count()

	return countCPU.count


def countThread(process):
	# process can disappear between the time
	# this function is called and the num_threads()
	# one is called, in this case return 0
	try:
		return process.num_threads()
	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		return 0


def countChildThread(process):
	# process can disappear between the time
	# this function is called and the children()
	# one is called, in this case return 0
	try:
		thread_count = 0
		# process.children() is super slow
		for subprocess in process.children(recursive=True):
			thread_count = thread_count + countThread(subprocess)
		return thread_count
	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		return 0


def joinDeadThreads(thread_list):
	for thread in thread_list:
		if not thread.is_alive() and thread._started.is_set():
			thread.join()
			thread_list.remove(thread)

	return thread_list


def joinThreads(thread_list):
	for thread in thread_list:
		if not thread._started.is_set():
			thread.start()
		thread.join()


# this extends threading.Thread to transmit exceptions
# back to the parent, best used with joinDeadThreads()
# on active thread list to raise exceptions early
class Thread(threading.Thread):
	def run(self):
		self._exception = None

		try:
			self._return = self._target(*self._args, **self._kwargs)
		except BaseException as exception:
			self._exception = exception

	def join(self):
		super(Thread, self).join()

		if self._exception:
			raise self._exception

		return self._return
