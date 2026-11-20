"""MathML for LaTeX segments (BR-17, ADR-006): the pinned KaTeX run by one long-lived Node subprocess.

``MathRenderer.derive(latex_list)`` returns new segments ``{source, tag, mathml, error}``. The source is kept as
the user typed it; a ``\\tag{n}`` in it is removed before rendering and stored as ``tag``. Invalid LaTeX gives
``mathml: None`` and KaTeX's message in ``error``. If Node or the vendored file is unavailable (or its SHA-256
differs), saving still works: ``mathml: None``, ``error: "renderer_unavailable"``.
"""
import hashlib
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

KATEX_DIR = Path(__file__).resolve().parent.parent / 'vendor' / 'katex'
KATEX_SHA256 = 'e6bfe5deebd4c7ccd272055bab63bd3ab2c73b907b6e6a22d352740a81381fd4'
UNAVAILABLE = 'renderer_unavailable'
TAG = re.compile(r'\\tag\*?\s*\{([^{}]*)\}')


def split_tag(source):
    """(source without ``\\tag{n}``, the tag text or None)."""
    found = TAG.search(source)
    if not found:
        return source, None
    return TAG.sub('', source).strip(), found.group(1).strip() or None


class MathRenderer:
    def __init__(self, *, katex_dir=KATEX_DIR, node=None, timeout=10.0):
        self.dir = Path(katex_dir)
        self.node = node if node is not None else shutil.which('node')
        self.timeout = timeout
        self.renderer = None            # "katex@x.y.z" once started
        self.problem = None             # why it is unavailable, if it is
        self._proc = None
        self._lock = threading.Lock()
        self._next = 0

    # --- process ---------------------------------------------------------------
    def _start(self):
        script, lib = self.dir / 'render.js', self.dir / 'katex.min.js'
        if not self.node:
            raise RuntimeError('node not found')
        if not script.is_file() or not lib.is_file():
            raise RuntimeError('vendored KaTeX missing')
        if hashlib.sha256(lib.read_bytes()).hexdigest() != KATEX_SHA256:
            raise RuntimeError('vendored katex.min.js does not match the pinned SHA-256')
        self._proc = subprocess.Popen([self.node, str(script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, encoding='utf-8', bufsize=1)
        ready = self._read()
        if not ready or not ready.get('ready'):
            raise RuntimeError('renderer did not report ready')
        self.renderer = ready['renderer']

    def _read(self):
        """One JSON line from the subprocess, or None on timeout/EOF (the process is then discarded)."""
        out = {}
        reader = threading.Thread(target=lambda: out.setdefault('line', self._proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(self.timeout)
        line = out.get('line')
        if not line:
            self._kill()
            return None
        return json.loads(line)

    def _kill(self):
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:  # noqa: BLE001 - best effort
                pass
            for pipe in (proc.stdin, proc.stdout):
                try:
                    pipe.close()
                except Exception:  # noqa: BLE001
                    pass

    def close(self):
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.stdin.close()
                    self._proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    pass
                self._kill()

    @property
    def available(self):
        with self._lock:
            return self._ensure()

    def _ensure(self):
        if self._proc is not None and self._proc.poll() is None:
            return True
        self._kill()
        try:
            self._start()
            self.problem = None
            return True
        except Exception as error:  # noqa: BLE001 - any failure means "unavailable", never blocks saving
            self._kill()
            self.problem = str(error)
            return False

    # --- rendering ---------------------------------------------------------------
    def render(self, source):
        """``(mathml | None, error | None)`` for one already-stripped source."""
        with self._lock:
            if not self._ensure():
                return None, UNAVAILABLE
            self._next += 1
            try:
                self._proc.stdin.write(json.dumps({'id': self._next, 'source': source}) + '\n')
                self._proc.stdin.flush()
                reply = self._read()
            except (OSError, ValueError):
                self._kill()
                return None, UNAVAILABLE
            if reply is None or reply.get('id') != self._next:
                self._kill()
                return None, UNAVAILABLE
            return reply.get('mathml'), reply.get('error')

    def derive(self, latex):
        """Recompute every segment (a client-sent ``mathml`` is never trusted)."""
        result = []
        for item in latex or []:
            source, tag = split_tag(item['source'])
            mathml, error = self.render(source) if source.strip() else (None, 'empty_source')
            result.append({'source': item['source'], 'tag': tag if tag is not None else item.get('tag'),
                           'mathml': mathml, 'error': error})
        return result
