"""Tests of the read API (step 3): OP-01, OP-02, OP-03, OP-10, OP-11, the Host check and the instance lock.

Covers AC-01, AC-02, AC-18 (read side) and AC-20. Synthetic sources and data folders in temporary
folders; a short smoke test runs on the real originals when the sources are present.
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import config as vr_config, schemas  # noqa: E402
from value_review.__main__ import main as launch  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.ingest import ingest_run  # noqa: E402
from value_review.service.app import create_app  # noqa: E402
from value_review.service.config import Config  # noqa: E402
from value_review.storage import InstanceLock, StorageError  # noqa: E402
from value_review.storage.files import AnnotationStore  # noqa: E402
from value_review.tests.test_ingest import make_pdf, result, sha  # noqa: E402

PNG = b'\x89PNG\r\n\x1a\n'
AT0, AT1, AT2 = '2026-11-16T10:00:00Z', '2026-11-16T11:00:00Z', '2026-11-16T12:00:00Z'


def decision(verdict='accepted', note=''):
    return {'verdict': verdict, 'note': note, 'by': 'Expert reviewer', 'at': AT1}


def version_file(original, n, state, at):
    return {'schema': 'value-review-version/1', 'paper': original['paper'], 'n': n, 'at': at, 'by': 'Expert reviewer',
            'note': 'Submitted', 'base_version': n - 1,
            'source': {'run_id': 'run-test', 'result_sha256': original['source']['result_sha256'],
                       'pdf_sha256': original['source']['pdf_sha256'], 'original_sha256': 'b' * 64},
            'state': state,
            'counts': {'total': 4, 'pending': 4 - len(state['decisions']), 'accepted': len(state['decisions']), 'corrected': 0,
                       'rejected': 0, 'unsure': 0, 'added_values': 0, 'added_records': 0, 'edited_records': 0},
            'values': []}


class Base(unittest.TestCase):
    PORT = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.run, self.pdfs, self.data = d / 'run', d / 'pdfs', d / 'data'
        self.run.mkdir()
        self.pdfs.mkdir()
        self.pdf = self.pdfs / '7.pdf'
        make_pdf(self.pdf, [(612, 792), (612, 792)])
        self.res = self.run / '7-pdf_with_feature_guide.json'
        self.res.write_text(json.dumps(result(sha(self.pdf)), ensure_ascii=False), encoding='utf-8')
        ingest_run(self.run, self.pdfs, self.data / 'originals')
        self.original = json.loads((self.data / 'originals' / '7.json').read_text(encoding='utf-8'))
        self.config = Config(data=self.data, run_dir=self.run, pdf_dir=self.pdfs, port=self.PORT)
        self.client = TestClient(create_app(self.config, web_dir=None), base_url='http://127.0.0.1')
        self.store = AnnotationStore(self.config.annotations)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


class Papers(Base):  # OP-01, AC-01
    def test_fresh_paper(self):
        r = self.client.get('/api/v1/papers')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [{
            'paper': '7', 'title': 'A test paper', 'pages': 2, 'records': 2, 'values': 4, 'needs_check': 3,
            'reviewed': 0, 'total': 4, 'status': 'not_started', 'version': 0, 'latest': None, 'draft_at': None,
            'source_changed': False, 'source_problems': [], 'completion': 'partial'}])

    def test_latest_version_and_newer_draft(self):
        s1 = empty_state()
        s1['decisions'] = {'o1': decision()}
        self.write_json(self.store.version_path('7', 1), version_file(self.original, 1, s1, AT1))
        row = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual((row['version'], row['latest'], row['reviewed'], row['status']),
                         (1, {'n': 1, 'at': AT1, 'by': 'Expert reviewer'}, 1, 'in_progress'))
        s2 = empty_state()
        s2['decisions'] = {k: decision() for k in ('o1', 'o2', 'o3', 'o4')}
        self.write_json(self.store.draft_path('7'), {'schema': 'value-review-draft/1', 'paper': '7', 'base_version': 1,
                                                     'trigger': 'auto', 'saved_at': AT2, 'state': s2})
        row = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual((row['reviewed'], row['status'], row['draft_at']), (4, 'done', AT2))

    def test_unreadable_files_are_reported_not_fatal(self):
        bad = self.store.version_path('7', 2)
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text('{not json', encoding='utf-8')
        s1 = empty_state()
        self.write_json(self.store.version_path('7', 1), version_file(self.original, 1, s1, AT1))
        row = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual(row['version'], 1)
        self.assertEqual(len(row['warnings']), 1)
        self.assertTrue(row['warnings'][0].startswith('v2.json'))
        self.assertTrue(bad.exists())  # never repaired or deleted

    def test_unreadable_draft_is_reported_and_not_offered(self):
        self.store.draft_path('7').parent.mkdir(parents=True, exist_ok=True)
        self.store.draft_path('7').write_text('{not json', encoding='utf-8')
        opened = self.client.get('/api/v1/papers/7').json()
        self.assertEqual((opened['draft'], opened['warnings']), (None, ['7.draft.json: JSONDecodeError']))
        row = self.client.get('/api/v1/papers').json()[0]
        self.assertEqual((row['draft_at'], row['status'], row['warnings']), (None, 'not_started', ['7.draft.json: JSONDecodeError']))
        self.assertTrue(self.store.draft_path('7').exists())   # never repaired or deleted

    def test_source_changed_is_flagged(self):  # AC-18
        self.res.write_text(self.res.read_text(encoding='utf-8').replace('710', '711'), encoding='utf-8')
        self.assertTrue(self.client.get('/api/v1/papers').json()[0]['source_changed'])
        r = self.client.get('/api/v1/papers/7').json()
        self.assertEqual((r['source_changed'], r['source_problems']), (True, ['result_changed']))


class OpenPaper(Base):  # OP-02, AC-02
    def test_fresh(self):
        r = self.client.get('/api/v1/papers/7')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['etag'], '"0"')
        body = r.json()
        self.assertEqual(body['original'], self.original)
        self.assertEqual((body['version'], body['current'], body['draft'], body['draft_stale'], body['source_changed']),
                         (0, empty_state(), None, False, False))
        self.assertEqual(schemas.errors('state', body['current']), [])
        ev = body['original']['observations'][0]['evidence'][0]
        self.assertEqual((ev['page'], ev['bbox']), (1, [0.5262, 0.3837, 0.5763, 0.3932]))
        catalog = body['feature_catalog']
        self.assertEqual(len(catalog), 54)   # the extraction guide's columns
        self.assertIn({'feature_id': 'strain_rate', 'label': 'Strain rate'}, catalog)

    def test_version_and_stale_draft(self):
        s1 = empty_state()
        s1['decisions'] = {'o1': decision('rejected', 'It belongs to another record')}
        self.write_json(self.store.version_path('7', 1), version_file(self.original, 1, s1, AT1))
        self.write_json(self.store.draft_path('7'), {'schema': 'value-review-draft/1', 'paper': '7', 'base_version': 0,
                                                     'trigger': 'manual', 'saved_at': AT0, 'state': empty_state()})
        r = self.client.get('/api/v1/papers/7')
        self.assertEqual(r.headers['etag'], '"1"')
        body = r.json()
        self.assertEqual((body['version'], body['current'], body['draft_stale']), (1, s1, True))

    def test_unknown_or_malformed_ids(self):
        for path in ('/api/v1/papers/8', '/api/v1/papers/abc', '/api/v1/papers/..%2Foriginals%2F7'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 404, path)
            self.assertIn(r.json()['error']['code'], ('paper_not_found', 'not_found'))


class PageImages(Base):  # OP-03
    def test_png_rendered_once_and_cached(self):
        r = self.client.get('/api/v1/papers/7/pages/1/image?w=1000')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['content-type'], 'image/png')
        self.assertIn('immutable', r.headers['cache-control'])
        self.assertTrue(r.content.startswith(PNG))
        files = list((self.data / 'cache' / 'pages' / '7').glob('*.png'))
        self.assertEqual([f.name.split('-', 1)[1] for f in files], ['1-1000.png'])
        mtime = files[0].stat().st_mtime_ns
        self.assertEqual(self.client.get('/api/v1/papers/7/pages/1/image?w=1000').content, r.content)
        self.assertEqual(files[0].stat().st_mtime_ns, mtime)

    def test_width_is_snapped_and_validated(self):
        self.client.get('/api/v1/papers/7/pages/2/image?w=1290')
        self.assertTrue(any(f.name.endswith('-2-1200.png') for f in (self.data / 'cache' / 'pages' / '7').glob('*.png')))
        self.assertEqual(self.client.get('/api/v1/papers/7/pages/1/image?w=100').status_code, 400)

    def test_prefetch_yields_to_the_reviewer(self):  # B-4 of 13-performance-report.md
        library = self.client.app.state.source().library
        url = '/api/v1/papers/7/pages/2/image?w=800&prefetch=true'
        library._render_lock.acquire()   # a reviewer's page is being rendered
        try:
            r = self.client.get(url)
        finally:
            library._render_lock.release()
        self.assertEqual((r.status_code, r.content), (204, b''))
        self.assertFalse(any((self.data / 'cache').rglob('*-2-800.png')))
        r = self.client.get(url)   # free: rendered into the cache
        self.assertEqual((r.status_code, r.content[:len(PNG)]), (200, PNG))
        self.assertTrue(any((self.data / 'cache').rglob('*-2-800.png')))
        self.assertEqual(self.client.get('/api/v1/papers/7/pages/2/image?w=800').content, r.content)   # the reviewer gets it from the cache

    def test_page_out_of_range(self):
        r = self.client.get('/api/v1/papers/7/pages/3/image')
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'page_not_found'))

    def test_changed_pdf_is_refused(self):  # BR-09
        make_pdf(self.pdf, [(612, 792), (612, 792), (612, 792)])
        r = self.client.get('/api/v1/papers/7/pages/1/image')
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))

    def test_sources_untouched(self):  # BR-01
        before = (sha(self.res), sha(self.pdf))
        self.client.get('/api/v1/papers')
        self.client.get('/api/v1/papers/7')
        self.client.get('/api/v1/papers/7/pages/1/image')
        self.assertEqual((sha(self.res), sha(self.pdf)), before)


class SettingsAndHealth(Base):  # OP-10, OP-11
    def test_defaults_and_update(self):
        folders = {'sources': [{'id': 'default', 'name': 'run', 'run_dir': str(self.run), 'pdf_dir': str(self.pdfs)}],
                   'active_source': 'default'}
        self.assertEqual(self.client.get('/api/v1/settings').json(), {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5, **folders})
        new = {'reviewer_name': 'Dr. Reviewer', 'keep_versions': 5, 'autosave_minutes': 10}
        self.assertEqual(self.client.put('/api/v1/settings', json=new).json(), {**new, **folders})   # folders left out: unchanged
        self.assertEqual(json.loads(self.store.settings_path.read_text(encoding='utf-8')), {**new, **folders})

    def test_invalid_settings_rejected(self):
        for bad in ({'reviewer_name': '', 'keep_versions': 20, 'autosave_minutes': 5},
                    {'reviewer_name': 'x', 'keep_versions': 0, 'autosave_minutes': 5},
                    {'reviewer_name': 'x', 'keep_versions': 20, 'autosave_minutes': 5, 'extra': 1}):
            r = self.client.put('/api/v1/settings', json=bad)
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'), bad)
        self.assertFalse(self.store.settings_path.exists())

    def test_health(self):
        self.assertEqual(self.client.get('/api/v1/health').json(), {'status': 'ok', 'papers': 1, 'data_dir_writable': True})

    def test_unknown_endpoint(self):
        r = self.client.get('/api/v1/nothing')
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'not_found'))

    def test_health_reports_an_unwritable_data_folder(self):
        with mock.patch('value_review.service.app.tempfile.mkstemp', side_effect=PermissionError(13, 'Access is denied')):
            body = self.client.get('/api/v1/health').json()
        self.assertEqual(body, {'status': 'degraded', 'papers': 1, 'data_dir_writable': False})

    def test_settings_that_cannot_be_saved(self):
        before = self.client.get('/api/v1/settings').json()
        new = {k: before[k] for k in ('keep_versions', 'autosave_minutes')}
        with mock.patch.object(AnnotationStore, 'save_settings', side_effect=StorageError('Could not write settings.json: Access is denied')):
            r = self.client.put('/api/v1/settings', json={**new, 'reviewer_name': 'Dr. R'})
            self.assertEqual((r.status_code, r.json()['error']), (500, {
                'code': 'storage_error', 'message': 'Could not write settings.json: Access is denied', 'details': {}}))
            r = self.client.put('/api/v1/active-source', json={'source': 'default'})
            self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertEqual(self.client.get('/api/v1/settings').json(), before)   # nothing changed

    def test_last_folder_messages(self):
        empty = Path(self.tmp.name) / 'no pdfs'
        empty.mkdir()
        pair = {'id': 'default', 'name': 'run', 'run_dir': str(self.run)}
        base = {'reviewer_name': 'R', 'keep_versions': 20, 'autosave_minutes': 5}
        r = self.client.put('/api/v1/settings', json={**base, 'sources': [{**pair, 'pdf_dir': str(empty)}]})
        self.assertEqual(r.json()['error']['details']['fields'], {'sources.0.pdf_dir': 'No PDF files in this folder.'})
        r = self.client.put('/api/v1/settings', json={**base, 'sources': [{**pair, 'pdf_dir': '   '}]})
        self.assertEqual(r.json()['error']['details']['fields'], {'sources.0.pdf_dir': 'Type the folder.'})


class LocalOnly(Base):  # AC-20
    PORT = 8766

    def test_non_local_host_or_origin_refused(self):
        for headers in ({'host': 'evil.example'}, {'host': '127.0.0.1:9999'}, {'host': '127.0.0.1:8766', 'origin': 'http://evil.example'}):
            r = self.client.get('/api/v1/health', headers=headers)
            self.assertEqual((r.status_code, r.json()['error']['code']), (403, 'forbidden_host'), headers)

    def test_malformed_host_port_refused(self):
        for host in ('127.0.0.1:abc', '127.0.0.1:99999', 'localhost:'):
            r = self.client.get('/api/v1/health', headers={'host': host})
            self.assertEqual(r.status_code, 403 if host != 'localhost:' else 200, host)

    def test_local_names_served(self):
        for host in ('127.0.0.1:8766', 'localhost:8766', 'localhost'):
            self.assertEqual(self.client.get('/api/v1/health', headers={'host': host}).status_code, 200, host)

    def test_second_instance_refused(self):
        lock = InstanceLock(self.store.lock_path).acquire()
        try:
            with self.assertRaises(StorageError):
                InstanceLock(self.store.lock_path).acquire()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(launch(['--no-browser', '--data', str(self.data), '--port', '8799']), 2)
            self.assertIn('already running', err.getvalue())
        finally:
            lock.release()
        self.assertFalse(self.store.lock_path.exists())

    def test_port_in_use_refused_and_lock_released(self):
        (self.store.folder / 'drafts').mkdir(parents=True, exist_ok=True)
        leftover = self.store.folder / 'drafts' / '7.draft.json.99.tmp'
        leftover.write_bytes(b'partial')
        err = io.StringIO()
        # A real server must never start here: if the port check broke, the test fails at once instead of hanging.
        with mock.patch('value_review.__main__.port_is_free', return_value=False), contextlib.redirect_stderr(err), \
                mock.patch('uvicorn.Server', side_effect=AssertionError('the server started on a busy port')):
            self.assertEqual(launch(['--no-browser', '--data', str(self.data), '--port', '8799']), 2)
        self.assertIn('Port 8799 is in use', err.getvalue())
        self.assertFalse(self.store.lock_path.exists())
        self.assertFalse(leftover.exists())   # cleaned before the port check

    def test_launcher_serves_opens_the_browser_and_releases_the_lock(self):
        started = {}

        class FakeServer:   # stands in for uvicorn.Server: no real port is opened
            def __init__(self, config):
                started['config'] = config
                self.started, self.should_exit = False, False

            def run(self):
                started['lock_held'] = self_store.lock_path.exists()
                self.started = True
                for _ in range(50):   # give the browser thread time to see the server start
                    if opened:
                        break
                    import time
                    time.sleep(0.05)

        self_store, opened = self.store, []
        out = io.StringIO()
        with mock.patch('uvicorn.Server', FakeServer), mock.patch('value_review.__main__.port_is_free', return_value=True), \
                mock.patch('value_review.__main__.webbrowser.open', side_effect=opened.append), contextlib.redirect_stdout(out):
            self.assertEqual(launch(['--data', str(self.data), '--port', '8799']), 0)
        config = started['config']
        self.assertEqual((config.host, config.port, config.workers), ('127.0.0.1', 8799, 1))
        self.assertTrue(started['lock_held'])
        self.assertEqual(opened, ['http://127.0.0.1:8799/'])
        self.assertIn('Tensile Value Review on http://127.0.0.1:8799/', out.getvalue())
        self.assertFalse(self.store.lock_path.exists())


class EdgePaths(Base):
    def test_page_image_storage_error(self):
        from value_review.service.library import Library
        with mock.patch.object(Library, 'page_png', side_effect=StorageError('Could not write abc-1-1200.png: Disk full')):
            r = self.client.get('/api/v1/papers/7/pages/1/image')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['message']),
                         (500, 'storage_error', 'Could not write abc-1-1200.png: Disk full'))

    def test_method_not_allowed_uses_the_error_shape(self):
        r = self.client.patch('/api/v1/settings', json={})
        self.assertEqual((r.status_code, r.json()['error']['code']), (405, 'invalid_request'))

    def test_data_folder_without_originals(self):
        with tempfile.TemporaryDirectory() as tmp, \
                TestClient(create_app(Config(data=Path(tmp), run_dir=self.run, pdf_dir=self.pdfs), web_dir=None), base_url='http://127.0.0.1') as client:
            self.assertEqual(client.get('/api/v1/papers').json(), [])
            self.assertEqual(client.get('/api/v1/health').json()['papers'], 0)

    def test_folder_settings_from_the_environment(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict('os.environ', {'VALUE_REVIEW_SOURCE_ROOT': tmp, 'VALUE_REVIEW_DATA': tmp}):
            self.assertEqual(vr_config.source_root(), Path(tmp))
            self.assertEqual(vr_config.data_root(), Path(tmp))
            self.assertEqual(vr_config.originals_dir(), Path(tmp) / 'originals')
            self.assertEqual((Config().originals, Config().cache), (Path(tmp) / 'originals', Path(tmp) / 'cache'))
        with mock.patch.dict('os.environ', {}, clear=False), mock.patch.object(vr_config, 'REPO_ROOT', Path(self.tmp.name) / 'nowhere'):
            import os
            os.environ.pop('VALUE_REVIEW_SOURCE_ROOT', None)
            self.assertEqual(vr_config.source_root(), Path(self.tmp.name) / 'nowhere')   # no sources found: the repository root


@unittest.skipUnless(vr_config.default_run_dir().is_dir() and vr_config.default_pdf_dir().is_dir(),
                     'LLM run or PDFs not found; set VALUE_REVIEW_SOURCE_ROOT')
class RealPapers(unittest.TestCase):  # AC-01, AC-02 on the real run
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data = Path(cls.tmp.name)
        ingest_run(vr_config.default_run_dir(), vr_config.default_pdf_dir(), data / 'originals')
        cls.client = TestClient(create_app(Config(data=data), web_dir=None), base_url='http://127.0.0.1')

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.tmp.cleanup()

    def test_fourteen_papers(self):
        rows = self.client.get('/api/v1/papers').json()
        self.assertEqual(len(rows), 14)
        self.assertEqual(sum(r['values'] for r in rows), 2581)
        p1 = rows[0]
        self.assertEqual((p1['paper'], p1['values'], p1['needs_check'], p1['status'], p1['source_changed']), ('1', 255, 6, 'not_started', False))

    def test_paper_1_page_5_renders(self):
        body = self.client.get('/api/v1/papers/1').json()
        first = body['original']['observations'][0]
        self.assertEqual((first['value'], first['evidence'][0]['page']), ('710 ± 25', 5))
        r = self.client.get('/api/v1/papers/1/pages/5/image')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(PNG))
        self.assertEqual(hashlib.sha256(r.content).hexdigest(), hashlib.sha256(self.client.get('/api/v1/papers/1/pages/5/image').content).hexdigest())


if __name__ == '__main__':
    unittest.main()
