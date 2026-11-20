"""Originals, the source check (BR-09) and page images (OP-03). Sources are read only (BR-01)."""
import hashlib
import io
import json
import re
import threading
from pathlib import Path

from ..storage import atomic_write_bytes
from .errors import ApiError

PAPER_ID = re.compile(r'[0-9]{1,4}')
WIDTH_MIN, WIDTH_MAX, WIDTH_STEP, WIDTH_DEFAULT = 400, 2400, 200, 1240


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def snap_width(w):
    """Clamp to 400-2400 and round to a step of 200, so the cache stays small."""
    w = max(WIDTH_MIN, min(WIDTH_MAX, int(w)))
    return int(round(w / WIDTH_STEP) * WIDTH_STEP)


class Library:
    def __init__(self, config, paths=None, originals=None, cache=None):
        """``paths()`` returns the current (results folder, PDF folder); they can change in Settings.
        ``originals`` and ``cache`` are the folders of one source (folder pair); default: the data folder's."""
        self.paths = paths or (lambda: (Path(config.run_dir), Path(config.pdf_dir)))
        self.originals = Path(originals or config.originals)
        self.cache = Path(cache or config.cache)
        self._originals = {}
        self._hashes = {}           # path -> ((size, mtime_ns), sha256)
        self._lock = threading.Lock()
        self._render_lock = threading.Lock()   # pdfium is not thread-safe
        self._waiting = 0                       # reviewer renders waiting for the lock

    # --- originals -------------------------------------------------------------
    def papers(self):
        folder = self.originals
        if not folder.is_dir():
            return []
        ids = [p.stem for p in folder.glob('*.json') if PAPER_ID.fullmatch(p.stem)]
        return sorted(ids, key=int)

    def original(self, paper):
        if not PAPER_ID.fullmatch(str(paper)):
            raise ApiError(404, 'paper_not_found', f'No paper {paper}')
        path = self.originals / f'{paper}.json'
        try:
            st = path.stat()
        except OSError:
            raise ApiError(404, 'paper_not_found', f'No paper {paper}') from None
        key = (st.st_size, st.st_mtime_ns)
        with self._lock:
            cached = self._originals.get(paper)
            if cached and cached[0] == key:
                return cached[1]
        data = json.loads(path.read_text(encoding='utf-8'))
        with self._lock:
            self._originals[paper] = (key, data)
        return data

    def original_sha256(self, paper):
        return self._hash(self.originals / f'{paper}.json')

    # --- source check (BR-09) --------------------------------------------------
    def _hash(self, path):
        try:
            st = path.stat()
        except OSError:
            return None
        key = (st.st_size, st.st_mtime_ns)
        with self._lock:
            cached = self._hashes.get(path)
            if cached and cached[0] == key:
                return cached[1]
        digest = _sha256(path)
        with self._lock:
            self._hashes[path] = (key, digest)
        return digest

    def source_problems(self, original):
        """Codes for sources that are missing or no longer match the original: [] when all is well."""
        src = original['source']
        out = []
        run_dir, pdf_dir = self.paths()
        for name, folder, expected in (('result', run_dir, src['result_sha256']),
                                       ('pdf', pdf_dir, src['pdf_sha256'])):
            digest = self._hash(Path(folder) / src[f'{name}_file'])
            if digest is None:
                out.append(f'{name}_missing')
            elif digest != expected:
                out.append(f'{name}_changed')
        return out

    # --- page images (OP-03) ---------------------------------------------------
    def page_png(self, paper, page, width, prefetch=False):
        """The page as PNG. ``prefetch`` (a page the client fetches ahead) yields to the reviewer: when it is not cached
        and a render is running or a reviewer's request is waiting, it returns None instead of queueing ahead of them
        (13-performance-report.md, B-4)."""
        original = self.original(paper)
        pages = {p['number']: p for p in original['pages']}
        if page not in pages:
            raise ApiError(404, 'page_not_found', f'Paper {paper} has no page {page}')
        problems = self.source_problems(original)
        if any(p.startswith('pdf_') for p in problems):
            raise ApiError(422, 'source_changed', 'The PDF is missing or changed since ingest', {'problems': problems})
        width = snap_width(width)
        sha = original['source']['pdf_sha256']
        target = self.cache / 'pages' / str(paper) / f'{sha[:16]}-{page}-{width}.png'
        if target.is_file():
            return target.read_bytes()
        if prefetch and (self._render_lock.locked() or self._waiting):
            return None
        with self._lock:
            self._waiting += 0 if prefetch else 1
        try:
            self._render_lock.acquire()
        finally:
            with self._lock:
                self._waiting -= 0 if prefetch else 1
        try:
            if target.is_file():
                return target.read_bytes()
            data = self._render(Path(self.paths()[1]) / original['source']['pdf_file'], page, width / pages[page]['width_pt'])
            atomic_write_bytes(target, data)
        finally:
            self._render_lock.release()
        return data

    @staticmethod
    def _render(pdf, page, scale):
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(pdf))
        try:
            pg = doc[page - 1]
            try:
                image = pg.render(scale=scale).to_pil()
            finally:
                pg.close()
        finally:
            doc.close()
        buf = io.BytesIO()
        # compress_level 3: 22-42 % faster to encode than the default 6 for 1.5 % more bytes (13-performance-report.md, B-4)
        image.convert('RGB').save(buf, format='PNG', compress_level=3)
        return buf.getvalue()
