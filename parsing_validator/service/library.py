"""The sealed collection as the service sees it: verification, originals and page images (read side).

* Each paper is verified in a background thread (about 4 s per paper); a missing original is generated there
  too, under the paper lock, so a request that needs it and the worker never produce it twice (OP-02).
* An existing original is trusted only if its recorded identity matches the catalog and the PDF on disk.
* Nothing here writes inside a sealed tree; the page cache lives in ``.cache/pages`` (OQ-09).
"""
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..ingest.adapter import CollectionRepository
from ..ingest.original import write_original
from .errors import ApiError

SCALE_RANGE = (1.0, 3.0)


class Library:
    def __init__(self, config):
        self.cfg = config
        self.repo = CollectionRepository(str(config.collection))
        self.papers = sorted(self.repo.papers(), key=int)
        self.catalog_sha256 = self.repo.catalog_sha256
        self.state = {n: {'verification': 'pending', 'error': None} for n in self.papers}
        self._locks = {n: threading.RLock() for n in self.papers}
        self._originals = {}          # paper -> (mtime_ns, size, original, file sha256)
        self._pdf_seen = {}           # paper -> (size, mtime_ns) of the PDF last verified by hash
        self._render_lock = threading.Lock()   # pdfium is not thread-safe
        self._prefetch = ThreadPoolExecutor(max_workers=1, thread_name_prefix='prefetch')
        self._worker = None
        self._stop = threading.Event()

    # --- identity --------------------------------------------------------------
    def known(self, paper):
        if paper not in self.state:
            raise ApiError(404, 'paper_not_found', f'Paper {paper} is not in the collection')
        return paper

    def _fail(self, paper, code, reason):
        self.state[paper] = {'verification': 'failed', 'error': {'code': code, 'reason': reason}}

    def _identity_matches(self, paper, original):
        entry = self.repo.entry(paper)
        src = original['source']
        return (src['collection_sha256'] == self.catalog_sha256 and src['manifest_sha256'] == entry['manifest_sha256']
                and src['pdf_sha256'] == entry['pdf_sha256'])

    def _pdf(self, paper):
        """Path of the paper's PDF, checked against the sealed hash once per process (then by size and mtime)."""
        path = self.cfg.pdfs / f'{paper}.pdf'
        try:
            stat = path.stat()
        except OSError:
            raise ApiError(422, 'source_changed', f'The PDF of paper {paper} is missing') from None
        seen = (stat.st_size, stat.st_mtime_ns)
        if self._pdf_seen.get(paper) != seen:
            if hashlib.sha256(path.read_bytes()).hexdigest() != self.repo.entry(paper)['pdf_sha256']:
                self._pdf_seen.pop(paper, None)
                raise ApiError(422, 'source_changed', f'The PDF of paper {paper} no longer matches the sealed hash')
            self._pdf_seen[paper] = seen
        return path

    # --- background preparation --------------------------------------------------
    def start(self):
        if self.cfg.prepare and self._worker is None:
            self._worker = threading.Thread(target=self._prepare_all, name='prepare', daemon=True)
            self._worker.start()

    def stop(self):
        self._stop.set()
        self._prefetch.shutdown(wait=False, cancel_futures=True)

    def wait(self, timeout=None):
        if self._worker is not None:
            self._worker.join(timeout)

    def _prepare_all(self):
        for paper in self.papers:
            if self._stop.is_set():
                return
            try:
                self.ensure_original(paper)
            except ApiError:
                pass  # recorded in self.state

    def ensure_original(self, paper):
        """The paper's original (generated once if absent). Raises ``ApiError`` 422 if the paper cannot be used."""
        self.known(paper)
        with self._locks[paper]:
            if self.state[paper]['verification'] == 'failed':
                raise self._unavailable(paper)
            target = self.cfg.originals / f'{paper}.json'
            try:
                if target.is_file():
                    original = self._load(paper, target)
                    if not self._identity_matches(paper, original):
                        self._fail(paper, 'source_changed', 'The recorded identity differs from the sealed collection')
                        raise self._unavailable(paper)
                    self._pdf(paper)
                    if self.state[paper]['verification'] == 'pending':
                        self.repo.bindings(paper)  # the full seal verification (BR-02)
                        self.state[paper] = {'verification': 'ok', 'error': None}
                    return original
                write_original(self.cfg.collection, self.cfg.pdfs, paper, self.cfg.originals)
                self.state[paper] = {'verification': 'ok', 'error': None}
                return self._load(paper, target)
            except ApiError:
                raise
            except Exception as error:  # noqa: BLE001 - any verification failure makes the paper unavailable, never crashes the service
                self._fail(paper, 'paper_unavailable', type(error).__name__)
                raise self._unavailable(paper) from None

    def _unavailable(self, paper):
        error = self.state[paper]['error'] or {}
        code = error.get('code', 'paper_unavailable')
        return ApiError(422, 'source_changed' if code == 'source_changed' else 'paper_unavailable',
                        f'Paper {paper} failed verification', {'reason': error.get('reason')})

    # --- originals -------------------------------------------------------------
    def _load(self, paper, path):
        stat = path.stat()
        cached = self._originals.get(paper)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
        raw = path.read_bytes()
        original = json.loads(raw)
        self._originals[paper] = (stat.st_mtime_ns, stat.st_size, original, hashlib.sha256(raw).hexdigest())
        return original

    def original_if_ready(self, paper):
        """The original if it is already on disk and the paper is not failed; never generates (used by the list)."""
        self.known(paper)
        if self.state[paper]['verification'] == 'failed':
            return None
        path = self.cfg.originals / f'{paper}.json'
        if not path.is_file():
            return None
        try:
            return self._load(paper, path)
        except (OSError, ValueError):
            return None

    def original_hash(self, paper):
        return self._originals[paper][3]

    # --- pages -------------------------------------------------------------------
    def page(self, paper, index, layers):
        original = self.ensure_original(paper)
        page = next((p for p in original['pages'] if p['index'] == index), None)
        if page is None:
            raise ApiError(404, 'page_not_found', f'Paper {paper} has no page {index}')
        out = dict(page)
        out['layers'] = {name: {**layer, 'items': layer['items'] if name in layers else []}
                         for name, layer in page['layers'].items()}
        return out

    # --- page images (OP-05, OQ-09) ----------------------------------------------
    def image_path(self, paper, index, scale):
        original = self.ensure_original(paper)
        if not any(p['index'] == index for p in original['pages']):
            raise ApiError(404, 'page_not_found', f'Paper {paper} has no page {index}')
        pdf = self._pdf(paper)
        sha = original['source']['pdf_sha256']
        target = self.cfg.cache / 'pages' / f'{sha[:16]}_{index}_{scale:.2f}.png'
        if not target.is_file():
            self._render(pdf, index, scale, target)
        if self.cfg.prefetch and any(p['index'] == index + 1 for p in original['pages']):
            nxt = self.cfg.cache / 'pages' / f'{sha[:16]}_{index + 1}_{scale:.2f}.png'
            if not nxt.is_file():
                self._prefetch.submit(self._safe_render, pdf, index + 1, scale, nxt)
        return target, hashlib.sha256(f'{sha}:{index}:{scale:.2f}'.encode()).hexdigest()

    def _safe_render(self, pdf, index, scale, target):
        try:
            self._render(pdf, index, scale, target)
        except Exception:  # noqa: BLE001 - a failed prefetch only means the next request renders it
            pass

    def _render(self, pdf, index, scale, target):
        import pypdfium2 as pdfium
        with self._render_lock:
            if target.is_file():
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            doc = pdfium.PdfDocument(str(pdf))
            try:
                page = doc[index]
                try:
                    image = page.render(scale=scale).to_pil()
                finally:
                    page.close()
            finally:
                doc.close()
            temp = target.with_name(f'{target.name}.{os.getpid()}.{threading.get_ident()}.tmp')
            image.save(temp, format='PNG')
            image.close()
            os.replace(temp, target)

    def clear_cache(self):
        """The user's explicit action (Settings → Clear cache): removes only ``.cache/pages/*.png``."""
        folder, removed = self.cfg.cache / 'pages', 0
        for png in folder.glob('*.png') if folder.is_dir() else []:
            try:
                png.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    # --- reporting -------------------------------------------------------------
    def summary(self):
        counts = {'ok': 0, 'pending': 0, 'failed': 0}
        for item in self.state.values():
            counts[item['verification']] += 1
        return {'sha256': self.catalog_sha256, 'papers': len(self.papers), 'verified': counts['ok'],
                'pending': counts['pending'],
                'unavailable': [{'paper': n, **s['error']} for n, s in self.state.items() if s['verification'] == 'failed']}
