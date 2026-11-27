"""Tests of launching runs (72-extraction-interface-contract.md, OP-X04, OP-X06; ADR-025): AC-X07 to AC-X10, AC-X12,
AC-X13, AC-X16, BR-X04, BR-X05, BR-X08, BR-X10, against the local fake provider."""
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.service import workspace  # noqa: E402
from value_review.tests.test_extraction_results import LINES  # noqa: E402
from value_review.tests.test_extraction_runs import API, ExtractionBase  # noqa: E402
from value_review.tests.text_pdf import make_text_pdf  # noqa: E402


class Launch(ExtractionBase):
    def setUp(self):
        super().setUp()
        for p in ('7', '8', '9'):
            make_text_pdf(self.papers / f'{p}.pdf', LINES)
        self.c.app.state.extraction.backoff = 0
        self.fake.requests.clear()
        self.fake.failures.clear()
        self.rid = self.new_run()['id']
        r = self.c.post(f'{API}/runs/{self.rid}/prompt/versions', json={'text': 'Extract it.'}, headers={'If-Match': '"0"'})
        assert r.status_code == 201, r.text
        self.base = f'{API}/runs/{self.rid}'
        self.folder = self.root / 'results' / 'tensile' / 'sonnet-test'

    def settings(self, **extraction):
        values = {'parallel': 3, 'retries': 2, 'minutes': 10, 'warn_usd': 5, **extraction}
        assert self.c.put('/api/v1/settings', json={'extraction': values}).status_code == 200

    def launch(self, papers=None):
        return self.c.post(f'{self.base}/launch', json={} if papers is None else {'papers': papers})

    def idle(self):
        self.assertTrue(self.c.app.state.extraction.launcher.wait_idle(20))
        return self.c.get(self.base).json()

    def statuses(self):
        return {p['paper']: p['status'] for p in self.c.get(f'{self.base}/papers').json()['papers']}

    def test_first_workflow_launch_two_papers_and_open_them_in_review(self):   # AC-X07, AC-X13, BR-X10
        r = self.launch(['7', '8'])
        self.assertEqual((r.status_code, r.json()['queued']), (202, ['7', '8']))
        run = self.idle()
        self.assertEqual((run['status'], run['locked'], run['prompt_version'], run['system_prompt_version']), ('complete', True, 1, 1))
        self.assertEqual(run['counts'], {'queued': 0, 'extracting': 0, 'done': 2, 'failed': 0})
        self.assertEqual(run['actual']['usd'], 0.016)
        self.assertIsNotNone(run['finished_at'])
        self.assertEqual(self.statuses(), {'7': 'done', '8': 'done', '9': 'no_results'})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()),
                         ['7-pdf_with_feature_guide.json', '8-pdf_with_feature_guide.json', 'run.json'])
        manifest = json.loads((self.folder / 'run.json').read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('run-manifest', manifest), [])
        self.assertEqual((manifest['prompt_version'], manifest['schema_name'], sorted(manifest['papers']), manifest['finished_at']),
                         (1, 'Tensile properties', ['7', '8'], run['finished_at']))
        sid = workspace.source_id('tensile', 'sonnet-test')
        self.assertEqual([p['paper'] for p in self.c.get(f'/api/v1/sources/{sid}/papers').json()], ['7', '8'])   # in Review
        ctx = self.c.app.state.extraction
        self.assertEqual(ctx.spending.spent(self.anthropic, ctx.month()), 0.016)
        self.assertTrue(all(r['prompt'] == 'Extract it.' for r in self.fake.requests))
        # launching again extracts only the papers without results
        self.assertEqual(self.launch().json()['queued'], ['9'])
        self.assertEqual(self.idle()['counts']['done'], 3)

    def test_estimate_and_warning(self):   # BR-X10, AC-X16
        self.settings(warn_usd=0.5)
        est = self.c.get(f'{self.base}/estimate?papers=7,8').json()
        self.assertEqual((est['papers'], est['usd'], est['price_known'], est['over_warning'], est['minutes']), (2, 0.64, True, True, 2))
        self.assertEqual(self.c.get(f'{self.base}/estimate').json()['papers'], 3)
        self.c.patch(self.base, json={'model': 'openai:gpt-test-1'})
        self.c.patch(f'/api/v1/keys/{self.openai}', json={'monthly_limit_usd': 20})
        est = self.c.get(f'{self.base}/estimate?papers=7').json()
        self.assertEqual((est['usd'], est['price_known'], est['over_warning'], est['limit_unchecked']), (None, False, False, True))

    def test_pause_resume_and_cancel(self):   # AC-X08, BR-X04
        self.settings(parallel=1)
        self.fake.delay = 0.5
        self.fake.failures.extend(['slow', 'slow', 'slow'])
        self.launch(['7', '8', '9'])
        time.sleep(0.2)
        r = self.c.post(f'{self.base}/pause')
        self.assertEqual(r.status_code, 200)
        run = self.idle()
        self.assertEqual(run['status'], 'paused')
        states = self.statuses()
        self.assertEqual(sorted(states.values()), ['done', 'queued', 'queued'])   # the paper in progress finished
        self.assertEqual(self.c.post(f'{self.base}/launch', json={}).status_code, 409)
        self.assertEqual(self.c.post(f'{self.base}/resume').status_code, 202)
        time.sleep(0.2)
        self.c.post(f'{self.base}/cancel')
        run = self.idle()
        self.assertEqual(run['status'], 'cancelled')
        self.assertEqual(sorted(self.statuses().values()), ['done', 'done', 'no_results'])   # what was done is kept
        left = [p for p, s in self.statuses().items() if s == 'no_results']
        self.assertEqual(self.launch().json()['queued'], left)
        self.assertEqual(self.idle()['status'], 'complete')

    def test_a_failure_after_retries_and_retry(self):   # AC-X09, BR-X08
        self.settings(parallel=1, retries=1)
        self.fake.failures.extend([500, 500])
        self.launch(['7', '8'])
        run = self.idle()
        self.assertEqual((run['status'], run['counts']['failed'], run['counts']['done']), ('complete', 1, 1))
        rows = {p['paper']: p for p in self.c.get(f'{self.base}/papers').json()['papers']}
        self.assertEqual((rows['7']['status'], rows['7']['error']), ('failed', 'Anthropic answered with an error (500).'))
        self.assertEqual(self.c.post(f'{self.base}/papers/8/retry').status_code, 409)   # only a failed paper
        self.assertEqual(self.c.post(f'{self.base}/papers/7/retry').status_code, 202)
        self.assertEqual((self.idle()['counts']['done'], self.statuses()['7']), (3 - 1, 'done'))

    def test_a_restart_pauses_the_run(self):   # AC-X10
        self.settings(parallel=1)
        self.launch(['7'])
        self.idle()
        launcher = self.c.app.state.extraction.launcher
        state = launcher.read_state(self.rid)
        state['papers']['8'] = {'status': 'extracting'}
        state['papers']['9'] = {'status': 'queued'}
        state['sessions'].append({'started_at': '2026-11-26T10:00:00Z', 'ended_at': None})
        launcher.write_state(self.rid, state)
        store = self.c.app.state.extraction.runs
        run, _ = store.read(self.rid)
        store.write({**run, 'status': 'running'})
        c = self.app()   # the service starts again
        run = c.get(self.base).json()
        self.assertEqual((run['status'], run['counts']['queued'], run['counts']['done']), ('paused', 2, 1))
        c.app.state.extraction.backoff = 0
        self.assertEqual(c.post(f'{self.base}/resume').status_code, 202)
        self.assertTrue(c.app.state.extraction.launcher.wait_idle(20))
        self.assertEqual(c.get(self.base).json()['status'], 'complete')

    def test_reviewed_papers_are_never_extracted_again(self):   # AC-X12, BR-X05
        self.launch(['7'])
        self.idle()
        sid = workspace.source_id('tensile', 'sonnet-test')
        r = self.c.post(f'/api/v1/sources/{sid}/papers/7/versions', json={'state': empty_state()}, headers={'If-Match': '"0"'})
        self.assertEqual(r.status_code, 201, r.text)
        launcher = self.c.app.state.extraction.launcher
        launcher.set_paper(self.rid, '7', status='failed')   # even a failed paper with a Review version is protected
        rows = {p['paper']: p for p in self.c.get(f'{self.base}/papers').json()['papers']}
        self.assertEqual((rows['7']['status'], rows['7']['reviewed']), ('skipped_reviewed', True))
        self.assertEqual(self.launch(['7', '8']).json()['queued'], ['8'])
        self.idle()
        r = self.launch(['7'])
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'nothing_to_extract'))

    def test_delete_a_launched_run(self):   # AC-X14, BR-X09
        self.launch(['7', '8'])
        self.idle()
        sid = workspace.source_id('tensile', 'sonnet-test')
        r = self.c.post(f'/api/v1/sources/{sid}/papers/7/versions', json={'state': empty_state()}, headers={'If-Match': '"0"'})
        self.assertEqual(r.status_code, 201, r.text)
        r = self.c.delete(self.base)
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']), (409, 'run_reviewed', {'papers': ['7']}))
        self.assertTrue(self.folder.is_dir())
        other = self.new_run(name='Other')['id']
        self.c.post(f'{API}/runs/{other}/prompt/versions', json={'text': 'x'}, headers={'If-Match': '"0"'})
        self.c.post(f'{API}/runs/{other}/launch', json={'papers': ['9']})
        self.idle()
        folder = self.root / 'results' / 'tensile' / 'other'
        self.assertTrue(folder.is_dir())
        self.assertEqual(self.c.delete(f'{API}/runs/{other}').status_code, 204)
        self.assertFalse(folder.exists())
        self.assertFalse((self.data / 'sources' / workspace.source_id('tensile', 'other')).exists())
        self.assertEqual(self.c.get(f'{API}/runs/{other}').status_code, 404)
        self.assertEqual([r['name'] for r in self.c.get('/api/v1/workspace').json()['missing']], [])

    def test_review_shows_the_run_metadata(self):   # PEND-01, ADR-028
        self.launch(['7'])
        self.idle()
        run = next(r for s in self.c.get('/api/v1/workspace').json()['sets'] for r in s['runs'] if r['name'] == 'sonnet-test')
        self.assertEqual({k: run['meta'][k] for k in ('schema', 'model', 'run_id')},
                         {'schema': 'Tensile properties · v1', 'model': 'claude-opus-5-5', 'run_id': self.rid})
        self.assertIsNotNone(run['meta']['finished_at'])

    def test_preconditions(self):
        self.assertEqual(self.launch(['77']).status_code, 404)
        other = self.new_run(name='No prompt')['id']
        r = self.c.post(f'{API}/runs/{other}/launch', json={})
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'no_prompt'))
        self.assertEqual(self.c.post(f'{self.base}/pause').status_code, 409)
        self.assertEqual(self.c.post(f'{self.base}/resume').status_code, 409)
        self.assertEqual(self.c.post(f'{self.base}/cancel').status_code, 409)
        self.c.put('/api/v1/models', json={'enabled': ['openai:gpt-test-1']})
        r = self.launch(['7'])
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'model_unavailable'))


if __name__ == '__main__':
    unittest.main()
