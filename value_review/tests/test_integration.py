"""Integration tests of the load → review → submit workflow (12-integration-test-plan.md).

The real FastAPI app, file storage, ingest and pypdfium2 run together on temporary folders; the TestClient stands in
for the React client (step 6 of the plan, client ↔ API, is a hand check). Each case reuses the expected behavior of the
black-box cases it names (10-black-box-test-design.md) and adds only what the interaction itself must guarantee.
"""
import csv
import io
import shutil
import sys
import threading
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402

from value_review import schemas  # noqa: E402
from value_review.service import app as app_module  # noqa: E402
from value_review.service.app import create_app  # noqa: E402
from value_review.storage import StorageError  # noqa: E402
from value_review.storage.files import AnnotationStore  # noqa: E402
from value_review.tests.test_ingest import make_pdf, sha  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402
from value_review.tests.test_versions import three_decisions  # noqa: E402

API = '/api/v1'
SETTINGS = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5}


def tree(folder):
    """{relative path: sha256} of every file under ``folder``."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()} if folder.is_dir() else {}


class Workflow(Base):
    """Two folder pairs: the default one (paper 7, from Base) and pair B with paper 7 (complete),
    11 (LLM result without its PDF) and 12 (PDF without an LLM result)."""

    def setUp(self):
        super().setUp()
        ticks = iter(range(10 ** 6))
        self.client.close()
        self.client = TestClient(create_app(self.config, web_dir=None, clock=lambda: f'2026-11-18T09:{next(ticks) % 60:02d}:00Z'),
                                 base_url='http://127.0.0.1')
        d = Path(self.tmp.name)
        self.run_b, self.pdfs_b = d / 'run B', d / 'pdfs B'
        self.run_b.mkdir(); self.pdfs_b.mkdir()
        shutil.copy(self.res, self.run_b / self.res.name)
        shutil.copy(self.pdf, self.pdfs_b / '7.pdf')
        shutil.copy(self.res, self.run_b / '11-pdf_with_feature_guide.json')
        make_pdf(self.pdfs_b / '12.pdf', [(612, 792)])
        self.default_pair = {'id': 'default', 'name': 'run', 'run_dir': str(self.run), 'pdf_dir': str(self.pdfs)}

    def add_pair_b(self):
        r = self.client.put(f'{API}/settings', json={**SETTINGS, 'sources': [
            self.default_pair, {'name': 'Model B', 'run_dir': f'"{self.run_b}"', 'pdf_dir': f'  {self.pdfs_b}  '}]})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def sources_snapshot(self):
        return tree(self.run), tree(self.pdfs), tree(self.run_b), tree(self.pdfs_b)

    def run_workflow(self):
        """IT-01 steps, asserting each one; returns what later cases build on."""
        sources_before = self.sources_snapshot()
        default_before = (tree(self.data / 'originals'), tree(self.data / 'annotations' / 'versions'))

        # 1 · Settings (BB-01): the pair is saved cleaned, with an id made from its name.
        settings = self.add_pair_b()
        pair = settings['sources'][1]
        self.assertEqual(pair, {'id': 'model-b', 'name': 'Model B', 'run_dir': str(self.run_b), 'pdf_dir': str(self.pdfs_b)})
        b = f'{API}/sources/model-b'

        # 2 · Load (BB-04): only complete papers are loaded; the others are named by what they miss.
        load = self.client.post(f'{b}/ingest').json()
        self.assertEqual((load['source'], load['written'], load['unchanged'], load['changed'], load['failed']), ('model-b', 1, 0, 0, 0))
        self.assertEqual((load['results_without_pdf'], load['pdfs_without_results']), (['11'], ['12']))
        self.assertTrue((self.data / 'sources' / 'model-b' / 'originals' / '7.json').is_file())

        # 3 · Switch the active pair: the unprefixed API now serves pair B.
        self.assertEqual(self.client.put(f'{API}/active-source', json={'source': 'model-b'}).json()['active_source'], 'model-b')
        rows = self.client.get(f'{API}/papers').json()   # BB-06
        self.assertEqual([(r['paper'], r['version'], r['status'], r['source_problems']) for r in rows], [('7', 0, 'not_started', [])])

        # 4 · Open (BB-07): ETag names version 0; the page renders from pair B's PDF into pair B's cache.
        opened = self.client.get(f'{b}/papers/7')
        self.assertEqual((opened.status_code, opened.headers['etag']), (200, '"0"'))
        self.assertEqual(opened.json()['original']['observations'][0]['evidence'][0]['bbox'], [0.5262, 0.3837, 0.5763, 0.3932])
        self.assertEqual(self.client.get(f'{b}/papers/7/pages/1/image').status_code, 200)
        self.assertTrue(any((self.data / 'sources' / 'model-b' / 'cache' / 'pages' / '7').glob('*.png')))

        # 5 · Draft, then submit (BB-08): v1 in pair B, draft gone.
        state = three_decisions()
        r = self.client.put(f'{b}/papers/7/draft', json={'base_version': 0, 'trigger': 'manual', 'state': state})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client.post(f'{b}/papers/7/versions', json={'state': state}, headers={'If-Match': '"0"'})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()['n'], r.headers['location']), (1, f'{b}/papers/7/versions/1'))
        store_b = AnnotationStore(self.data / 'sources' / 'model-b' / 'annotations')
        v1 = store_b.read_version('7', 1)[0]
        self.assertIsNotNone(v1)
        self.assertEqual(schemas.errors('version', v1), [])
        self.assertFalse(store_b.draft_path('7').exists())
        rows = self.client.get(f'{API}/papers').json()
        self.assertEqual((rows[0]['version'], rows[0]['latest']['n'], rows[0]['reviewed']), (1, 1, 3))

        # 6 · Export (BB-12): the CSV carries the three decisions with the model's value alongside.
        r = self.client.get(f'{b}/papers/7/versions/1/export.csv')
        self.assertEqual(r.status_code, 200)
        csv_rows = {row['observation_id']: row for row in csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')))}
        self.assertEqual({k: csv_rows[k]['status'] for k in ('o1', 'o2', 'o3', 'o4')},
                         {'o1': 'corrected', 'o2': 'rejected', 'o3': 'accepted', 'o4': 'pending'})
        self.assertEqual((csv_rows['o1']['value'], csv_rows['o1']['original_value']), ('710 ± 26', '710 ± 25'))
        export_json = self.client.get(f'{b}/papers/7/versions/1/export.json').json()
        self.assertEqual(schemas.errors('export', export_json), [])

        # Interaction guarantees: the other pair and every source file are untouched (BR-01, per-pair data).
        self.assertEqual((tree(self.data / 'originals'), tree(self.data / 'annotations' / 'versions')), default_before)
        self.assertEqual(self.client.get(f'{API}/sources/default/papers/7/versions').json(), [])
        self.assertEqual(self.sources_snapshot(), sources_before)
        return {'b': b, 'store_b': store_b, 'csv_v1': r.content}


class HappyPath(Workflow):
    def test_it01_load_review_submit_export_on_a_second_pair(self):  # IT-01
        self.run_workflow()


class PartialFailure(Workflow):
    def test_it05_failed_version_write_keeps_the_draft_reopenable(self):  # IT-05 (WB-12)
        self.add_pair_b()
        b = f'{API}/sources/model-b'
        self.client.post(f'{b}/ingest')
        state = three_decisions()
        r = self.client.put(f'{b}/papers/7/draft', json={'base_version': 0, 'trigger': 'manual', 'state': state, 'ui': {'mode': 'record', 'observation_id': 'o1'}})
        self.assertEqual(r.status_code, 200, r.text)
        store_b = AnnotationStore(self.data / 'sources' / 'model-b' / 'annotations')
        with mock.patch.object(AnnotationStore, 'write_version', side_effect=StorageError('disk full')):
            r = self.client.post(f'{b}/papers/7/versions', json={'state': state}, headers={'If-Match': '"0"'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertEqual(store_b.version_numbers('7'), [])
        opened = self.client.get(f'{b}/papers/7')
        body = opened.json()
        self.assertEqual((opened.headers['etag'], body['draft_stale'], body['draft']['state'], body['draft']['ui']),
                         ('"0"', False, state, {'mode': 'record', 'observation_id': 'o1'}))   # Continue offered, view kept
        self.assertEqual(self.client.get(f'{b}/papers').json()[0]['status'], 'in_progress')   # progress from the draft
        r = self.client.post(f'{b}/papers/7/versions', json={'state': body['draft']['state']}, headers={'If-Match': '"0"'})
        self.assertEqual((r.status_code, store_b.version_numbers('7')), (201, [1]))   # retry succeeds as v1


class ConcurrentLoad(Workflow):  # IT-06, WB-02
    def setUp(self):
        super().setUp()
        self.add_pair_b()
        self.url = f'{API}/sources/model-b/ingest'
        self.real_ingest = app_module.ingest_run

    def test_it06_second_load_while_one_runs(self):
        started, release = threading.Event(), threading.Event()

        def slow_ingest(*args, **kwargs):
            started.set()
            self.assertTrue(release.wait(10), 'first load never released')
            return self.real_ingest(*args, **kwargs)

        first = {}
        with mock.patch.object(app_module, 'ingest_run', slow_ingest):
            other = TestClient(self.client.app, base_url='http://127.0.0.1')   # a second tab
            worker = threading.Thread(target=lambda: first.update(r=other.post(self.url)))
            worker.start()
            self.assertTrue(started.wait(10), 'first load never started')
            second = self.client.post(self.url)
            release.set()
            worker.join(10)
            other.close()
        self.assertEqual((second.status_code, second.json()['error']['code']), (409, 'ingest_running'))
        self.assertEqual((first['r'].status_code, first['r'].json()['written']), (200, 1))
        originals = self.data / 'sources' / 'model-b' / 'originals'
        self.assertEqual(sorted(p.name for p in originals.iterdir()), ['7.json'])   # no temporaries, no partial files
        again = self.client.post(self.url).json()   # WB-02: the lock is free afterwards
        self.assertEqual((again['written'], again['unchanged']), (0, 1))

    def test_wb02_lock_released_when_a_load_crashes(self):
        with mock.patch.object(app_module, 'ingest_run', side_effect=RuntimeError('pdfium crashed')),                 self.assertLogs('value_review', 'ERROR') as logs, self.assertRaises(RuntimeError):
            self.client.post(self.url)
        self.assertIn('internal error', logs.output[0])
        r = self.client.post(self.url)
        self.assertEqual((r.status_code, r.json()['written']), (200, 1))


class FailuresAndTransitions(Workflow):
    def test_it02_stale_submit_changes_nothing(self):  # IT-02 (BB-10)
        w = self.run_workflow()
        r = self.client.post(f"{w['b']}/papers/7/versions", json={'state': three_decisions()}, headers={'If-Match': '"0"'})
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']['current']), (409, 'version_conflict', 1))
        self.assertEqual(r.headers['etag'], '"1"')
        self.assertEqual(w['store_b'].version_numbers('7'), [1])
        self.assertEqual(self.client.get(f"{w['b']}/papers/7/versions/1/export.csv").content, w['csv_v1'])

    def test_it03_missing_pdf_makes_the_paper_read_only_and_keeps_its_versions(self):  # IT-03 (BB-13)
        w = self.run_workflow()
        (self.pdfs_b / '7.pdf').unlink()
        row = self.client.get(f"{w['b']}/papers").json()[0]
        self.assertEqual((row['source_changed'], row['source_problems']), (True, ['pdf_missing']))
        r = self.client.get(f"{w['b']}/papers/7/pages/1/image")   # page 1 is cached, still refused
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        r = self.client.post(f"{w['b']}/papers/7/versions", json={'state': three_decisions()}, headers={'If-Match': '"1"'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        r = self.client.put(f"{w['b']}/papers/7/draft", json={'base_version': 1, 'trigger': 'manual', 'state': three_decisions()})
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        self.assertEqual(w['store_b'].version_numbers('7'), [1])
        self.assertEqual(self.client.get(f"{w['b']}/papers/7/versions/1/export.csv").content, w['csv_v1'])
        self.assertEqual(self.client.get(f'{API}/sources/default/papers').json()[0]['source_problems'], [])   # other pair unaffected

    def test_it04_changed_model_output_is_kept_out_and_read_only(self):  # IT-04 (BB-05)
        w = self.run_workflow()
        original = self.data / 'sources' / 'model-b' / 'originals' / '7.json'
        before = original.read_bytes()
        result = self.run_b / self.res.name
        result.write_text(result.read_text(encoding='utf-8').replace('710 ± 25', '715 ± 25'), encoding='utf-8')
        load = self.client.post(f"{w['b']}/ingest").json()
        self.assertEqual({p['paper']: p['outcome'] for p in load['papers']}, {'7': 'changed'})
        self.assertEqual((load['written'], load['changed']), (0, 1))
        self.assertEqual(original.read_bytes(), before)   # BR-01: never rewritten
        row = self.client.get(f"{w['b']}/papers").json()[0]
        self.assertEqual(row['source_problems'], ['result_changed'])
        self.assertEqual(self.client.get(f"{w['b']}/papers/7").json()['original']['observations'][0]['value'], '710 ± 25')
        r = self.client.post(f"{w['b']}/papers/7/versions/1/restore", headers={'If-Match': '"1"'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'source_changed'))
        self.assertEqual(w['store_b'].version_numbers('7'), [1])


if __name__ == '__main__':
    unittest.main()
