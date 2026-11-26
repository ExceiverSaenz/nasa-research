"""A local fake of the model providers' "list models" endpoints, for the tests (52-models-keys-interface-contract.md).

It answers on 127.0.0.1 only. A key in ``GOOD`` gets 200 with that provider's answer shape, a key starting with
``slow-`` waits longer than the service's timeout, any other key gets 401. Requests are recorded (path and headers) so
tests can check how the key was sent. ``env()`` gives the variables that point the service at it.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GOOD = {'test-key-anthropic-0001', 'test-key-openai-0002', 'test-key-google-0003', 'test-key-server-0004'}
ANSWERS = {
    'anthropic': {'data': [{'id': 'claude-opus-5-5', 'display_name': 'Claude Opus 5.5'},
                           {'id': 'claude-haiku-5-5', 'display_name': 'Claude Haiku 5.5'}]},
    'openai': {'data': [{'id': 'gpt-test-1'}, {'id': 'gpt-test-mini'}, {'id': 'text-embedding-test'}]},
    'google': {'models': [{'name': 'models/gemini-test-pro', 'displayName': 'Gemini Test Pro', 'supportedGenerationMethods': ['generateContent']},
                          {'name': 'models/embedding-test', 'supportedGenerationMethods': ['embedContent']}]},
    'server': {'data': [{'id': 'local-llama-test'}]},
}


class FakeProvider:
    def __init__(self, delay=3.0):
        self.requests, self.delay, self.empty_server = [], delay, False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):   # quiet
                pass

            def do_GET(self):
                provider = self.path.strip('/').split('/', 1)[0]
                headers = {k.lower(): v for k, v in self.headers.items()}
                outer.requests.append({'provider': provider, 'path': self.path, 'headers': headers})
                key = headers.get('x-api-key') or headers.get('x-goog-api-key') or headers.get('authorization', '').removeprefix('Bearer ')
                if key.startswith('slow-'):
                    time.sleep(outer.delay)
                if key in GOOD and provider in ANSWERS:
                    answer = {'data': []} if provider == 'server' and outer.empty_server else ANSWERS[provider]
                    body, status = json.dumps(answer).encode(), 200
                else:
                    body, status = b'{"error": {"message": "invalid key"}}', 401
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:   # the client gave up (timeout test)
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def env(self):
        return {f'VALUE_REVIEW_PROVIDER_URL_{p.upper()}': f'{self.url}/{p}' for p in ('anthropic', 'openai', 'google')}

    def server_url(self):
        return f'{self.url}/server'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
