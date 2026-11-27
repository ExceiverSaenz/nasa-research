"""Tests of the model calls (service/extraction/models.py; ADR-026) against the local fake provider. No real
provider is called."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.service.extraction import models  # noqa: E402
from value_review.tests.fake_provider import FakeProvider  # noqa: E402
from value_review.tests.text_pdf import make_text_pdf  # noqa: E402

ANTHROPIC, OPENAI = 'test-key-anthropic-0001', 'test-key-openai-0002'


class Models(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeProvider(delay=2.0)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = Path(cls.tmp.name) / '7.pdf'
        make_text_pdf(cls.pdf, [['Material: FeCrAl', 'Yield strength 710 ± 25 MPa']])

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()
        cls.tmp.cleanup()

    def setUp(self):
        self.fake.requests.clear()
        self.fake.failures.clear()
        patcher = mock.patch.dict(os.environ, self.fake.env())
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, provider='anthropic', model='claude-opus-5-5', key=ANTHROPIC, timeout=10):
        return models.extract(provider, model, key, 'Extract the values.', self.pdf, timeout)

    def test_anthropic(self):
        answer = self.call()
        self.assertEqual([v['field_id'] for v in answer.data['values']], ['yield_strength', 'ultimate_tensile_strength', 'material'])
        self.assertEqual((answer.input_tokens, answer.output_tokens, answer.usd), (1000, 200, 0.008))   # $4 and $20 per million
        sent = self.fake.requests[-1]
        self.assertEqual((sent['path'], sent['model'], sent['prompt'], sent['pdf_bytes']),
                         ('/anthropic/v1/messages', 'claude-opus-5-5', 'Extract the values.', self.pdf.stat().st_size))
        self.assertEqual(sent['headers']['x-api-key'], ANTHROPIC)
        self.assertEqual(sent['format']['format']['type'], 'json_schema')
        self.assertEqual(sent['format']['format']['schema']['required'], ['records', 'values', 'completion'])

    def test_openai(self):
        answer = self.call('openai', 'gpt-test-1', OPENAI)
        self.assertEqual((len(answer.data['records']), answer.usd), (2, None))   # no catalog price (OQ-X01)
        sent = self.fake.requests[-1]
        self.assertEqual((sent['path'], sent['headers']['authorization'], sent['pdf_bytes']),
                         ('/openai/responses', f'Bearer {OPENAI}', self.pdf.stat().st_size))
        self.assertEqual((sent['format']['format']['type'], sent['format']['format']['strict']), ('json_schema', True))

    def failure(self, *args, **kwargs):
        with self.assertRaises(models.ModelError) as caught:
            self.call(*args, **kwargs)
        return caught.exception

    def test_failures_say_whether_to_retry(self):
        e = self.failure(key='wrong-key-1234')
        self.assertEqual((e.code, e.retry, e.message), ('key_rejected', False, 'The provider did not accept this key.'))
        self.assertNotIn('wrong-key-1234', e.message)
        for failure, code, retry in ((500, 'provider_error', True), (429, 'rate_limited', True), (404, 'model_not_found', False),
                                     (400, 'rejected', False), ('json', 'not_json', True)):
            self.fake.failures.append(failure)
            e = self.failure()
            self.assertEqual((e.code, e.retry), (code, retry), failure)
        self.fake.failures.append(500)
        self.assertEqual(self.failure('openai', 'gpt-test-1', OPENAI).code, 'provider_error')

    def test_a_wrong_shape_a_slow_answer_and_a_large_pdf(self):
        self.fake.answer = lambda _sha: {'records': [], 'values': [{'field_id': 'x'}], 'completion': {'status': 'complete', 'notes': ''}}
        try:
            self.assertEqual(self.failure().code, 'bad_answer')
        finally:
            from value_review.tests.fake_provider import answer_for
            self.fake.answer = answer_for
        self.fake.failures.append('slow')
        e = self.failure(timeout=0.5)
        self.assertEqual((e.code, e.retry), ('timeout', True))
        with mock.patch.object(models, 'MAX_PDF_BYTES', 10):
            self.assertEqual(self.failure().code, 'pdf_too_large')
        self.assertEqual(self.failure('google', 'gemini-test-pro', 'x').code, 'provider_pending')


if __name__ == '__main__':
    unittest.main()
