"""Tests of storage/atomic.py and storage/files.py: atomic replace, start-up cleanup, the instance lock (WB-17 of
11-white-box-coverage-review.md). Every file the service writes (originals, drafts, versions, settings, page cache)
goes through ``atomic_write_bytes``, so a reader must never see a partial file and a failure must leave the old one.
"""
import json
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
from value_review.storage.files import AnnotationStore  # noqa: E402


class OtherProcess:
    """A real, running process other than this one: another instance holding the lock."""

    def __enter__(self):
        import subprocess
        self.proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        return self.proc.pid

    def __exit__(self, *exc):
        self.proc.kill()
        self.proc.wait()


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
                raise OSError(21, 'device not ready', str(self.target))   # OS errors carry the full file name
        with self.assertRaises(StorageError) as caught:
            atomic_write_bytes(self.target, b'new', fault=fail)
        self.assertEqual((self.target.read_bytes(), self.temporaries()), (b'old', []))
        self.assertEqual(str(caught.exception), 'Could not write v1.json: device not ready')   # contract: no absolute path

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
        locked = PermissionError(13, 'Access is denied', str(self.target))   # as Windows raises it: with the full path
        with mock.patch.object(atomic.os, 'replace', side_effect=locked) as replace, \
                self.assertRaises(StorageError) as caught:
            atomic_write_bytes(self.target, b'new', retries=4, backoff=0)
        self.assertEqual(replace.call_count, 4)
        self.assertEqual(str(caught.exception), 'Could not replace v1.json: Access is denied')   # contract: no absolute path
        self.assertEqual((self.target.read_bytes(), self.temporaries()), (b'old', []))

    def test_cleanup_touches_only_temporaries(self):
        self.write_old()
        (self.target.parent / 'v2.json.123.tmp').write_bytes(b'partial')
        self.assertEqual(remove_leftover_temporaries(self.target.parent), 1)
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()), ['v1.json'])


class AnnotationFiles(unittest.TestCase):
    """storage/files.py paths that only fail with damaged files or a disk that refuses (11-white-box-coverage-review.md, gap 2)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AnnotationStore(Path(self.tmp.name) / 'annotations')

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def denied(path):
        return PermissionError(13, 'Access is denied', str(path))   # as Windows raises it: with the full path

    @staticmethod
    def version(n):
        state = {'schema': 'value-review-state/1', 'decisions': {}, 'column_moves': {}, 'record_moves': {}, 'record_edits': {},
                 'added_records': [], 'added_values': [], 'boxes': {}}
        counts = {k: 0 for k in ('total', 'pending', 'accepted', 'corrected', 'rejected', 'unsure', 'added_values',
                                 'added_records', 'edited_records')}
        return {'schema': 'value-review-version/1', 'paper': '7', 'n': n, 'at': '2026-11-18T10:00:00Z', 'by': 'Expert reviewer',
                'note': 'Submitted', 'base_version': n - 1,
                'source': {'run_id': 'r', 'result_sha256': 'a' * 64, 'pdf_sha256': 'b' * 64, 'original_sha256': 'c' * 64},
                'state': state, 'counts': counts, 'values': []}

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_schema_invalid_files_are_reported_and_not_used(self):
        self.write(self.store.version_path('7', 1), self.version(1))
        self.assertEqual(self.store.read_version('7', 1)[1], None)   # the fixture itself is valid
        bad = self.version(2)
        del bad['state']
        self.write(self.store.version_path('7', 2), bad)
        data, problem = self.store.read_version('7', 2)
        self.assertIsNone(data)
        self.assertTrue(problem.startswith('v2.json: '), problem)
        k, latest, next_n, problems = self.store.current('7')
        self.assertEqual((k, latest['n'], next_n, len(problems)), (1, 1, 3, 1))   # v1 is current; v2's number is never reused
        self.write(self.store.draft_path('7'), {'schema': 'value-review-draft/1', 'paper': '7'})
        data, problem = self.store.read_draft('7')
        self.assertIsNone(data)
        self.assertTrue(problem.startswith('7.draft.json: '), problem)

    def test_validated_once_but_a_changed_file_is_read_again(self):  # B-2 of 13-performance-report.md
        path = self.store.version_path('7', 1)
        self.write(path, self.version(1))
        with mock.patch('value_review.schemas.errors', wraps=__import__('value_review.schemas', fromlist=['errors']).errors) as check:
            first = self.store.read_version('7', 1)
            again = self.store.read_version('7', 1)
            self.assertEqual(check.call_count, 1)   # the second read comes from the cache
        self.assertIs(first[0], again[0])
        bad = self.version(1)
        bad['by'] = ''   # invalid (minLength), and the file size changes
        self.write(path, bad)
        self.assertIsNone(self.store.read_version('7', 1)[0])
        good = json.dumps(self.version(1))
        path.write_text(good, encoding='utf-8')
        self.assertIsNotNone(self.store.read_version('7', 1)[0])
        st = path.stat()
        path.write_text(good.replace('"Submitted"', '"Submittex"'), encoding='utf-8')   # same size, new time
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        self.assertEqual(self.store.read_version('7', 1)[0]['note'], 'Submittex')

    def test_version_header_checks_only_the_header(self):  # listing versions without validating full snapshots
        broken_body = self.version(1)
        broken_body['values'] = [{'not': 'a value'}]
        self.write(self.store.version_path('7', 1), broken_body)
        header, problem = self.store.version_header('7', 1)
        self.assertIsNone(problem)
        self.assertEqual((header['n'], header['by'], 'state' in header, 'values' in header), (1, 'Expert reviewer', False, False))
        self.assertIsNone(self.store.read_version('7', 1)[0])   # opening it still finds the damage
        broken_header = self.version(2)
        broken_header['by'] = ''
        self.write(self.store.version_path('7', 2), broken_header)
        self.assertIsNone(self.store.version_header('7', 2)[0])
        self.write(self.store.version_path('7', 3), ['not', 'an', 'object'])
        self.assertEqual(self.store.version_header('7', 3), (None, 'v3.json: not an object'))

    def test_write_version_never_replaces_a_file(self):
        self.store.write_version('7', self.version(1))
        before = self.store.version_path('7', 1).read_bytes()
        with self.assertRaises(StorageError) as caught:
            self.store.write_version('7', {**self.version(1), 'note': 'Other'})
        self.assertEqual(str(caught.exception), 'v1.json already exists')
        self.assertEqual(self.store.version_path('7', 1).read_bytes(), before)   # BR-03: versions are immutable

    def test_prune_skips_a_file_deleted_meanwhile(self):
        for n in (2, 3):
            self.store.write_version('7', self.version(n))
        with mock.patch.object(self.store, 'version_numbers', return_value=[3, 2, 1]):   # v1 listed, then gone
            self.assertEqual(self.store.prune('7', 1), [2])
        self.assertEqual(self.store.version_numbers('7'), [3])

    def test_prune_failure_is_reported_without_the_path(self):
        for n in (1, 2):
            self.store.write_version('7', self.version(n))
        path = self.store.version_path('7', 1)
        with mock.patch.object(Path, 'unlink', side_effect=self.denied(path)), self.assertRaises(StorageError) as caught:
            self.store.prune('7', 1)
        self.assertEqual(str(caught.exception), 'Could not delete v1.json: Access is denied')
        self.assertTrue(path.exists())

    def test_delete_draft_failure_is_reported_without_the_path(self):
        self.assertFalse(self.store.delete_draft('7'))   # no draft: nothing to do
        self.write(self.store.draft_path('7'), {})
        with mock.patch.object(Path, 'unlink', side_effect=self.denied(self.store.draft_path('7'))), \
                self.assertRaises(StorageError) as caught:
            self.store.delete_draft('7')
        self.assertEqual(str(caught.exception), 'Could not delete the draft: Access is denied')
        self.assertTrue(self.store.draft_path('7').exists())


class StartUpCleanup(unittest.TestCase):
    def test_every_written_folder_of_every_pair_and_nothing_else(self):
        from value_review.__main__ import clean_leftovers
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            left = ['originals/7.json.1.tmp', 'annotations/settings.json.1.tmp', 'annotations/drafts/7.draft.json.1.tmp',
                    'annotations/versions/7/v2.json.1.tmp', 'cache/pages/7/abc-1-1200.png.1.tmp',
                    'sources/model-b/originals/9.json.2.tmp', 'sources/model-b/annotations/drafts/9.draft.json.2.tmp',
                    'sources/model-b/annotations/versions/9/v1.json.2.tmp', 'sources/model-b/cache/pages/9/x.png.2.tmp']
            kept = ['originals/7.json', 'annotations/versions/7/v1.json', 'sources/model-b/originals/9.json',
                    'frontend/node_modules/pkg/build.tmp', 'notes.tmp']   # not written by the service: never touched
            for rel in left + kept:
                (data / rel).parent.mkdir(parents=True, exist_ok=True)
                (data / rel).write_bytes(b'x')
            self.assertEqual(clean_leftovers(data), len(left))
            self.assertEqual(sorted(p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file()), sorted(kept))
            self.assertEqual(clean_leftovers(data / 'missing'), 0)


class Lock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'annotations' / 'value-review.lock'

    def tearDown(self):
        self.tmp.cleanup()

    def test_held_lock_refuses_a_second_instance_and_release_frees_it(self):
        with InstanceLock(self.path):
            self.assertEqual(self.path.read_text(), str(os.getpid()))
        self.assertFalse(self.path.exists())
        with OtherProcess() as pid:   # another instance, a live process, holds the lock
            self.path.write_text(str(pid))
            with self.assertRaises(StorageError):
                InstanceLock(self.path).acquire()
        InstanceLock(self.path).acquire().release()   # its process is gone: taken over

    def test_lock_left_with_our_own_pid_is_taken_over(self):
        # a container restarted after a crash: the new process often has the same pid (1) as the one that left the lock
        self.path.parent.mkdir(parents=True)
        self.path.write_text(str(os.getpid()))
        lock = InstanceLock(self.path).acquire()
        self.assertEqual(self.path.read_text(), str(os.getpid()))
        lock.release()
        self.assertFalse(self.path.exists())

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
