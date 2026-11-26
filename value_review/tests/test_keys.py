"""Tests of the API keys and models (52-models-keys-interface-contract.md, OP-K01 to OP-K06): AC-K01 to AC-K09 and
BR-K01 to BR-K06, against a local fake provider. No request leaves the machine."""
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.service import providers  # noqa: E402
from value_review.storage import StorageError  # noqa: E402
from value_review.storage.secrets import SecretStore  # noqa: E402
from value_review.tests.fake_provider import FakeProvider  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

OPENAI, ANTHROPIC, SERVER = 'test-key-openai-0002', 'test-key-anthropic-0001', 'test-key-server-0004'


class Keys(Base):
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
        self.fake.requests.clear()
        self.fake.empty_server = False
        patcher = mock.patch.dict(os.environ, self.fake.env())
        patcher.start()
        self.addCleanup(patcher.stop)

    @property
    def secrets_path(self):
        return self.client.app.state.secrets.path

    def add(self, provider='openai', key=OPENAI, **extra):
        return self.client.post('/api/v1/keys', json={'provider': provider, 'key': key, **extra})

    def responses_never_hold(self, *texts):
        bodies = [self.client.get(p).text for p in ('/api/v1/keys', '/api/v1/models', '/api/v1/settings')]
        for text in texts:
            for b in bodies:
                self.assertNotIn(text, b)

    def test_no_keys(self):   # AC-K01
        self.assertEqual(self.client.get('/api/v1/keys').json(), [])
        models = self.client.get('/api/v1/models').json()
        self.assertEqual([m['id'] for m in models['models']][:2], ['anthropic:claude-opus-5-5', 'anthropic:claude-sonnet-5-5'])
        self.assertFalse(any(m['available'] for m in models['models']))
        self.assertEqual(models['models'][0]['usd_per_paper'], 0.32)   # 60 000 x $4 + 4 000 x $20 per million
        self.assertFalse(self.secrets_path.exists())

    def test_a_working_key_is_saved_and_never_returned(self):   # AC-K02, BR-K01, BR-K06
        r = self.add(name='Lab account', monthly_limit_usd=50)
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual({k: body[k] for k in ('provider', 'name', 'last4', 'monthly_limit_usd', 'spent_usd', 'default', 'models_found')},
                         {'provider': 'openai', 'name': 'Lab account', 'last4': '0002', 'monthly_limit_usd': 50, 'spent_usd': 0,
                          'default': True, 'models_found': 3})
        self.assertNotIn(OPENAI, r.text)
        self.responses_never_hold(OPENAI)
        sent = self.fake.requests[-1]
        self.assertEqual((sent['path'], sent['headers']['authorization']), ('/openai/models', f'Bearer {OPENAI}'))
        stored = json.loads(self.secrets_path.read_text(encoding='utf-8'))
        self.assertEqual(schemas.errors('secrets', stored), [])
        self.assertEqual(stored['keys'][0]['key'], OPENAI)
        self.assertNotIn(OPENAI, self.store.settings_path.read_text(encoding='utf-8') if self.store.settings_path.exists() else '')

    def test_how_each_provider_gets_the_key(self):
        self.add('anthropic', ANTHROPIC)
        self.add('google', 'test-key-google-0003')
        a, g = self.fake.requests[0], self.fake.requests[1]
        self.assertEqual((a['path'], a['headers']['x-api-key'], a['headers']['anthropic-version']),
                         ('/anthropic/models?limit=1000', ANTHROPIC, '2023-06-01'))
        self.assertEqual((g['path'], g['headers']['x-goog-api-key']), ('/google/models?pageSize=1000', 'test-key-google-0003'))
        self.assertNotIn('test-key-google-0003', g['path'])   # never in the URL
        ids = [m['id'] for m in self.client.get('/api/v1/models').json()['models'] if m['available']]
        self.assertEqual(ids, ['anthropic:claude-opus-5-5', 'anthropic:claude-haiku-5-5', 'google:gemini-test-pro'])

    def test_a_rejected_key_is_not_saved(self):   # AC-K03
        r = self.add(key='wrong-key-1234')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['message']),
                         (422, 'key_rejected', 'The provider did not accept this key.'))
        self.assertNotIn('wrong-key-1234', r.text)
        self.assertFalse(self.secrets_path.exists())

    def test_an_unreachable_or_slow_provider(self):   # AC-K04
        with mock.patch.object(providers, 'TIMEOUT', 0.5):
            r = self.add(key='slow-key-12345')
        self.assertEqual((r.status_code, r.json()['error']['code']), (502, 'provider_unreachable'))
        self.assertEqual(r.json()['error']['message'], 'Could not reach OpenAI. Check the connection and try again.')
        for base in ('http://127.0.0.1:9/none', 'file:///etc'):   # nothing listening; not http(s)
            with mock.patch.dict(os.environ, {'VALUE_REVIEW_PROVIDER_URL_OPENAI': base}):
                r = self.add()
            self.assertEqual((r.status_code, r.json()['error']['code']), (502, 'provider_unreachable'), base)
        self.assertFalse(self.secrets_path.exists())

    def test_invalid_input(self):
        for body in ({'provider': 'openai', 'key': 'short'}, {'provider': 'openai', 'key': 'has a space 123'},
                     {'provider': 'other', 'key': OPENAI}, {'provider': 'server', 'key': SERVER, 'url': 'ftp://x'},
                     {'provider': 'server', 'key': SERVER}, {'provider': 'openai', 'key': OPENAI, 'monthly_limit_usd': -1},
                     {'provider': 'openai', 'key': OPENAI, 'extra': 1}):
            r = self.client.post('/api/v1/keys', json=body)
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'), body)
        self.assertEqual(self.fake.requests, [])   # nothing was sent

    def test_defaults_per_provider(self):   # AC-K05, BR-K02
        first = self.add(name='Lab').json()
        second = self.add(name='').json()
        self.assertEqual((first['default'], second['default'], second['name']), (True, False, 'OpenAI key 2'))
        r = self.client.patch(f"/api/v1/keys/{second['id']}", json={'default': True})
        self.assertEqual(r.json()['default'], True)
        keys = {k['id']: k for k in self.client.get('/api/v1/keys').json()}
        self.assertEqual((keys[first['id']]['default'], keys[second['id']]['default']), (False, True))
        self.assertEqual(self.client.delete(f"/api/v1/keys/{second['id']}").status_code, 204)
        self.assertEqual([(k['id'], k['default']) for k in self.client.get('/api/v1/keys').json()], [(first['id'], True)])
        self.assertEqual(self.client.delete('/api/v1/keys/k_00000000').status_code, 404)

    def test_editing(self):   # BR-K03
        kid = self.add(name='Lab', monthly_limit_usd=50).json()['id']
        self.fake.requests.clear()
        r = self.client.patch(f'/api/v1/keys/{kid}', json={'name': 'Lab 2', 'monthly_limit_usd': None})
        self.assertEqual((r.json()['name'], r.json()['monthly_limit_usd'], self.fake.requests), ('Lab 2', None, []))   # not tested again
        r = self.client.patch(f'/api/v1/keys/{kid}', json={'key': 'wrong-key-1234'})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.get('/api/v1/keys').json()[0]['last4'], '0002')   # the old key stays
        self.assertEqual(self.client.post(f'/api/v1/keys/{kid}/test').status_code, 200)

    def test_models_follow_the_keys(self):   # AC-K06, AC-K07, BR-K04
        r = self.client.put('/api/v1/models', json={'enabled': ['openai:gpt-test-1']})
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']),
                         (400, 'model_unavailable', {'models': ['openai:gpt-test-1']}))
        kid = self.add().json()['id']
        self.add('anthropic', ANTHROPIC)
        rows = {m['id']: m for m in self.client.get('/api/v1/models').json()['models']}
        self.assertNotIn('openai:text-embedding-test', rows)   # cannot write text
        self.assertEqual((rows['openai:gpt-test-1']['usd_per_paper'], rows['openai:gpt-test-1']['source']), (None, 'provider'))
        self.assertFalse(rows['anthropic:claude-sonnet-5-5']['available'])   # in the catalog, not listed by the key
        r = self.client.put('/api/v1/models', json={'enabled': ['openai:gpt-test-1', 'anthropic:claude-opus-5-5'], 'default': 'openai:gpt-test-1'})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client.put('/api/v1/models', json={'enabled': ['openai:gpt-test-1'], 'default': 'anthropic:claude-opus-5-5'})
        self.assertEqual(r.status_code, 400)
        self.client.delete(f'/api/v1/keys/{kid}')   # the last OpenAI key
        s = self.client.get('/api/v1/settings').json()
        self.assertEqual((s['models_enabled'], s['default_model']), (['anthropic:claude-opus-5-5'], 'anthropic:claude-opus-5-5'))

    def test_own_server(self):   # AC-K08
        self.fake.empty_server = True
        r = self.add('server', SERVER, url=self.fake.server_url() + '/')
        self.assertEqual((r.status_code, r.json()['url'], r.json()['models_found']), (201, self.fake.server_url(), 0))
        self.assertEqual(self.fake.requests[-1]['path'], '/server/models')
        r = self.client.put('/api/v1/models', json={'enabled': ['server:my-model'], 'manual': ['my-model']})
        self.assertEqual(r.status_code, 200, r.text)
        row = next(m for m in r.json()['models'] if m['id'] == 'server:my-model')
        self.assertEqual((row['source'], row['enabled'], row['default']), ('manual', True, True))

    @unittest.skipUnless(os.name == 'posix', 'file modes are a POSIX feature')
    def test_owner_only_file(self):   # AC-K09
        self.add()
        self.assertEqual(stat.S_IMODE(self.secrets_path.stat().st_mode), 0o600)

    def test_disk_and_file_problems(self):   # BR-K06
        with mock.patch.object(SecretStore, 'write', side_effect=StorageError('Could not write secrets.json: Access is denied')):
            r = self.add()
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_path.write_text('{"schema": "value-review-secrets/1", "keys": [{"key": "' + OPENAI + '"}]}', encoding='utf-8')
        r = self.client.get('/api/v1/keys')
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertNotIn(OPENAI, r.text)   # not even in the error


if __name__ == '__main__':
    unittest.main()
