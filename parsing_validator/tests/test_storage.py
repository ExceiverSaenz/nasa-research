"""Tests of the storage layer: atomic writes, the instance lock, review and draft stores.

Covers AC-05, AC-06, AC-07, AC-08, AC-15 and AC-16 of the specification. Uses temporary folders only.
"""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from parsing_validator.storage import AnnotationStore, InstanceLock, RevisionConflict, StorageError, VersionError, atomic_write_bytes  # noqa: E402
from parsing_validator.storage import atomic as atomic_module  # noqa: E402

SOURCE = {'original_file': 'originals/7.json', 'original_sha256': 'a' * 64}


class Crash(BaseException):
    """Simulates the process dying at a step."""


def state(tag='table', marked=False):
    return {'reviewed': {'marked': marked, 'marked_at': None}, 'next_new_id': 1,
            'pages': {'7': {'reading_order': ['k8'], 'blocks': {'k8': {'status': 'accepted', 'tag': {'value': tag}}}}}}


def ticking_clock():
    counter = iter(range(1, 10 ** 6))
    return lambda: f'2026-11-13T12:00:{next(counter) % 60:02d}Z'


class Atomic(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / 'x.json'

    def tearDown(self):
        self.dir.cleanup()

    def test_replaces_and_leaves_no_temporary(self):
        atomic_write_bytes(self.path, b'one')
        atomic_write_bytes(self.path, b'two')
        self.assertEqual(self.path.read_bytes(), b'two')
        self.assertEqual(list(Path(self.dir.name).glob('*.tmp')), [])

    def test_crash_between_temp_and_replace_keeps_old_file_AC16(self):
        atomic_write_bytes(self.path, b'old')

        def die(step):
            if step == 'tmp_written':
                raise Crash()
        with self.assertRaises(Crash):
            atomic_write_bytes(self.path, b'new', fault=die)
        self.assertEqual(self.path.read_bytes(), b'old')  # a reader never sees a partial file
        self.assertEqual(len(list(Path(self.dir.name).glob('*.tmp'))), 1)  # left for start-up cleanup
        store = AnnotationStore(self.dir.name)
        self.assertEqual(store.startup()['temporaries_removed'], 1)
        self.assertEqual(list(Path(self.dir.name).glob('*.tmp')), [])

    def test_permission_error_is_retried_then_succeeds(self):
        real = os.replace
        calls = {'n': 0}

        def flaky(a, b):
            calls['n'] += 1
            if calls['n'] < 3:
                raise PermissionError('WinError 5')
            return real(a, b)
        with mock.patch.object(atomic_module.os, 'replace', flaky):
            atomic_write_bytes(self.path, b'ok', backoff=0.001)
        self.assertEqual((self.path.read_bytes(), calls['n']), (b'ok', 3))

    def test_permission_error_forever_fails_with_storage_error_and_old_file(self):
        atomic_write_bytes(self.path, b'old')
        with mock.patch.object(atomic_module.os, 'replace', side_effect=PermissionError('WinError 5')):
            with self.assertRaises(StorageError):
                atomic_write_bytes(self.path, b'new', backoff=0.001, retries=3)
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual(list(Path(self.dir.name).glob('*.tmp')), [])

    @unittest.skipUnless(sys.platform == 'win32', 'held handle semantics are Windows-specific')
    def test_held_handle_on_destination_is_retried_on_windows(self):
        atomic_write_bytes(self.path, b'old')
        handle = open(self.path, 'rb')
        threading.Timer(0.1, handle.close).start()
        atomic_write_bytes(self.path, b'new')  # the replace fails while the handle is open, then succeeds
        self.assertEqual(self.path.read_bytes(), b'new')

    @unittest.skipUnless(sys.platform == 'win32', 'held handle semantics are Windows-specific')
    def test_held_handle_never_released_gives_storage_error_on_windows(self):
        atomic_write_bytes(self.path, b'old')
        with open(self.path, 'rb'):
            with self.assertRaises(StorageError):
                atomic_write_bytes(self.path, b'new', backoff=0.001, retries=3)
        self.assertEqual(self.path.read_bytes(), b'old')


class Lock(unittest.TestCase):
    def test_second_instance_is_rejected_and_release_frees_it(self):
        with tempfile.TemporaryDirectory() as d:
            first = InstanceLock(Path(d) / '.lock').acquire()
            with self.assertRaises(StorageError):
                InstanceLock(Path(d) / '.lock').acquire()
            first.release()
            InstanceLock(Path(d) / '.lock').acquire().release()

    def test_stale_lock_of_a_dead_process_is_taken_over(self):
        with tempfile.TemporaryDirectory() as d:
            child = subprocess.Popen([sys.executable, '-c', 'pass'])
            child.wait()
            (Path(d) / '.lock').write_text(str(child.pid))
            lock = InstanceLock(Path(d) / '.lock').acquire()
            self.assertEqual((Path(d) / '.lock').read_text(), str(os.getpid()))
            lock.release()


class Stores(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = AnnotationStore(self.dir.name, now=ticking_clock())

    def tearDown(self):
        self.dir.cleanup()

    def commit(self, n=1, store=None):
        store = store or self.store
        for _ in range(n):
            store.save_review('7', state(), if_match=store.read('7')['revision'], source=SOURCE)

    def test_first_save_creates_revision_1_and_increments(self):
        self.assertEqual(self.store.read('7')['revision'], 0)
        self.commit(3)
        review = self.store.read('7')['review']
        self.assertEqual((review['revision'], review['source'], review['schema']), (3, SOURCE, 'parsing-validator-review/1'))

    def test_stale_if_match_is_a_conflict_and_changes_nothing_AC05(self):
        self.commit(3)
        before = self.store.review_path('7').read_bytes()
        self.store.save_draft('7', base_revision=3, trigger='manual', state=state())
        with self.assertRaises(RevisionConflict) as caught:
            self.store.save_review('7', state('text'), if_match=2, source=SOURCE)
        self.assertEqual((caught.exception.expected, caught.exception.stored), (2, 3))
        self.assertEqual(self.store.review_path('7').read_bytes(), before)
        self.assertTrue(self.store.draft_path('7').exists())

    def test_draft_leaves_review_byte_identical_AC06(self):
        self.commit(3)
        before = self.store.review_path('7').read_bytes()
        result = self.store.save_draft('7', base_revision=3, trigger='auto', state=state('text'),
                                       new_versions=[{'label': 'tag changed', 'at': 't', 'state': state('text')}])
        self.assertEqual(result['versions'], 1)
        self.assertEqual(self.store.review_path('7').read_bytes(), before)
        info = self.store.read('7')['draft']
        self.assertEqual((info['stale'], info['trigger']), (False, 'auto'))

    def test_save_removes_the_draft_and_keeps_no_versions(self):
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state())
        result = self.store.save_review('7', state(), if_match=0, source=SOURCE)
        self.assertEqual(result['warnings'], [])
        self.assertFalse(self.store.draft_path('7').exists())

    def test_stale_draft_is_reported_not_restored_not_deleted_AC07(self):
        self.commit(4)
        self.store.save_draft('7', base_revision=3, trigger='manual', state=state('text'))
        read = self.store.read('7')
        self.assertTrue(read['draft']['stale'])
        self.assertEqual(read['review']['revision'], 4)
        self.assertEqual(AnnotationStore(self.dir.name).startup()['stale_drafts'], ['7'])
        self.assertTrue(self.store.draft_path('7').exists())  # never deleted automatically (OQ-08)

    def test_crash_between_review_and_draft_removal_AC08(self):
        self.commit(3)
        self.store.save_draft('7', base_revision=3, trigger='manual', state=state('text'))

        def die(step):
            if step == 'review_written':
                raise Crash()
        crashing = AnnotationStore(self.dir.name, now=ticking_clock(), fault=die)
        with self.assertRaises(Crash):
            crashing.save_review('7', state('text'), if_match=3, source=SOURCE)
        restarted = AnnotationStore(self.dir.name)
        report = restarted.startup()
        read = restarted.read('7')
        self.assertEqual(read['review']['revision'], 4)  # the review has the new content
        self.assertEqual(read['review']['pages']['7']['blocks']['k8']['tag']['value'], 'text')
        self.assertTrue(read['draft']['stale'])  # the leftover draft is stale, not restored over newer data
        self.assertEqual(report['stale_drafts'], ['7'])
        self.assertTrue(restarted.draft_path('7').exists())
        restarted.discard_draft('7')  # only the user's choice removes it
        self.assertIsNone(restarted.read('7')['draft'])

    def test_real_process_kill_between_review_and_draft_removal(self):
        self.commit(3)
        self.store.save_draft('7', base_revision=3, trigger='manual', state=state())
        code = (
            'import os,sys; sys.path.insert(0, sys.argv[1]);'
            'from parsing_validator.storage import AnnotationStore;'
            'import json;'
            'st=json.loads(sys.argv[3]);'
            'f=lambda step: os._exit(7) if step=="review_written" else None;'
            'AnnotationStore(sys.argv[2], fault=f).save_review("7", st, if_match=3, source={"original_file":"o","original_sha256":"x"})')
        done = subprocess.run([sys.executable, '-c', code, str(ROOT), self.dir.name, __import__('json').dumps(state())])
        self.assertEqual(done.returncode, 7)
        read = AnnotationStore(self.dir.name).read('7')
        self.assertEqual((read['review']['revision'], read['draft']['stale']), (4, True))

    def test_invalid_review_file_is_reported_and_untouched_AC15(self):
        self.store.folder.mkdir(parents=True, exist_ok=True)
        self.store.review_path('7').write_bytes(b'{not json')
        read = self.store.read('7')
        self.assertIsNone(read['review'])
        self.assertEqual(read['revision'], 0)
        self.assertEqual(read['warnings'], [{'code': 'file_invalid', 'file': '7.review.json'}])
        self.assertEqual(self.store.review_path('7').read_bytes(), b'{not json')

    def test_review_of_another_paper_or_wrong_schema_is_invalid(self):
        self.commit(1)
        raw = self.store.review_path('7').read_text(encoding='utf8')
        self.store.review_path('7').write_text(raw.replace('"paper": "7"', '"paper": "9"'), encoding='utf8')
        self.assertEqual(self.store.read('7')['warnings'][0]['code'], 'file_invalid')

    def versions(self, n, start=0):
        return [{'label': f'v{i}', 'at': 't', 'state': state(tag=f'tag{i}')} for i in range(start, start + n)]

    def test_versions_are_capped_keeping_the_newest(self):
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state('tag129'), new_versions=self.versions(130))
        listing = self.store.draft_versions('7')
        self.assertEqual((len(listing), listing[0]['label'], listing[-1]['label']), (100, 'v30', 'v129'))

    def test_each_version_is_rebuilt_exactly_from_the_current_state(self):
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state('tag11'), new_versions=self.versions(12))
        for i in range(12):
            self.assertEqual(self.store.version_state('7', i), state(f'tag{i}'))

    def test_versions_added_across_saves_keep_the_chain_intact(self):
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state('tag3'), new_versions=self.versions(4))
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state('tag6'), new_versions=self.versions(3, start=4))
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state('tag7'), new_versions=self.versions(1, start=7))
        self.assertEqual([v['label'] for v in self.store.draft_versions('7')], [f'v{i}' for i in range(8)])
        for i in range(8):
            self.assertEqual(self.store.version_state('7', i), state(f'tag{i}'))

    def test_a_corrupted_patch_is_detected_by_the_hash(self):
        import json
        self.store.save_draft('7', base_revision=0, trigger='manual', state=state('tag4'), new_versions=self.versions(5))
        path = self.store.draft_path('7')
        draft = json.loads(path.read_text(encoding='utf8'))
        draft['versions'][3]['undo'][0]['value'] = 'tampered'
        path.write_text(json.dumps(draft), encoding='utf8')
        self.store.version_state('7', 4)  # later versions do not depend on the broken patch
        with self.assertRaises(VersionError):
            self.store.version_state('7', 3)  # the target's own patch is wrong: the hash check catches it
        with self.assertRaises(VersionError):
            self.store.version_state('7', 99)

    def test_a_draft_without_new_versions_keeps_the_existing_chain(self):
        self.store.save_draft('7', base_revision=0, trigger='auto', state=state('tag2'), new_versions=self.versions(3))
        self.store.save_draft('7', base_revision=0, trigger='pagehide', state=state('tag2', marked=True))
        self.assertEqual(len(self.store.draft_versions('7')), 3)
        self.assertEqual(self.store.version_state('7', 1), state('tag1'))
        self.assertTrue(self.store.read('7')['draft_file']['state']['reviewed']['marked'])

    def test_paper_ids_are_digits_only(self):
        for bad in ('../x', '7/../8', 'a', '', '7.review'):
            with self.assertRaises(ValueError):
                self.store.review_path(bad)

    def test_locks_are_taken_in_numeric_order(self):
        order = [id(l) for l in self.store.all_locks(['10', '9', '7'])]
        self.assertEqual(order, [id(self.store.lock(p)) for p in ('7', '9', '10')])

    def test_shape_errors_raise_before_anything_is_written(self):
        with self.assertRaises(ValueError):
            self.store.save_draft('7', base_revision=0, trigger='sometimes', state=state())
        self.assertFalse(self.store.draft_path('7').exists())


if __name__ == '__main__':
    unittest.main()
