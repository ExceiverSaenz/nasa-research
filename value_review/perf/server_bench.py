"""Server latency, CPU, memory and disk under realistic use (13-performance-report.md, part B1).

    python -B -m value_review.perf.server_bench [--dataset real|stress] [--runs 30] [--json out.json] [--profile]

``real`` loads the LLM run and PDFs of the source root (read only) into a temporary data folder; ``stress`` builds the
synthetic set of perf/stress_data.py. The real launcher serves it on a free port; requests go over HTTP with a kept-alive
connection, so times include the server stack. ``psutil`` samples the server's CPU and memory during each scenario.
``--profile`` adds an in-process cProfile and tracemalloc run of the slowest operations. Nothing outside the temporary
folder is written.
"""
import argparse
import cProfile
import http.client
import io
import json
import pstats
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import config as vr_config  # noqa: E402
from value_review.ingest import ingest_run  # noqa: E402

API = '/api/v1'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Client:
    """One kept-alive HTTP connection, like one browser tab."""

    def __init__(self, port):
        self.port = port
        self.conn = http.client.HTTPConnection('127.0.0.1', port, timeout=120)

    def call(self, method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        h = {'Content-Type': 'application/json'} if body is not None else {}
        h.update(headers or {})
        for attempt in (1, 2):
            t = time.perf_counter()
            try:
                self.conn.request(method, API + path, body=data, headers=h)
                res = self.conn.getresponse()
                payload = res.read()
                break
            except (ConnectionError, http.client.RemoteDisconnected, http.client.CannotSendRequest):
                # the server closed an idle kept-alive connection (uvicorn: after 5 s); reconnect like a browser
                self.conn.close()
                self.conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120)
                if attempt == 2:
                    raise
        ms = (time.perf_counter() - t) * 1000
        if res.status >= 400:
            raise RuntimeError(f'{method} {path}: {res.status} {payload[:200]!r}')
        return ms, payload


class Sampler:
    """CPU % and RSS of the server process, every 50 ms, while a scenario runs."""

    def __init__(self, proc):
        self.proc, self.cpu, self.rss, self._stop = proc, [], [], threading.Event()

    def __enter__(self):
        self.proc.cpu_percent(None)
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def _run(self):
        while not self._stop.wait(0.05):
            try:
                self.cpu.append(self.proc.cpu_percent(None))
                self.rss.append(self.proc.memory_info().rss)
            except psutil.Error:
                return

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()

    def summary(self):
        cpu = [c / psutil.cpu_count() for c in self.cpu] or [0]
        return {'cpu_avg_%': round(statistics.mean(cpu), 1), 'cpu_max_%': round(max(cpu), 1),
                'rss_max_mb': round(max(self.rss or [0]) / 2 ** 20, 1)}


def stats(times):
    s = sorted(times)
    pick = lambda q: s[min(len(s) - 1, int(round(q * (len(s) - 1))))]   # noqa: E731
    return {'n': len(s), 'p50_ms': round(pick(0.5), 1), 'p95_ms': round(pick(0.95), 1), 'max_ms': round(s[-1], 1)}


def build_real(tmp):
    run, pdfs = vr_config.default_run_dir(), vr_config.default_pdf_dir()
    data = Path(tmp) / 'data'
    rows = ingest_run(run, pdfs, data / 'originals')
    if not rows or any(r['outcome'] != 'written' for r in rows):
        raise SystemExit(f'could not load the real run from {run}')
    (data / 'annotations').mkdir(parents=True, exist_ok=True)
    (data / 'annotations' / 'settings.json').write_text(json.dumps({
        'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5, 'active_source': 'default',
        'sources': [{'id': 'default', 'name': run.name, 'run_dir': str(run), 'pdf_dir': str(pdfs)}]}), encoding='utf-8')
    return data


def build_stress(tmp):
    from value_review.perf import stress_data
    data = stress_data.build(Path(tmp) / 'stress')
    stress_data.add_versions(data, '1', 20)
    return data


def full_state(original, k=0):
    verdicts = ['accepted', 'rejected', 'unsure']
    decisions = {o['observation_id']: {'verdict': verdicts[(i + k) % 3], 'note': '' if (i + k) % 3 == 0 else 'A reason',
                                       'by': 'Expert reviewer', 'at': '2026-11-19T10:00:00Z'}
                 for i, o in enumerate(original['observations'])}
    return {'schema': 'value-review-state/1', 'decisions': decisions, 'column_moves': {}, 'record_moves': {}, 'record_edits': {},
            'added_records': [], 'added_values': [], 'boxes': {}}


def folder_size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file()) if Path(path).exists() else 0


def run_bench(data, runs):
    port = free_port()
    # fixed arguments: this same Python, the package's own launcher, a temporary data folder
    proc = subprocess.Popen([sys.executable, '-B', '-m', 'value_review', '--no-browser', '--port', str(port), '--data', str(data)],  # noqa: S603
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    server = psutil.Process(proc.pid)
    try:
        for _ in range(200):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        c = Client(port)
        out = {'idle_rss_mb': round(server.memory_info().rss / 2 ** 20, 1)}
        papers = json.loads(c.call('GET', '/papers')[1])
        big = max(papers, key=lambda p: p['values'])
        out['papers'], out['largest'] = len(papers), {'paper': big['paper'], 'values': big['values'], 'pages': big['pages'], 'versions': big['version']}
        pid, base = big['paper'], big['version']
        results = {}

        def scenario(name, fn, n=runs):
            times = []
            with Sampler(server) as s:
                for i in range(n):
                    times.append(fn(i))
            results[name] = {**stats(times), **s.summary()}

        scenario('settings', lambda i: c.call('GET', '/settings')[0])
        scenario('list papers', lambda i: c.call('GET', '/papers')[0])
        scenario('open largest paper', lambda i: c.call('GET', f'/papers/{pid}')[0])
        original = json.loads(c.call('GET', f'/papers/{pid}')[1])['original']

        # page images: cold (cache emptied) and cached
        cache = Path(data) / 'cache'
        pages = list(range(1, min(big['pages'], 10) + 1))
        for width in (800, 1200, 2400):
            shutil.rmtree(cache, ignore_errors=True)
            scenario(f'page image cold {width}px', lambda i, w=width: c.call('GET', f'/papers/{pid}/pages/{pages[i % len(pages)]}/image?w={w}')[0],
                     n=len(pages))
        scenario('page image cached 1200px', lambda i: c.call('GET', f'/papers/{pid}/pages/1/image?w=1200')[0])
        png_sizes = [p.stat().st_size for p in cache.rglob('*-1200.png')]
        out['page_png_kb_1200'] = round(statistics.mean(png_sizes) / 1024, 1) if png_sizes else None

        state = full_state(original)
        scenario('save draft (every value decided)', lambda i: c.call('PUT', f'/papers/{pid}/draft',
                                                                     {'base_version': base, 'trigger': 'auto', 'state': state})[0])
        c.call('DELETE', f'/papers/{pid}/draft')
        submits = max(5, runs // 3)
        scenario('submit (full snapshot)', lambda i: c.call('POST', f'/papers/{pid}/versions', {'state': full_state(original, i)},
                                                           {'If-Match': f'"{base + i}"'})[0], n=submits)
        scenario('version list', lambda i: c.call('GET', f'/papers/{pid}/versions')[0])
        scenario('list papers (after versions)', lambda i: c.call('GET', '/papers')[0])
        scenario('export csv', lambda i: c.call('GET', f'/papers/{pid}/versions/{base + submits}/export.csv')[0], n=10)
        scenario('export json', lambda i: c.call('GET', f'/papers/{pid}/versions/{base + submits}/export.json')[0], n=10)
        scenario('export latest.zip', lambda i: c.call('GET', '/export/latest.zip')[0], n=5)
        scenario('load papers again', lambda i: c.call('POST', '/ingest')[0], n=5)

        # four tabs at once: open a paper and five cold pages each
        shutil.rmtree(cache, ignore_errors=True)
        targets = [p['paper'] for p in sorted(papers, key=lambda p: -p['pages'])[:4]]
        per_request, lock = [], threading.Lock()

        def tab(paper):
            cl = Client(port)
            for path in [f'/papers/{paper}'] + [f'/papers/{paper}/pages/{n}/image?w=1200' for n in range(1, 6)]:
                ms = cl.call('GET', path)[0]
                with lock:
                    per_request.append(ms)
        with Sampler(server) as s:
            t0 = time.perf_counter()
            threads = [threading.Thread(target=tab, args=(p,)) for p in targets]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            wall = (time.perf_counter() - t0) * 1000
        results['4 tabs at once (open + 5 cold pages each)'] = {**stats(per_request), 'wall_ms': round(wall, 1), **s.summary()}

        # memory soak: 1,000 mixed requests
        rss0 = server.memory_info().rss
        mix = ['/papers', f'/papers/{pid}', '/settings', f'/papers/{pid}/versions', f'/papers/{pid}/pages/1/image?w=1200']
        with Sampler(server) as s:
            for i in range(1000):
                c.call('GET', mix[i % len(mix)])
        out['soak_1000'] = {'rss_start_mb': round(rss0 / 2 ** 20, 1), 'rss_end_mb': round(server.memory_info().rss / 2 ** 20, 1), **s.summary()}
        out['cache_mb'] = round(folder_size(cache) / 2 ** 20, 2)
        out['versions_mb'] = round(folder_size(Path(data) / 'annotations' / 'versions') / 2 ** 20, 2)
        out['results'] = results
        return out
    finally:
        proc.terminate()
        proc.wait(10)


def image_formats(data):
    """The same rendered page as PNG (as served), optimized PNG, JPEG and WebP: bytes only, nothing adopted."""
    from PIL import Image
    pngs = sorted(Path(data, 'cache').rglob('*-1200.png'))
    if not pngs:
        return None
    img = Image.open(pngs[0]).convert('RGB')
    sizes = {'png_as_served': pngs[0].stat().st_size}
    for name, kw in (('png_optimized', {'format': 'PNG', 'optimize': True}), ('jpeg_q85', {'format': 'JPEG', 'quality': 85}),
                     ('webp_q85', {'format': 'WEBP', 'quality': 85})):
        buf = io.BytesIO()
        t = time.perf_counter()
        img.save(buf, **kw)
        sizes[name] = {'kb': round(buf.tell() / 1024, 1), 'encode_ms': round((time.perf_counter() - t) * 1000, 1)}
    sizes['png_as_served'] = round(sizes['png_as_served'] / 1024, 1)
    return sizes


def profile(data, top=10):
    """cProfile (cumulative time) and tracemalloc peak of the heaviest operations, in process."""
    from fastapi.testclient import TestClient
    from value_review.service.app import create_app
    from value_review.service.config import Config
    out = {}
    with TestClient(create_app(Config(data=data), web_dir=None), base_url='http://127.0.0.1') as client:
        papers = client.get(f'{API}/papers').json()
        pid = max(papers, key=lambda p: p['values'])['paper']
        original = client.get(f'{API}/papers/{pid}').json()['original']
        cache = Path(data) / 'cache'
        current = len(client.get(f'{API}/papers/{pid}/versions').json())
        ops = {
            'list papers': lambda: client.get(f'{API}/papers'),
            'open largest paper': lambda: client.get(f'{API}/papers/{pid}'),
            'page image cold 1200px': lambda: (shutil.rmtree(cache, ignore_errors=True), client.get(f'{API}/papers/{pid}/pages/1/image?w=1200')),
            'save draft': lambda: client.put(f'{API}/papers/{pid}/draft', json={'base_version': current, 'trigger': 'auto', 'state': full_state(original)}),
        }
        for name, fn in ops.items():
            fn()   # warm caches the way a second request would see them
            prof = cProfile.Profile()
            tracemalloc.start()
            prof.enable()
            for _ in range(5):
                fn()
            prof.disable()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            buf = io.StringIO()
            pstats.Stats(prof, stream=buf).sort_stats('cumulative').print_stats(40)
            rows = []
            for line in buf.getvalue().splitlines():
                parts = line.split(None, 5)
                if len(parts) == 6 and parts[0].replace('/', '').isdigit() and 'value_review' in parts[5] or (len(parts) == 6 and any(k in parts[5] for k in ('jsonschema', 'json/', 'pypdfium2', 'PIL', 'hashlib', 'pathlib'))):
                    rows.append({'cum_s_per_5': float(parts[3]), 'function': parts[5].replace(str(ROOT), '').strip()[:110]})
            out[name] = {'tracemalloc_peak_mb': round(peak / 2 ** 20, 1), 'top': rows[:top]}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -B -m value_review.perf.server_bench')
    parser.add_argument('--dataset', choices=['real', 'stress'], default='real')
    parser.add_argument('--runs', type=int, default=30)
    parser.add_argument('--json', help='write the results to this file')
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args(argv)
    tmp = tempfile.mkdtemp(prefix='vr-bench-')
    try:
        data = build_real(tmp) if args.dataset == 'real' else build_stress(tmp)
        out = {'dataset': args.dataset, 'machine': {'cpus': psutil.cpu_count(), 'ram_gb': round(psutil.virtual_memory().total / 2 ** 30, 1),
                                                    'python': sys.version.split()[0]}}
        out.update(run_bench(data, args.runs))
        out['image_formats'] = image_formats(data)
        if args.profile:
            out['profile'] = profile(data)
        text = json.dumps(out, indent=1, ensure_ascii=False)
        if args.json:
            Path(args.json).write_text(text, encoding='utf-8')
        print(text)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
