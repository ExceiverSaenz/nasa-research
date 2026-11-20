"""The real launcher: uvicorn in a subprocess on 127.0.0.1 (OQ-10)."""
import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def launch(port):
    return subprocess.Popen([sys.executable, '-B', '-m', 'parsing_validator', '--port', str(port), '--no-browser'],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class Launcher(unittest.TestCase):
    def test_port_in_use_then_serve_then_second_instance_refused(self):
        taken = socket.socket()
        taken.bind(('127.0.0.1', 0))
        taken.listen(1)
        busy = launch(taken.getsockname()[1])
        _, err = busy.communicate(timeout=60)
        taken.close()
        self.assertEqual(busy.returncode, 2)
        self.assertIn('in use', err)

        port = free_port()
        first = launch(port)
        try:
            base = f'http://127.0.0.1:{port}'
            deadline = time.time() + 60
            while True:
                try:
                    status, raw = fetch(base + '/api/v1/health')
                    break
                except (urllib.error.URLError, ConnectionError):
                    self.assertIsNone(first.poll(), 'the service exited early')
                    self.assertLess(time.time(), deadline, 'the service did not start')
                    time.sleep(0.3)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)['status'], 'ok')
            self.assertEqual(json.loads(raw)['collection']['papers'], 23)
            self.assertEqual(fetch(base + '/api/v1/papers/6')[0], 404)
            self.assertEqual(fetch(base + '/api/v1/health', {'Origin': 'http://evil.example'})[0], 403)
            code, page = fetch(base + '/')
            self.assertEqual(code, 200)
            self.assertIn(b'Parsing Validator', page)

            second = launch(free_port())
            _, err = second.communicate(timeout=60)
            self.assertEqual(second.returncode, 2)
            self.assertIn('already running', err)
        finally:
            first.terminate()
            first.communicate(timeout=30)

        # terminate() does not run the cleanup on Windows: the next start must take over the stale lock
        third = launch(free_port())
        try:
            time.sleep(8)
            self.assertIsNone(third.poll(), 'a stale lock must be taken over')
        finally:
            third.terminate()
            third.communicate(timeout=30)


if __name__ == '__main__':
    unittest.main()
