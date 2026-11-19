"""Tests of storage/atomic.py: atomic replace, start-up cleanup and the instance lock (WB-17 of
11-white-box-coverage-review.md). Every file the service writes (originals, drafts, versions, settings, page cache)
goes through ``atomic_write_bytes``, so a reader must never see a partial file and a failure must leave the old one.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.storage import atomic  # noqa: E402
from value_review.storage.atomic import InstanceLock, StorageError, atomic_write_bytes, remove_leftover_temporaries  # noqa: E402


class Crash(BaseException):
    """Stands for the process dying (not an OSError): nothing is cleaned up on the way out."""


class AtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.target = self.dir / 'versions' / '7' / 'v1.json'

    def tearDown(self):
        self.tmp.cleanup()

    def temporaries(self):
        return sorted(p.name for p in self.dir.rglob('*.tmp'))

    def write_old(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'old')

    def test_new_file_and_parent_folders(self):
        atomic_write_bytes(self.target, b'new')
        self.assertEqual((self.target.read_bytes(), self.temporaries()), (b'new', []))

    def test_replaces_and_reports_both_fault_points(self):
        self.write_old()
        points = []
        atomic_write_bytes(self.target, b'new', fault=points.append)
        self.assertEqual((self.target.read_bytes(), points, self.temporaries()), (b'new', ['tmp_written', 'replaced'], []))

    def test_os_error_before_replace_keeps_the_old_file_and_no_temporary(self):
        self.write_old()

        def fail(point):
            if point == 'tmp_written':
                raise OSError('device not ready')
        with self.assertRaises(StorageError):
            atomic_write_bytes(self.target, b'new', fault=fail)
        self.assertEqual((self.target.read_bytes(), self.temporaries()), (b'old', []))

    def test_crash_after_temporary_leaves_it_for_the_start_up_cleanup(self):
        self.write_old()

        def crash(point):
            if point == 'tmp_written':
                raise Crash()
        with self.assertRaises(Crash):
            atomic_write_bytes(self.target, b'new', fault=crash)
        self.assertEqual(self.target.read_bytes(), b'old')   # a reader still sees the whole old file
        self.assertEqual(len(self.temporaries()), 1)
        self.assertEqual(remove_leftover_temporaries(self.target.parent), 1)
        self.assertEqual((self.temporaries(), self.target.read_bytes()), ([], b'old'))

    def test_transient_permission_error_is_retried(self):
        self.write_old()
        real, calls = os.replace, []

        def flaky(src, dst):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError('in use by another process')
            real(src, dst)
        with mock.patch.object(atomic.os, 'replace', flaky):
            atomic_write_bytes(self.target, b'new', retries=6, backoff=0)
        self.assertEqual((len(calls), self.target.read_bytes(), self.temporaries()), (3, b'new', []))

    def test_permission_error_on_every_try_fails_and_keeps_the_old_file(self):
        self.write_old()
        with mock.patch.object(atomic.os, 'replace', side_effect=PermissionError('locked')) as replace, \
                self.assertRaises(StorageError) as caught:
            atomic_write_bytes(self.target, b'new', retries=4, backoff=0)
        self.assertEqual(replace.call_count, 4)
        self.assertIn('v1.json', str(caught.exception))
        self.assertNotIn(self.tmp.name, str(caught.exception))   # contract: no absolute path in messages
        self.assertEqual((self.target.read_bytes(), self.temporaries()), (b'old', []))

    def test_cleanup_touches_only_temporaries(self):
        self.write_old()
        (self.target.parent / 'v2.json.123.tmp').write_bytes(b'partial')
        self.assertEqual(remove_leftover_temporaries(self.target.parent), 1)
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()), ['v1.json'])


class Lock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'annotations' / 'value-review.lock'

    def tearDown(self):
        self.tmp.cleanup()

    def test_held_lock_refuses_a_second_instance_and_release_frees_it(self):
        with InstanceLock(self.path):
            self.assertEqual(self.path.read_text(), str(os.getpid()))
            with self.assertRaises(StorageError):
                InstanceLock(self.path).acquire()
        self.assertFalse(self.path.exists())
        InstanceLock(self.path).acquire().release()

    def test_stale_or_unreadable_lock_is_taken_over(self):
        for content in ('0', 'not a pid', ''):
            with self.subTest(content=content):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(content)
                lock = InstanceLock(self.path).acquire()
                self.assertEqual(self.path.read_text(), str(os.getpid()))
                lock.release()

    def test_release_without_acquire_leaves_another_owners_lock(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(str(os.getpid()))
        InstanceLock(self.path).release()
        self.assertTrue(self.path.exists())


if __name__ == '__main__':
    unittest.main()
