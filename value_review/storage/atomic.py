"""Atomic replace and the single-instance lock.

Copied from parsing_validator/storage/atomic.py (ADR-001: copy, do not import).

A reader never sees a partial file: the data goes to a temporary file in the destination
folder, is flushed and closed, and then replaces the destination. On Windows the replace
can fail transiently (``PermissionError``, cause in this repository undetermined), so it is
retried a bounded number of times and then fails with ``StorageError``, leaving the old file.
"""
import os
import sys
import time
from pathlib import Path

RETRIES = 6
BACKOFF_SECONDS = 0.02


class StorageError(Exception):
    """A write failed; the previous file is intact."""


def reason(error):
    """The OS's reason for a failed file operation, without the file name: the text of an OSError carries the full
    path, and StorageError messages reach the client (contract: no absolute path in error messages)."""
    return getattr(error, 'strerror', None) or type(error).__name__


def atomic_write_bytes(path, data, *, fault=None, retries=RETRIES, backoff=BACKOFF_SECONDS):
    """Replace ``path`` with ``data`` atomically.

    ``fault`` is a test hook called as ``fault('tmp_written')`` after the temporary file is
    complete and closed, and as ``fault('replaced')`` after the replace.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    try:
        with open(temp, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if fault:
            fault('tmp_written')
        for attempt in range(retries):
            try:
                os.replace(temp, path)
                break
            except PermissionError as error:
                if attempt == retries - 1:
                    raise StorageError(f'Could not replace {path.name}: {reason(error)}') from error
                time.sleep(backoff * (2 ** attempt))
        if fault:
            fault('replaced')
    except StorageError:
        _discard(temp)
        raise
    except OSError as error:
        _discard(temp)
        raise StorageError(f'Could not write {path.name}: {reason(error)}') from error
    except BaseException:
        # A simulated or real crash after the temporary file exists leaves it for the start-up cleanup.
        raise


def _discard(temp):
    try:
        Path(temp).unlink()
    except OSError:
        pass


def remove_leftover_temporaries(folder):
    """Delete ``*.tmp`` files left by an interrupted write; they are never read. Returns the count."""
    count = 0
    for temp in Path(folder).glob('*.tmp'):
        _discard(temp)
        count += 1
    return count


def pid_alive(pid):
    """Whether a process with this id exists (cross-platform)."""
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class InstanceLock:
    """Lock file created exclusively and holding the process id; a stale lock is taken over."""

    def __init__(self, path):
        self.path = Path(path)
        self._held = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._owner_alive():
                    raise StorageError('Another instance is running (lock held)') from None
                _discard(self.path)  # stale: its process is gone
                continue
            with os.fdopen(descriptor, 'w') as handle:
                handle.write(str(os.getpid()))
            self._held = True
            return self
        raise StorageError('Could not take the instance lock')

    def _owner_alive(self):
        try:
            pid = int(self.path.read_text().strip())
        except (OSError, ValueError):
            return False
        # Our own pid: left by an earlier run that had the same pid (a container restarted, where the process is
        # usually pid 1 again). Whoever wrote it is gone, since this process is the one starting.
        return pid != os.getpid() and pid_alive(pid)

    def release(self):
        if self._held:
            _discard(self.path)
            self._held = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
