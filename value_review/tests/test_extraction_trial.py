"""Tests of testing a run's prompt (72-extraction-interface-contract.md, OP-X05): AC-X05, AC-X06, BR-X03, against the
local fake provider."""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.tests.test_extraction_results import LINES  # noqa: E402
from value_review.tests.test_extraction_runs import API, ExtractionBase  # noqa: E402
from value_review.tests.text_pdf import make_text_pdf  # noqa: E402


def wait(client, tid, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        body = client.get(f'{API}/tests/{tid}').json()
        if body['status'] == 'done':
            return body
        time.sleep(0.05)
    raise AssertionError('the test did not finish')


class Trial(ExtractionBase):
    def setUp(self):
        super().setUp()
        for p in ('7', '8'):
            make_text_pdf(self.papers / f'{p}.pdf', LINES)
        self.c.app.state.extraction.backoff = 0
        self.fake.requests.clear()
        self.fake.failures.clear()
        self.rid = self.new_run()['id']
        r = self.c.post(f'{API}/runs/{self.rid}/prompt/versions', json={'text': 'Extract it.'}, headers={'If-Match': '"0"'})
        assert r.status_code == 201, r.text

    def start(self, papers):
        return self.c.post(f'{API}/runs/{self.rid}/tests', json={'papers': papers})

    def test_values_with_their_page_and_nothing_saved(self):   # AC-X05, BR-X03
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        r = self.start(['7', '8'])
        self.assertEqual((r.status_code, r.json()['status']), (202, 'running'))
        body = wait(self.c, r.json()['id'])
        self.assertEqual([p['status'] for p in body['papers']], ['done', 'done'])
        first = body['papers'][0]['values'][0]
        self.assertEqual({k: first[k] for k in ('field_id', 'field', 'records', 'value', 'unit', 'page', 'found')},
                         {'field_id': 'yield_strength', 'field': 'Yield strength', 'records': ['SS-J'], 'value': '710 ± 25',
                          'unit': 'MPa', 'page': 1, 'found': True})
        self.assertEqual(body['usd'], 0.016)   # two papers, $0.008 each with the fake's usage
        self.assertEqual([r['prompt'] for r in self.fake.requests], ['Extract it.', 'Extract it.'])
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)   # nothing in the workspace
        self.assertFalse((self.data / 'sources').exists())   # nothing loaded into Review
        ctx = self.c.app.state.extraction
        self.assertEqual(ctx.spending.spent(self.anthropic, ctx.month()), 0.016)   # the test still costs money
        self.assertEqual(self.c.get(f'{API}/runs/{self.rid}').json()['status'], 'draft')

    def test_limits_and_preconditions(self):   # AC-X06
        self.assertEqual(self.start(['7', '8', '9', '7b']).status_code, 400)
        self.assertEqual(self.c.post(f'{API}/runs/{self.rid}/tests', json={'papers': []}).status_code, 400)
        r = self.start(['99'])
        self.assertEqual((r.status_code, r.json()['error']['code']), (404, 'paper_not_found'))
        other = self.new_run(name='Without prompt')['id']
        r = self.c.post(f'{API}/runs/{other}/tests', json={'papers': ['7']})
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'no_prompt'))
        self.c.patch(f'/api/v1/keys/{self.anthropic}', json={'monthly_limit_usd': 1})
        ctx = self.c.app.state.extraction
        ctx.spending.add(self.anthropic, ctx.month(), 1.0)
        r = self.start(['7'])
        self.assertEqual((r.status_code, r.json()['error']['code']), (409, 'key_at_limit'))   # BR-X07
        self.assertEqual(self.c.get(f'{API}/tests/t_00000000').status_code, 404)

    def test_failures_are_per_paper_after_the_retries(self):
        self.fake.failures.extend([500, 500, 500])   # retries 2: three attempts for paper 7
        body = wait(self.c, self.start(['7', '8']).json()['id'])
        self.assertEqual([(p['status'], p['error']) for p in body['papers']],
                         [('failed', 'Anthropic answered with an error (500).'), ('done', None)])
        self.assertEqual(len(self.fake.requests), 4)
        self.fake.requests.clear()
        self.c.put('/api/v1/settings', json={'extraction': {'parallel': 3, 'retries': 0, 'minutes': 10, 'warn_usd': 5}})
        self.fake.failures.extend([401])
        body = wait(self.c, self.start(['7']).json()['id'])
        self.assertEqual((body['papers'][0]['status'], body['papers'][0]['error'], len(self.fake.requests)),
                         ('failed', 'The provider did not accept this key.', 1))   # not tried again
        self.c.patch(f'{API}/runs/{self.rid}', json={'key_id': self.openai, 'model': 'openai:gpt-test-1'})
        self.fake.failures.clear()
        body = wait(self.c, self.start(['7']).json()['id'])
        self.assertEqual((body['papers'][0]['status'], body['usd']), ('done', None))   # no catalog price for this model

    def test_the_page_image_of_a_set_pdf(self):
        r = self.c.get(f'{API}/sets/tensile/pdfs/7/pages/1/image?w=400')
        self.assertEqual((r.status_code, r.headers['content-type'], r.content[:8]), (200, 'image/png', b'\x89PNG\r\n\x1a\n'))
        for path in (f'{API}/sets/tensile/pdfs/7/pages/3/image', f'{API}/sets/tensile/pdfs/77/pages/1/image',
                     f'{API}/sets/../pdfs/7/pages/1/image', f'{API}/sets/tensile/pdfs/..%2F7/pages/1/image'):
            self.assertEqual(self.c.get(path).status_code, 404, path)


if __name__ == '__main__':
    unittest.main()
