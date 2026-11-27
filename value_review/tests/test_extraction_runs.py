"""Tests of the extraction runs and their Setup (72-extraction-interface-contract.md, OP-X01, OP-X02): AC-X01, AC-X02,
AC-X11 (draft part) and BR-X06, BR-X07, on a temporary workspace with a local fake provider."""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.service.app import create_app  # noqa: E402
from value_review.service.config import Config  # noqa: E402
from value_review.tests.fake_provider import FakeProvider  # noqa: E402
from value_review.tests.test_ingest import make_pdf  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

API = '/api/v1/extraction'
ANTHROPIC, OPENAI = 'test-key-anthropic-0001', 'test-key-openai-0002'
SONNET = 'anthropic:claude-opus-5-5'


class ExtractionBase(Base):
    """A workspace with the set "tensile" (PDFs 7, 8, 9), an Anthropic and an OpenAI key, two enabled models and the
    seeded schema "Tensile properties" v1. ``self.c`` is a client of a service on that workspace."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fake = FakeProvider(delay=2.0)

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, self.fake.env())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = Path(self.tmp.name) / 'ws'
        self.papers = self.root / 'papers' / 'tensile'
        self.papers.mkdir(parents=True)
        (self.root / 'results').mkdir()
        shutil.copy(self.pdf, self.papers / '7.pdf')
        for p in ('8', '9'):
            make_pdf(self.papers / f'{p}.pdf', [(612, 792)])
        self.c = self.app()
        self.anthropic = self.c.post('/api/v1/keys', json={'provider': 'anthropic', 'key': ANTHROPIC, 'name': 'Lab'}).json()['id']
        self.openai = self.c.post('/api/v1/keys', json={'provider': 'openai', 'key': OPENAI}).json()['id']
        r = self.c.put('/api/v1/models', json={'enabled': [SONNET, 'openai:gpt-test-1'], 'default': SONNET})
        assert r.status_code == 200, r.text
        assert self.c.get('/api/v1/schemas').status_code == 200   # seeds "Tensile properties" v1

    def app(self, workspace='default'):
        root = self.root if workspace == 'default' else workspace
        return TestClient(create_app(Config(data=self.data, run_dir=self.run, pdf_dir=self.pdfs, workspace=root), web_dir=None),
                          base_url='http://127.0.0.1')

    def new_run(self, **extra):
        body = {'name': 'Sonnet test', 'set': 'tensile', 'schema_id': 'tensile-properties', 'schema_version': 1, 'model': SONNET, **extra}
        r = self.c.post(f'{API}/runs', json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def codes(self, run):
        return [b['code'] for b in run['blocked']]


class Runs(ExtractionBase):
    def test_sets(self):   # OP-X02
        body = self.c.get(f'{API}/sets').json()
        self.assertEqual((body['configured'], body['found']), (True, True))
        self.assertEqual([(s['name'], s['pdfs'], s['runs'], s['tool_runs']) for s in body['sets']], [('tensile', 3, [], [])])

    def test_a_draft_is_created_with_the_default_key(self):   # AC-X01
        run = self.new_run()
        self.assertEqual((run['status'], run['key_id'], run['folder'], run['results_folder'], run['schema_name'], run['locked']),
                         ('draft', self.anthropic, 'sonnet-test', 'results/tensile/sonnet-test/', 'Tensile properties', False))
        self.assertEqual(run['blocked'], [])
        self.assertEqual(run['created_by'], 'Expert reviewer')
        stored = json.loads((self.data / 'extraction' / 'runs' / run['id'] / 'run.json').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('run', stored), [])
        self.assertEqual([r['id'] for r in self.c.get(f'{API}/runs').json()['runs']], [run['id']])
        self.assertEqual(self.c.get(f'{API}/sets').json()['sets'][0]['tool_runs'], [run['id']])
        self.assertFalse((self.root / 'results' / 'tensile').exists())   # nothing written in the workspace yet

    def test_folders_are_unique_in_a_set(self):
        (self.root / 'results' / 'tensile' / 'sonnet-test').mkdir(parents=True)   # a folder made by hand
        first = self.new_run()
        second = self.new_run()
        self.assertEqual((first['folder'], second['folder']), ('sonnet-test-2', 'sonnet-test-3'))

    def test_what_blocks_a_run(self):   # AC-X02, BR-X07
        run = self.new_run(model=None)
        self.assertEqual(self.codes(run), ['no_model', 'no_key'])
        self.assertTrue(all(b['message'] for b in run['blocked']))
        rid = run['id']
        r = self.c.patch(f'{API}/runs/{rid}', json={'model': 'google:gemini-test-pro'})
        self.assertEqual(self.codes(r.json()), ['model_unavailable', 'no_key'])
        r = self.c.patch(f'{API}/runs/{rid}', json={'model': 'openai:gpt-test-1'})
        self.assertEqual((self.codes(r.json()), r.json()['key_id']), ([], self.openai))   # the provider's default key
        r = self.c.patch(f'{API}/runs/{rid}', json={'key_id': self.anthropic})
        self.assertEqual(self.codes(r.json()), ['key_wrong_provider'])
        self.c.patch(f'/api/v1/keys/{self.anthropic}', json={'monthly_limit_usd': 5})
        self.c.app.state.extraction.spending.add(self.anthropic, self.c.app.state.extraction.month(), 5.0)
        r = self.c.patch(f'{API}/runs/{rid}', json={'model': SONNET, 'key_id': self.anthropic})
        self.assertEqual(self.codes(r.json()), ['key_at_limit'])
        self.c.put('/api/v1/models', json={'enabled': ['openai:gpt-test-1']})
        self.assertEqual(self.codes(self.c.get(f'{API}/runs/{rid}').json()), ['model_unavailable', 'key_at_limit'])

    def test_a_missing_workspace_set_or_key(self):   # AC-X02
        rid = self.new_run()['id']
        self.c.delete(f'/api/v1/keys/{self.anthropic}')
        self.assertIn('key_not_found', self.codes(self.c.get(f'{API}/runs/{rid}').json()))
        shutil.rmtree(self.papers)
        self.assertIn('set_not_found', self.codes(self.c.get(f'{API}/runs/{rid}').json()))
        c = self.app(workspace=None)
        self.assertIn('no_workspace', self.codes(c.get(f'{API}/runs/{rid}').json()))
        self.assertEqual(c.get(f'{API}/sets').json()['configured'], False)

    def test_invalid_input(self):
        for body, status in (({'name': ' ', 'set': 'tensile', 'schema_id': 'tensile-properties', 'schema_version': 1}, 400),
                             ({'name': 'x', 'set': '..', 'schema_id': 'tensile-properties', 'schema_version': 1}, 400),
                             ({'name': 'x', 'set': 'tensile', 'schema_id': 'tensile-properties', 'schema_version': 9}, 422),
                             ({'name': 'x', 'set': 'tensile', 'schema_id': 'nope', 'schema_version': 1}, 422),
                             ({'name': 'x', 'set': 'tensile', 'schema_id': 'tensile-properties', 'schema_version': 1, 'key_id': 'k_00000000'}, 422),
                             ({'name': 'x', 'set': 'tensile', 'schema_id': 'tensile-properties', 'schema_version': 1, 'extra': 1}, 400)):
            r = self.c.post(f'{API}/runs', json=body)
            self.assertEqual(r.status_code, status, (body, r.text))
        self.assertEqual(self.c.get(f'{API}/runs').json()['runs'], [])
        for path in (f'{API}/runs/r_00000000', f'{API}/runs/nope', f'{API}/runs/..'):
            self.assertEqual(self.c.get(path).status_code, 404, path)

    def test_edit_copy_and_delete_a_draft(self):   # BR-X06 (draft part)
        run = self.new_run()
        rid = run['id']
        r = self.c.patch(f'{API}/runs/{rid}', json={'name': 'Renamed', 'schema_version': 1})
        self.assertEqual((r.json()['name'], r.json()['folder']), ('Renamed', 'sonnet-test'))   # the folder stays
        copy = self.c.post(f'{API}/runs/{rid}/copy').json()
        self.assertEqual((copy['name'], copy['copied_from'], copy['status'], copy['model'], copy['folder']),
                         ('Copy of Renamed', rid, 'draft', SONNET, 'copy-of-renamed'))
        self.assertEqual(self.c.delete(f'{API}/runs/{rid}').status_code, 204)
        self.assertEqual([r['id'] for r in self.c.get(f'{API}/runs').json()['runs']], [copy['id']])

    def test_a_launched_run_is_read_only(self):   # AC-X11
        run = self.new_run()
        store = self.c.app.state.extraction.runs
        stored, _ = store.read(run['id'])
        store.write({**stored, 'status': 'complete', 'launched_at': '2026-11-26T10:00:00Z', 'prompt_version': 1})
        for body in ({'model': 'openai:gpt-test-1'}, {'schema_version': 1}, {'set': 'other'}, {'key_id': self.openai}):
            r = self.c.patch(f'{API}/runs/{run["id"]}', json=body)
            self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'run_locked'), body)
        r = self.c.patch(f'{API}/runs/{run["id"]}', json={'name': 'Final'})
        self.assertEqual((r.status_code, r.json()['name'], r.json()['locked']), (200, 'Final', True))
        self.assertEqual(self.c.post(f'{API}/runs/{run["id"]}/copy').json()['status'], 'draft')

    def test_a_damaged_run_file_is_reported(self):
        rid = self.new_run()['id']
        (self.data / 'extraction' / 'runs' / rid / 'run.json').write_text('{ not json', encoding='utf-8')
        body = self.c.get(f'{API}/runs').json()
        self.assertEqual((body['runs'], body['problems']), ([], [f'{rid}/run.json: JSONDecodeError']))
        self.assertEqual(self.c.get(f'{API}/runs/{rid}').status_code, 500)


if __name__ == '__main__':
    unittest.main()
