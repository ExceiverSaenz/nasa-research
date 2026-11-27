"""A local fake of the model providers, for the tests (52-models-keys-interface-contract.md,
72-extraction-interface-contract.md): their "list models" endpoints, and the Anthropic Messages and OpenAI Responses
endpoints a run calls.

It answers on 127.0.0.1 only. A key in ``GOOD`` gets 200 with that provider's answer shape, a key starting with
``slow-`` waits longer than the service's timeout, any other key gets 401. Requests are recorded (path and headers) so
tests can check how the key was sent. ``env()`` gives the variables that point the service at it.
"""
import base64
import hashlib
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


def answer_for(pdf_sha):
    """The default answer of the fake model: two records and three values on page 1. "Yield strength 710" and "FeCrAl"
    are on page 1 of the test PDFs made by tests.test_ingest.make_pdf with ``text``; the second quote is on no page."""
    return {'records': [{'record_id': 'r1', 'label': 'SS-J', 'condition': 'room temperature'},
                        {'record_id': 'r2', 'label': 'SS-Mini', 'condition': ''}],
            'values': [{'field_id': 'yield_strength', 'record_ids': ['r1'], 'value': '710 ± 25', 'unit': 'MPa', 'page': 1,
                        'quote': 'Yield strength 710', 'flags': ['reported_aggregate'], 'notes': ''},
                       {'field_id': 'ultimate_tensile_strength', 'record_ids': ['r1'], 'value': '845', 'unit': 'MPa', 'page': 1,
                        'quote': 'not on the page', 'flags': [], 'notes': ''},
                       {'field_id': 'material', 'record_ids': ['r1', 'r2'], 'value': 'FeCrAl', 'unit': '', 'page': 1,
                        'quote': 'FeCrAl', 'flags': [], 'notes': 'both specimens'}],
            'completion': {'status': 'complete', 'notes': f'pdf {pdf_sha[:8]}'}}


class FakeProvider:
    def __init__(self, delay=3.0):
        self.requests, self.delay, self.empty_server = [], delay, False
        # model calls: ``failures`` are answered first, one per call (an HTTP status, "json" for text that is not JSON,
        # or "slow" to wait ``delay`` first); then ``answer`` (a function of the PDF's sha256) gives the answer
        self.failures, self.answer, self.usage = [], answer_for, (1000, 200)
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

            def do_POST(self):
                provider = self.path.strip('/').split('/', 1)[0]
                headers = {k.lower(): v for k, v in self.headers.items()}
                body = json.loads(self.rfile.read(int(headers.get('content-length') or 0)) or b'{}')
                key = headers.get('x-api-key') or headers.get('authorization', '').removeprefix('Bearer ')
                parts = (body.get('messages') or body.get('input') or [{}])[0].get('content') or []
                pdf = next((p.get('source', {}).get('data') or p.get('file_data', '').split(',', 1)[-1]
                            for p in parts if p.get('type') in ('document', 'input_file')), '')
                raw = base64.b64decode(pdf) if pdf else b''
                text = next((p.get('text') for p in parts if p.get('type') in ('text', 'input_text')), '')
                outer.requests.append({'provider': provider, 'path': self.path, 'headers': headers, 'model': body.get('model'),
                                       'prompt': text, 'pdf_bytes': len(raw), 'format': body.get('output_config') or body.get('text')})
                failure = outer.failures.pop(0) if outer.failures else None
                if failure == 'slow':
                    time.sleep(outer.delay)
                    failure = None
                if key not in GOOD:
                    status, payload = 401, {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid key'}}
                elif isinstance(failure, int):
                    status, payload = failure, {'type': 'error', 'error': {'type': 'api_error', 'message': 'try again'}}
                else:
                    answer = 'not json {' if failure == 'json' else json.dumps(outer.answer(hashlib.sha256(raw).hexdigest()))
                    tokens_in, tokens_out = outer.usage
                    status = 200
                    if provider == 'anthropic':
                        payload = {'id': 'msg_fake', 'type': 'message', 'role': 'assistant', 'model': body.get('model'),
                                   'content': [{'type': 'text', 'text': answer}], 'stop_reason': 'end_turn', 'stop_sequence': None,
                                   'usage': {'input_tokens': tokens_in, 'output_tokens': tokens_out}}
                    else:
                        payload = {'id': 'resp_fake', 'object': 'response', 'created_at': 0, 'model': body.get('model'),
                                   'status': 'completed', 'output': [{'type': 'message', 'id': 'msg_fake', 'role': 'assistant',
                                   'status': 'completed', 'content': [{'type': 'output_text', 'text': answer, 'annotations': []}]}],
                                   'parallel_tool_calls': True, 'tool_choice': 'auto', 'tools': [],
                                   'usage': {'input_tokens': tokens_in, 'output_tokens': tokens_out, 'total_tokens': tokens_in + tokens_out,
                                             'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}}}
                data = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
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
