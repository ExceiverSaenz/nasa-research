"""Tests of the workspace (62-workspace-interface-contract.md): AC-W01 to AC-W08 and BR-W01 to BR-W07, on temporary
folders with synthetic papers."""
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import config as vr_config  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.service import workspace  # noqa: E402
from value_review.service.app import create_app  # noqa: E402
from value_review.service.config import Config  # noqa: E402
from value_review.tests.test_ingest import make_pdf, sha  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

API = '/api/v1/workspace'


class Workspace(Base):
    def setUp(self):
        super().setUp()
        self.root = Path(self.tmp.name) / 'ws'
        self.papers = self.root / 'papers' / 'tensile'
        self.runs = self.root / 'results' / 'tensile'

    def make(self, *run_names, pdfs=('7', '8', '9')):
        """A paper set with ``pdfs`` and runs whose results cover paper 7 (copied from the Base paper)."""
        self.papers.mkdir(parents=True, exist_ok=True)
        for p in pdfs:
            if p == '7':
                shutil.copy(self.pdf, self.papers / '7.pdf')
            else:
                make_pdf(self.papers / f'{p}.pdf', [(612, 792)])
        for name in run_names:
            (self.runs / name).mkdir(parents=True)
            shutil.copy(self.res, self.runs / name / self.res.name)

    def app(self, root=None, **extra):
        return TestClient(create_app(Config(data=self.data, run_dir=self.run, pdf_dir=self.pdfs,
                                            workspace=self.root if root is None else root, **extra), web_dir=None), base_url='http://127.0.0.1')

    def scan(self, client):
        r = client.post(f'{API}/scan')
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_not_configured(self):   # AC-W01
        body = self.client.get(API).json()
        self.assertEqual((body['configured'], body['root'], body['sets'], body['missing']), (False, None, [], []))
        self.assertEqual(self.client.post(f'{API}/scan').json()['totals'], None)
        self.assertEqual(self.client.get('/api/v1/settings').json()['sources'][0]['id'], 'default')

    def test_runs_are_found_and_loaded(self):   # AC-W02, AC-W03
        self.make('gpt low', 'gpt-high')
        c = self.app()
        before = c.get(API).json()
        self.assertEqual([(r['name'], r['loaded']) for r in before['sets'][0]['runs']], [('gpt low', 0), ('gpt-high', 0)])
        body = self.scan(c)
        self.assertEqual(body['totals'], {'written': 2, 'unchanged': 0, 'changed': 0, 'failed': 0})
        item = body['sets'][0]
        self.assertEqual((item['name'], item['pdfs'], len(item['runs'])), ('tensile', 3, 2))
        run = item['runs'][0]
        self.assertEqual((run['results'], run['loaded'], run['pdfs_without_results'], run['results_without_pdf'], run['problem']),
                         (1, 1, ['8', '9'], [], None))
        self.assertEqual(self.scan(c)['totals'], {'written': 0, 'unchanged': 2, 'changed': 0, 'failed': 0})
        self.assertEqual(c.get('/api/v1/settings').json()['sources'], c.get('/api/v1/settings').json()['sources'])
        self.assertEqual([s['id'] for s in c.get('/api/v1/settings').json()['sources']], ['default'])   # never a stored pair

    def test_ids_are_stable_and_distinct(self):   # BR-W03
        self.assertEqual(workspace.source_id('tensile', 'gpt low'), workspace.source_id('tensile', 'gpt low'))
        self.assertNotEqual(workspace.source_id('tensile', 'gpt low'), workspace.source_id('tensile', 'gpt-low'))
        long = workspace.source_id('A very long paper set name ' * 3, 'A very long run name ' * 3)
        self.assertLessEqual(len(long), 40)
        self.assertTrue(workspace.pairs.SOURCE_ID.fullmatch(long))
        self.make('gpt-low')
        c = self.app()
        sid = self.scan(c)['sets'][0]['runs'][0]['source_id']
        moved = Path(self.tmp.name) / 'moved'
        shutil.move(str(self.root), str(moved))
        c = self.app(root=moved)
        self.assertEqual(self.scan(c)['sets'][0]['runs'][0]['source_id'], sid)
        self.assertEqual(c.get(f'/api/v1/sources/{sid}/papers').status_code, 200)

    def test_a_new_run_appears_without_setup(self):   # AC-W04
        self.make('one')
        c = self.app()
        self.scan(c)
        (self.runs / 'two').mkdir()
        shutil.copy(self.res, self.runs / 'two' / self.res.name)
        body = self.scan(c)
        self.assertEqual(body['totals']['written'], 1)
        self.assertEqual([r['name'] for r in body['sets'][0]['runs']], ['one', 'two'])

    def test_review_and_submit_on_a_run(self):   # AC-W05, BR-W05, BR-W06
        self.make('gpt-low')
        before = {p: sha(p) for p in self.root.rglob('*') if p.is_file()}
        c = self.app()
        sid = self.scan(c)['sets'][0]['runs'][0]['source_id']
        base = f'/api/v1/sources/{sid}/papers'
        self.assertEqual([p['paper'] for p in c.get(base).json()], ['7'])
        self.assertEqual(c.get(f'{base}/7/pages/1/image').status_code, 200)
        state = empty_state()
        state['decisions'] = {'o1': {'verdict': 'accepted', 'note': '', 'by': 'R', 'at': '2026-11-19T10:00:00Z'}}
        r = c.put(f'{base}/7/draft', json={'base_version': 0, 'trigger': 'manual', 'state': state})
        self.assertEqual(r.status_code, 200, r.text)
        r = c.post(f'{base}/7/versions', json={'state': state}, headers={'If-Match': '"0"'})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(c.get(f'{base}/7/versions/1/export.csv').status_code, 200)
        self.assertTrue((self.data / 'sources' / sid / 'annotations' / 'versions' / '7' / 'v1.json').is_file())
        self.assertEqual({p: sha(p) for p in self.root.rglob('*') if p.is_file()}, before)   # nothing written inside
        self.assertEqual(c.put('/api/v1/active-source', json={'source': sid}).status_code, 404)   # pairs only

    def test_problems_are_listed_and_nothing_is_loaded_for_them(self):   # AC-W06
        self.make('good')
        (self.runs / 'empty').mkdir()
        (self.root / 'results' / 'orphan' / 'run').mkdir(parents=True)
        shutil.copy(self.res, self.root / 'results' / 'orphan' / 'run' / self.res.name)
        (self.root / 'results' / '.hidden' / 'run').mkdir(parents=True)
        (self.root / 'papers' / 'unused').mkdir()
        c = self.app()
        body = self.scan(c)
        sets = {s['name']: s for s in body['sets']}
        self.assertEqual(sorted(sets), ['orphan', 'tensile', 'unused'])
        runs = {r['name']: r for r in sets['tensile']['runs']}
        self.assertIn('No result files', runs['empty']['problem'])
        self.assertIsNone(runs['empty']['source_id'])
        self.assertIn('papers\\orphan\\', sets['orphan']['runs'][0]['problem'])
        self.assertEqual(body['totals']['written'], 1)
        self.assertEqual(len(list((self.data / 'sources').iterdir())), 1)

    def test_a_missing_root_or_folder(self):
        c = self.app(root=Path(self.tmp.name) / 'nowhere')
        body = self.scan(c)
        self.assertEqual((body['configured'], body['found'], body['problems']), (True, False, ['This folder does not exist.']))
        self.root.mkdir()
        body = self.scan(self.app())
        self.assertEqual(body['problems'], ['No papers\\ folder inside it.', 'No results\\ folder inside it.'])

    def test_a_removed_run_keeps_its_reviews(self):   # AC-W07
        self.make('gpt-low')
        c = self.app()
        sid = self.scan(c)['sets'][0]['runs'][0]['source_id']
        base = f'/api/v1/sources/{sid}/papers'
        self.assertEqual(c.post(f'{base}/7/versions', json={'state': empty_state()}, headers={'If-Match': '"0"'}).status_code, 201)
        shutil.rmtree(self.runs / 'gpt-low')
        body = self.scan(c)
        self.assertEqual(body['missing'], [{'source_id': sid, 'set': 'tensile', 'run': 'gpt-low'}])
        self.assertEqual([v['n'] for v in c.get(f'{base}/7/versions').json()], [1])
        self.assertTrue(c.get(base).json()[0]['source_changed'])   # read only

    def test_a_folder_pair_on_a_run_keeps_it(self):   # AC-W08, BR-W04
        self.make('gpt-low')
        c = self.app()
        r = c.put('/api/v1/settings', json={'sources': [
            {'id': 'default', 'name': 'run', 'run_dir': str(self.run), 'pdf_dir': str(self.pdfs)},
            {'name': 'Mine', 'run_dir': str(self.runs / 'gpt-low'), 'pdf_dir': str(self.papers)}]})
        self.assertEqual(r.status_code, 200, r.text)
        pair = r.json()['sources'][1]['id']
        body = self.scan(c)
        run = body['sets'][0]['runs'][0]
        self.assertEqual((run['source_id'], run['pair'], run['loaded'], body['missing']), (pair, True, 1, []))
        self.assertTrue((self.data / 'sources' / pair / 'originals' / '7.json').is_file())
        self.assertFalse(list((self.data / 'sources').glob('ws-*')))

    def test_the_default_pair_is_hidden_only_when_empty_and_missing(self):   # BR-W07
        self.make('gpt-low')
        gone = Path(self.tmp.name) / 'gone'
        c = TestClient(create_app(Config(data=Path(self.tmp.name) / 'fresh', run_dir=gone, pdf_dir=gone, workspace=self.root),
                                  web_dir=None), base_url='http://127.0.0.1')
        self.assertEqual(self.scan(c)['hidden_pairs'], ['default'])
        self.assertEqual(self.scan(self.app())['hidden_pairs'], [])   # its folders exist and it has data

    def test_one_load_at_a_time_and_failures_are_reported(self):
        self.make('gpt-low')
        c = self.app()
        with mock.patch('value_review.service.workspace.ingest_run', side_effect=OSError(13, 'Access is denied')):
            body = self.scan(c)
        self.assertEqual(body['sets'][0]['runs'][0]['problem'], 'Could not load: Access is denied.')
        (self.runs / 'gpt-low' / self.res.name).write_text('{ not json', encoding='utf-8')
        body = self.scan(c)
        self.assertEqual((body['totals']['failed'], body['sets'][0]['runs'][0]['failed'][0]['paper']), (1, '7'))

    def test_the_root_comes_from_the_environment(self):   # BR-W01
        with mock.patch.dict('os.environ', {'VALUE_REVIEW_WORKSPACE': f' {self.root} ', 'VALUE_REVIEW_WORKSPACE_SHOWN': 'C:\\mine'}):
            config = Config(data=self.data)
        self.assertEqual((config.workspace, config.workspace_shown), (self.root, 'C:\\mine'))
        with mock.patch.dict('os.environ', {'VALUE_REVIEW_WORKSPACE': ''}):
            self.assertIsNone(vr_config.default_workspace())

    def test_a_tampered_record_is_ignored(self):
        self.make('gpt-low')
        c = self.app()
        sid = self.scan(c)['sets'][0]['runs'][0]['source_id']
        record = self.data / 'sources' / sid / 'source.json'
        record.write_text(json.dumps({'set': '..', 'run': '..'}), encoding='utf-8')
        self.assertEqual(c.get(f'/api/v1/sources/{sid}/papers').status_code, 404)


if __name__ == '__main__':
    unittest.main()
