#! /usr/bin/env python3
#-*- coding: UTF-8 -*-

### Legal
#
# Author:  Thomas DEBESSE <dev@illwieckz.net>
# License: ISC
#

import atexit
import logging
import psutil
import subprocess
import threading
import random
import time

# Hysteresis thresholds for process-tree suspension and resumption.
# The small oversubscription allowance accommodates thread-count estimates
# and avoids repeatedly suspending and resuming jobs around the CPU count.
LOW_WATERMARK = 1.05
HIGH_WATERMARK = 1.1

# Time between scheduler decisions and minimum delay between resumes.
MONITOR_INTERVAL = 0.1
RESUME_COOLDOWN = 1.0

_last_resume_time = 0.0

# Processes whose resume operation failed and must be retried.
_pending_resumes = {}
# Subprocesses launched through call(), indexed by their root PID.
_processes = {}
# Protect scheduler state shared by worker threads and the monitor.
_process_lock = threading.RLock()
# Suspensions initiated or adopted by Urcheon, keyed by (PID, creation time).
# Each record contains the entries that still require the process to stay
# suspended. Creation time protects against accidentally acting on a reused PID.
_suspensions = {}

_monitor = None

getProcess = psutil.Process


def countCPU():
	if not hasattr(countCPU, "count"):
		# Reuse computed value.
		countCPU.count = psutil.cpu_count() or 1

	return countCPU.count


def countThread(process):
	# Process can disappear between the time this function is called and
	# the num_threads() one is called. In this case 0 should be returned.
	try:
		return process.num_threads()
	except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
		return 0


def countChildThread(process):
	# process can disappear between the time
	# this function is called and the children()
	# one is called, in this case return 0
	try:
		thread_count = 0
		# process.children() is super slow
		for children in process.children(recursive=True):
			thread_count = thread_count + countThread(children)
		return thread_count
	except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
		return 0


def joinDeadThreads(thread_list):
	# Join completed workers promptly so their exceptions can be propagated.
	for thread in thread_list[:]:
		if not thread.is_alive() and thread._started.is_set():
			thread.join()
			thread_list.remove(thread)

	return thread_list


def joinThreads(thread_list):
	# Start remaining unstarted workers and wait for them.
	for thread in thread_list:
		if not thread._started.is_set():
			thread.start()
		thread.join()


def _get_watermarks():
	count = countCPU()

	# Keep both thresholds above the nominal CPU count, with a bounded
	# allowance of at most five extra threads.
	low = min(max(int(count * LOW_WATERMARK), count + 1), count + 5)
	high = min(max(int(count * HIGH_WATERMARK), low + 1), count + 5)

	return low, high


def _process_tree(root_pid):
	# Return the root and its descendants, tolerating processes that disappear
	# or become inaccessible while the tree is being enumerated.
	try:
		root = psutil.Process(root_pid)
		processes = [root]
		try:
			processes.extend(root.children(recursive=True))
		except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
			pass

		# Deduplicate PIDs in case the process listing overlaps.
		return list({process.pid: process for process in processes}.values())
	except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
		return []


def _register_suspension_locked(entry, pid, create_time):
	# Caller must hold _process_lock. Register this entry as an owner of
	# the suspension, so overlapping process trees cannot resume it too early.
	identity = (pid, create_time)
	previous_create_time = entry["suspended_pids"].get(pid)

	if (
		previous_create_time is not None
		and previous_create_time != create_time
	):
		# The PID now identifies a different process; release the stale record.
		_release_suspension_locked(
			entry, pid, previous_create_time
		)

	record = _suspensions.get(identity)

	if record is None:
		record = {"owners": set()}
		_suspensions[identity] = record

	record["owners"].add(id(entry))
	entry["suspended_pids"][pid] = create_time
	entry["suspended"] = entry["pid"] in entry["suspended_pids"]

	# This identity is now owned again, so a queued resume is obsolete.
	_pending_resumes.pop(identity, None)


def _forget_suspended_process_locked(pid, create_time):
	# Remove all scheduler bookkeeping once the process is gone or no longer
	# needs a resume. Also clear stale references from every registered entry.
	identity = (pid, create_time)

	_suspensions.pop(identity, None)
	_pending_resumes.pop(identity, None)

	for entry in _processes.values():
		if entry["suspended_pids"].get(pid) == create_time:
			entry["suspended_pids"].pop(pid, None)
			entry["suspended"] = entry["pid"] in entry["suspended_pids"]



def _release_suspension_locked(entry, pid, create_time):
	# Release one entry's ownership. Resume only when no other entry still
	# requires this process to remain suspended.
	identity = (pid, create_time)
	record = _suspensions.get(identity)

	if entry["suspended_pids"].get(pid) == create_time:
		# Only remove the mapping if it still refers to this process.
		entry["suspended_pids"].pop(pid, None)

	entry["suspended"] = entry["pid"] in entry["suspended_pids"]

	if record is None:
		return

	record["owners"].discard(id(entry))

	if record["owners"]:
		# Another entry still needs this process to remain suspended.
		_pending_resumes.pop(identity, None)
		return

	if _try_resume(pid, create_time):
		# No entry needs this suspension anymore.
		_forget_suspended_process_locked(pid, create_time)
	else:
		# Keep the central record until a retry succeeds.
		_pending_resumes[identity] = None


def _rollback_new_suspensions_locked(entry, previous):
	# A process tree may be only partially suspended. Undo suspensions added
	# by this attempt, but preserve ownership that existed before it began.
	for pid, create_time in reversed(list(entry["suspended_pids"].items())):
		if previous.get(pid) == create_time:
			continue

		_release_suspension_locked(entry, pid, create_time)

	entry["suspended"] = entry["pid"] in entry["suspended_pids"]


# Process state checks and suspend() are not atomic. Another program may
# stop a process between the status check and suspend(), so we cannot
# reliably distinguish every external suspension from one initiated here.
# Where detected, such cases are handled on a best-effort basis.
# It is a reasonable trade-off given the limitations.
# The goal is robustness: external state changes should not abort the scheduler.
def _suspend_process(entry, process):
	pid = process.pid

	try:
		create_time = process.create_time()
		status = process.status()

		if status == psutil.STATUS_STOPPED:
			identity = (pid, create_time)

			if identity not in _suspensions:
				# Do not claim ownership of an already-stopped process unless
				# Urcheon is already tracking its suspension.
				return False

			_register_suspension_locked(entry, pid, create_time)
			return True

		if not process.is_running():
			# The process is no longer a live target to suspend.
			return True

		try:
			process.suspend()
		except psutil.Error:
			# suspend() may have taken effect before reporting an error.
			# If the process is now stopped, assume Urcheon suspended it, 
			# even though an external suspension cannot be ruled out.
			# This is an accepted trade-off: resuming externally suspended
			# processes is preferable to leaving our suspensions unrecovered.
			try:
				if (
					process.create_time() == create_time
					and process.status() == psutil.STATUS_STOPPED
				):
					_register_suspension_locked(
						entry, pid, create_time
					)
			except psutil.Error:
		 		# A vanished process no longer needs to be suspended.
				pass

			return False

		_register_suspension_locked(entry, pid, create_time)
		return True

	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		return True

	except psutil.AccessDenied:
		return False


def _suspend(entry):
	# Preserve ownership from earlier successful attempts. If this attempt
	# fails partway through the tree, only its new suspensions are rolled back.
	previous = entry["suspended_pids"].copy()

	try:
		root = psutil.Process(entry["pid"])
		create_time = root.create_time()
		root_status = root.status()

	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		entry["suspended"] = False
		return False
	except psutil.AccessDenied:
		entry["suspended"] = False
		return False

	identity = (entry["pid"], create_time)

	if (
		root_status == psutil.STATUS_STOPPED
		and identity not in _suspensions
	):
		# The root is stopped but Urcheon does not own that suspension.
		# Mark it so the monitor will avoid repeatedly targeting this entry.
		# Don't take ownership of a root stopped externally.
		entry["external_stop"] = create_time
		entry["suspended"] = False
		return False

	entry["external_stop"] = None

	if root_status == psutil.STATUS_STOPPED:
		_register_suspension_locked(
			entry, entry["pid"], create_time
		)

	success = True

	if root_status != psutil.STATUS_STOPPED:
		if not _suspend_process(entry, root):
			# Suspend the root first if it isn't already stopped.
			success = False

	# Suspend descendants as well: limiting only the root would leave worker
	# processes running and would not meaningfully pause the job.
	try:
		children = root.children(recursive=True)
	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		children = []
		success = False
	except psutil.AccessDenied:
		children = []
		success = False

	for process in children:
		if not _suspend_process(entry, process):
			success = False

	# Verify that the original root still exists and is stopped.
	try:
		if root.create_time() != create_time:
			success = False
		else:
			root_suspended = (
				entry["suspended_pids"].get(entry["pid"]) == create_time
				and root.status() == psutil.STATUS_STOPPED
			)

	except (
		psutil.NoSuchProcess,
		psutil.ZombieProcess,
		psutil.AccessDenied,
	):
		root_suspended = False
		success = False

	if success and root_suspended:
		entry["suspended"] = True
		return True

	# The tree was only partially suspended. Roll back new suspensions rather
	# than leaving a job in an inconsistent, partially paused state.
	_rollback_new_suspensions_locked(entry, previous)
	return False


def _try_resume(pid, create_time):
	# Best-effort resume for a process Urcheon believes it owns.
	try:
		process = psutil.Process(pid)

		if process.create_time() != create_time:
			# Treat PID reuse as the original process having disappeared.
			return True

		if process.status() != psutil.STATUS_STOPPED:
			# An external resume may already have made this process runnable.
			return True

		process.resume()

		# Confirm that the process is no longer stopped.
		return process.status() != psutil.STATUS_STOPPED

	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		return True
	except psutil.Error:
		return False


def _resume(entry):
	# Release this entry's ownership of each suspended process, in reverse
	# order. Shared processes are resumed only after their last owner releases.
	for pid, create_time in reversed(list(entry["suspended_pids"].items())):
		_release_suspension_locked(entry, pid, create_time)

	entry["suspended"] = entry["pid"] in entry["suspended_pids"]


def _retry_pending_resumes_locked():
	# Retry failed resumes on later monitor iterations. A new owner may have
	# acquired the suspension since it was queued, in which case do not resume.
	for pid, create_time in list(_pending_resumes):
		identity = (pid, create_time)
		record = _suspensions.get(identity)

		if record is not None and record["owners"]:
			# Ownership was reacquired; don't resume this process.
			_pending_resumes.pop(identity, None)
			continue

		if _try_resume(pid, create_time):
			_forget_suspended_process_locked(pid, create_time)


def _is_stopped(process):
	try:
		return process.status() == psutil.STATUS_STOPPED
	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		return True
	except psutil.AccessDenied:
		# Status is unknown, don't assume the process is stopped.
		return False


def _entry_active_thread_count_locked(entry):
	# Estimate active threads in one registered job's process tree.
	if entry["process"].poll() is not None:
		return 0

	processes = {}

	for process in _process_tree(entry["pid"]):
		try:
			identity = (process.pid, process.create_time())

			if _is_stopped(process):
	   			# Exclude stopped processes from the active-thread estimate.
				continue

		except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
			continue

		processes[identity] = process

	return sum(countThread(process) for process in processes.values())


def _active_thread_count_locked():
   	# Count each process at most once, even when registered job trees overlap.
	processes = {}

	for entry in _processes.values():
		if entry["process"].poll() is not None:
			continue

		for process in _process_tree(entry["pid"]):
			try:
				identity = (process.pid, process.create_time())

				if _is_stopped(process):
					continue

			except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
				continue

			processes[identity] = process

	total = 0

	for process in processes.values():
		total += countThread(process)

	return total


def _running_entries_locked():
	# Return registered jobs that are alive and currently contribute threads.
	return [
		entry
		for entry in _processes.values()
		if entry["process"].poll() is None
		and _entry_active_thread_count_locked(entry) > 0
	]


def _has_runnable_processes_locked(exclude=None):
	# Prevent the scheduler from suspending the last job that can make progress.
	for entry in _processes.values():
		if entry is exclude:
			continue

		if entry["process"].poll() is not None:
			continue

		if _entry_active_thread_count_locked(entry) > 0:
			return True

	return False



def _entry_resume_thread_count_locked(entry):
	# Estimate how many threads would become active if this entry's
	# exclusively owned suspended processes were resumed.
	processes = {}

	for pid, create_time in entry["suspended_pids"].items():
		identity = (pid, create_time)
		record = _suspensions.get(identity)

		if record is None or id(entry) not in record["owners"]:
			# This entry must own the suspension. Other entries may also
			# own it; their ownership will prevent a premature resume.
			continue

		try:
			process = psutil.Process(pid)

			if process.create_time() != create_time:
				continue

			if process.status() != psutil.STATUS_STOPPED:
				continue

			processes[identity] = process

		except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
			continue

	return sum(countThread(process) for process in processes.values())


def _root_stopped_externally_locked(entry):
	# An externally stopped root is not a useful suspension candidate.
	# Keep this marker while it remains stopped; clear it when it resumes.
	create_time = entry.get("external_stop")

	if create_time is None:
		return False

	try:
		root = psutil.Process(entry["pid"])

		if root.create_time() != create_time:
			entry["external_stop"] = None
			return False

		if root.status() == psutil.STATUS_STOPPED:
			return True

		entry["external_stop"] = None
		return False

	except (psutil.NoSuchProcess, psutil.ZombieProcess):
		entry["external_stop"] = None
		return False
	except psutil.AccessDenied:
		# Preserve the marker, don't retry a tree we cannot verify.
		return True


def _monitor_processes():
	# Continuously regulate aggregate subprocess thread usage.
	global _last_resume_time

	low, high = _get_watermarks()

	while True:
		time.sleep(MONITOR_INTERVAL)

		if logging.getLogger().isEnabledFor(logging.DEBUG):
			iteration_start = time.monotonic()

		try:
			with _process_lock:
				# Recover any suspensions whose previous resume failed.
				_retry_pending_resumes_locked()
				active_threads = _active_thread_count_locked()
				running = _running_entries_locked()

				if logging.getLogger().isEnabledFor(logging.DEBUG):
					logging.debug(
						"Monitor snapshot: active_threads=%d high=%d "
						"low=%d registered=%d running=%d suspended=%d "
						"pending_resumes=%d",
						active_threads,
						high,
						low,
						len(_processes),
						len(running),
						sum(
							1 for entry in _processes.values()
							if entry["suspended"]
						),
						len(_pending_resumes),
					)

				if logging.getLogger().isEnabledFor(logging.DEBUG):
					for entry in running:
						try:
							process = psutil.Process(entry["pid"])
							logging.debug(
								"Process pid=%d name=%s threads=%d children=%d",
								entry["pid"],
								process.name(),
								countThread(process),
								len(process.children(recursive=True)),
							)
						except psutil.Error:
							pass

				if active_threads > high:
					# Suspend jobs until usage falls to the low watermark.
					# Recalculate after each attempt because process trees
					# and their thread counts can change at any time.
					attempted = set()

					while active_threads > low:
						candidates = [
							entry for entry in _running_entries_locked()
							if entry["pid"] not in attempted
							and not _root_stopped_externally_locked(entry)
						]

						if not candidates:
							break

						thread_counts = {
							entry["pid"]: _entry_active_thread_count_locked(entry)
							for entry in candidates
						}

						# Ignore process trees that contribute no active threads.
						thread_counts = {
							pid: threads
							for pid, threads in thread_counts.items()
							if threads > 0
						}

						if not thread_counts:
							break

						# Prefer small trees to reduce the amount of work paused.
						smallest = min(thread_counts.values())
						smallest_candidates = [
							entry for entry in candidates
							if thread_counts.get(entry["pid"], 0) == smallest
						]

						# Randomize ties to avoid always favoring the same job.
						random.shuffle(smallest_candidates)
						entry = None

						for candidate in smallest_candidates:
							attempted.add(candidate["pid"])

							if _has_runnable_processes_locked(exclude=candidate):
								# Never suspend a candidate if doing so would leave
								# no other runnable job to make progress.
								entry = candidate
								break

						if entry is None:
							break

						suspended_successfully = _suspend(entry)

						# Refresh state after every attempt, successful or not.
						running = _running_entries_locked()
						active_threads = _active_thread_count_locked()

						if not suspended_successfully:
							logging.debug(
								"Suspension failed: pid=%d active=%d",
								entry["pid"],
								active_threads,
							)

				elif active_threads < low:
					# Resume jobs when capacity is available, but rate-limit
					# resumes to reduce oscillation around the thresholds.
					now = time.monotonic()

					if now - _last_resume_time >= RESUME_COOLDOWN:
						suspended = [
							entry for entry in _processes.values()
							if entry["process"].poll() is None
							and entry["suspended_pids"]
						]

						candidates = [
							(_entry_resume_thread_count_locked(entry), entry)
							for entry in suspended
						]

						# Consider the smallest process trees first.
						candidates = [
							(threads, entry)
							for threads, entry in candidates
							if threads > 0
						]
						candidates.sort(key=lambda candidate: candidate[0])

						if candidates:
							smallest_threads = candidates[0][0]

							# Only the smallest trees are eligible for resumption.
							smallest_candidates = [
								(threads, entry) for threads, entry in candidates
								if threads == smallest_threads
							]

							_, candidate_entry = random.choice(smallest_candidates)

							if active_threads + smallest_threads <= high:
								entry = candidate_entry

							elif not _has_runnable_processes_locked(exclude=candidate_entry):
								# Allow progress when no other runnable work remains.
								entry = candidate_entry

								logging.debug(
									"Overriding high watermark to resume "
									"the last runnable job: pid=%d threads=%d "
									"active=%d high=%d",
									entry["pid"],
									smallest_threads,
									active_threads,
									high,
								)

							else:
								entry = None

								logging.debug(
									"Skipping resume: smallest tree needs "
									"%d threads, active=%d high=%d",
									smallest_threads,
									active_threads,
									high,
								)

							if entry is not None:
								logging.debug(
									"Resuming process tree: pid=%d "
									"estimated_threads=%d active_before=%d high=%d",
									entry["pid"],
									smallest_threads,
									active_threads,
									high,
								)

								_resume(entry)
								_last_resume_time = now

						elif not running:
							# Normal estimates can exclude every candidate.
							# Recover a stopped root only when this entry is
							# the sole owner of its tracked suspension.
							recovery_candidates = []

							for candidate_entry in suspended:
								pid = candidate_entry["pid"]
								create_time = (
									candidate_entry["suspended_pids"].get(pid)
								)
								if create_time is None:
									continue

								identity = (pid, create_time)
								record = _suspensions.get(identity)
								if (
									record is None
									or record["owners"] != {id(candidate_entry)}
								):
									continue

								if _root_stopped_externally_locked(candidate_entry):
									continue

								try:
									root = psutil.Process(pid)
									if (
										root.create_time() != create_time
										or root.status() != psutil.STATUS_STOPPED
									):
										continue
								except psutil.Error:
									continue

								recovery_candidates.append(candidate_entry)

							if recovery_candidates:
								entry = random.choice(recovery_candidates)
								logging.warning(
									"No runnable jobs and no estimated resume "
									"candidates; recovering suspended root: pid=%d",
									entry["pid"],
								)
								_resume(entry)
								_last_resume_time = now

			if logging.getLogger().isEnabledFor(logging.DEBUG):
				elapsed = time.monotonic() - iteration_start

				if elapsed > MONITOR_INTERVAL:
					logging.debug(
						"Slow monitor iteration: elapsed=%.3fs interval=%.3fs",
						elapsed,
						MONITOR_INTERVAL,
					)

		except Exception:
			# Keep the monitor alive after unexpected errors in one iteration.
			logging.exception("Error in subprocess monitor")


def _start_monitor_locked():
	# Start one daemon monitor on demand, rather than creating a monitor
	# thread for every subprocess.
	global _monitor

	if _monitor is None or not _monitor.is_alive():
		_monitor = threading.Thread(
			target=_monitor_processes,
			name="UrcheonProcessMonitor",
			daemon=True,
		)
		logging.debug("Starting subprocess monitor")
		_monitor.start()


def _cleanup_suspensions():
	# Make a final best-effort attempt to release all outstanding suspensions
	# when Urcheon exits.
	with _process_lock:
		for pid, create_time in list(_suspensions):
			if _try_resume(pid, create_time):
				_forget_suspended_process_locked(pid, create_time)
			else:
				logging.error(
					"Unable to resume process during shutdown: pid=%d",
					pid,
				)


atexit.register(_cleanup_suspensions)


def call(*popenargs, **kwargs):
	# Wrapper for subprocess.Popen that integrates the process with the
	# scheduler and ensures its suspension ownership is released at completion.
	timeout = kwargs.pop("timeout", None)

	logging.debug("Parallelism.call invoked: %r", popenargs)

	with subprocess.Popen(*popenargs, **kwargs) as process:
		entry = {
			"pid": process.pid,
			"process": process,
			"suspended": False,
			"suspended_pids": {},
			"external_stop": None,
		}

		with _process_lock:
			_processes[process.pid] = entry
			_start_monitor_locked()

		try:
			try:
				return process.wait(timeout=timeout)
			except subprocess.TimeoutExpired:
				# Avoid leaving a timed-out child running after the call fails.
				process.kill()
				process.wait()
				raise

		finally:
			# Release owned suspensions and unregister the completed job.
			with _process_lock:
				_resume(entry)
				_processes.pop(process.pid, None)


# This extends threading.Thread to transmit exceptions
# back to the parent, best used with joinDeadThreads()
# on active thread list to raise exceptions early.
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
