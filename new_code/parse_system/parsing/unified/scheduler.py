"""Bounded three-engine spawn coordinator, with terminal evidence on every attempt.

Renderer runs in a daemon thread in isolated temporary staging. Python cannot kill
an arbitrary renderer callable: on timeout its staging is retained and reported;
it cannot modify the terminal output. KeyboardInterrupt returns status interrupted
after collecting children (rather than re-raising).
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import multiprocessing as mp
import math
import os
from pathlib import Path
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback

MODELS = ('layoutlmv3', 'table_transformer', 'mineru')


def _fingerprint(runtime):
    return hashlib.sha256(json.dumps(runtime, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _manifest_hash(runtime):
    path = runtime.get('env_manifest')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None


def _package_fingerprint():
    packages = sorted((str(d.metadata.get('Name', '')).lower(), d.version)
                      for d in importlib.metadata.distributions())
    return hashlib.sha256(json.dumps(packages, separators=(',', ':')).encode()).hexdigest()


def _worker(model, runtime, factory, inbox, events, barrier, cancelled, output):
    engine = None
    package_fingerprint = None
    manifest_sha256 = None
    def emit(event, **fields):
        events.put(dict(event=event, model=model, time=time.monotonic(), pid=os.getpid(),
                        executable=sys.executable, prefix=sys.prefix,
                        runtime_fingerprint=_fingerprint(runtime), package_fingerprint=package_fingerprint, env_manifest_sha256=manifest_sha256, **fields))
    try:
        engine = factory(model, runtime)
        package_fingerprint = _package_fingerprint()
        manifest_sha256 = _manifest_hash(runtime)
        emit('ready')
        while not barrier.wait(.05):
            if cancelled.is_set():
                return
        while not cancelled.is_set():
            try:
                job = inbox.get(timeout=.05)
            except queue.Empty:
                continue
            if job is None:
                break
            key = dict(paper_id=job['paper_id'], page=job['page'])
            emit('started', **key)
            try:
                result = engine.process(job, Path(output) / 'results' / job['paper_id'] / str(job['page']) / model)
                # Fail in the child if its return value cannot cross the queue.
                json.dumps(result)
                emit('completed', result=result, **key)
            except BaseException:
                emit('failed', error=traceback.format_exc(), **key)
                return
    except BaseException:
        emit('failed', error=traceback.format_exc())
    finally:
        if engine is not None and hasattr(engine, 'close'):
            try:
                engine.close()
            except BaseException:
                emit('failed', error=traceback.format_exc())


def run_pipeline(papers: list[dict], output: Path, runtime: dict, *, renderer,
                 engine_factory, max_inflight=2, load_timeout=300, task_timeout=600) -> dict:
    """Return completed/failed/interrupted summary; never overwrite a destination."""
    if (type(max_inflight) is not int or max_inflight < 1
            or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                   for value in (load_timeout, task_timeout))):
        raise ValueError('positive max_inflight/load_timeout/task_timeout required')
    if not papers:
        raise ValueError('at least one paper required')
    ids = [p['id'] for p in papers]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i or i in ('.', '..') or '/' in i or '\\' in i or ':' in i for i in ids):
        raise ValueError('paper IDs must be unique safe path components')
    if any(type(p['page_count']) is not int or p['page_count'] < 1 for p in papers):
        raise ValueError('page_count must be positive')
    fingerprint = _fingerprint(runtime)
    package_fingerprint = _package_fingerprint()
    manifest_sha256 = _manifest_hash(runtime)
    output = Path(output).resolve()
    archive = output.with_name(output.name + '.zip')
    if output.exists() or archive.exists() or archive.with_suffix('.zip.sha256').exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    (output / 'inputs.json').write_text(json.dumps(papers, indent=2, default=str), encoding='utf-8')
    (output / 'configuration.json').write_text(json.dumps(runtime, indent=2), encoding='utf-8')
    tasks = [(p, n) for p in papers for n in range(1, p['page_count'] + 1)]
    tuples = {(p['id'], n, m): dict(paper_id=p['id'], page=n, model=m, status='pending')
              for p, n in tasks for m in MODELS}
    ctx = mp.get_context('spawn')
    events = ctx.Queue()
    inboxes = {m: ctx.Queue(maxsize=max_inflight) for m in MODELS}
    barrier, cancelled = ctx.Event(), ctx.Event()
    workers = {}
    history, ready, inflight, active = [], set(), {}, {}
    rendering = None
    rendered = queue.Queue()
    cursor, peak = 0, 0
    error, status = None, 'completed'
    staging = Path(tempfile.mkdtemp(prefix='parsing-render-', dir=output.parent))
    started = time.monotonic()

    def launch_render(paper, page):
        destination = staging / paper['id'] / str(page)
        def work():
            try:
                rendered.put((renderer(paper, page, destination), None))
            except KeyboardInterrupt:
                rendered.put((None, 'KeyboardInterrupt'))
            except BaseException:
                rendered.put((None, traceback.format_exc()))
        thread = threading.Thread(target=work, daemon=True, name='parsing-render')
        thread.start()
        return dict(thread=thread, paper=paper, page=page, start=time.monotonic(), destination=destination)

    def consume(event):
        history.append(event)
        model = event['model']
        if event['event'] == 'ready':
            if event['executable'] != sys.executable or event['prefix'] != sys.prefix or event['runtime_fingerprint'] != fingerprint or event['package_fingerprint'] != package_fingerprint or event['env_manifest_sha256'] != manifest_sha256:
                raise RuntimeError('worker environment mismatch')
            ready.add(model)
        elif event['event'] in ('started', 'completed', 'failed'):
            if 'page' in event:
                key = (event['paper_id'], event['page'], model)
                record = tuples[key]
                record['status'] = {'started': 'running', 'completed': 'completed', 'failed': 'failed'}[event['event']]
                record.update({k: v for k, v in event.items() if k in ('result', 'error', 'pid')})
                if event['event'] == 'started':
                    active[model] = (key, event['time'])
                else:
                    active.pop(model, None)
                    page_key = key[:2]
                    if page_key in inflight:
                        inflight[page_key].add(model)
                        if len(inflight[page_key]) == len(MODELS):
                            page_staging = staging / key[0] / str(key[1])
                            if page_staging.exists():
                                shutil.rmtree(page_staging)
                            del inflight[page_key]
            if event['event'] == 'failed':
                raise RuntimeError(f"{model}: {event['error']}")

    try:
        for model in MODELS:
            worker = ctx.Process(target=_worker, args=(model, runtime, engine_factory, inboxes[model], events, barrier, cancelled, str(output)), name=f'parsing-{model}')
            workers[model] = worker
            worker.start()
        while len(ready) != len(MODELS):
            try:
                consume(events.get(timeout=.02))
            except queue.Empty:
                pass
            for model, worker in workers.items():
                if worker.exitcode is not None:
                    raise RuntimeError(f'{model} exited during loading: {worker.exitcode}')
            if time.monotonic() - started > load_timeout:
                raise TimeoutError('model load timeout')
        history.append(dict(event='barrier_released', time=time.monotonic()))
        barrier.set()
        while cursor < len(tasks) or inflight or rendering:
            while True:
                try:
                    consume(events.get_nowait())
                except queue.Empty:
                    break
            for model, worker in workers.items():
                if worker.exitcode is not None:
                    raise RuntimeError(f'{model} exited before completion: {worker.exitcode}')
            now = time.monotonic()
            for model, (key, task_start) in active.items():
                if now - task_start > task_timeout:
                    tuples[key]['status'] = 'failed'
                    raise TimeoutError(f'{model} task timeout: {key}')
            if rendering:
                try:
                    job, render_error = rendered.get_nowait()
                except queue.Empty:
                    if now - rendering['start'] > task_timeout:
                        raise TimeoutError('render timeout')
                else:
                    if render_error == 'KeyboardInterrupt':
                        raise KeyboardInterrupt
                    if render_error:
                        raise RuntimeError('render failed: ' + render_error)
                    paper, page = rendering['paper'], rendering['page']
                    if job['paper_id'] != paper['id'] or job['page'] != page:
                        raise ValueError('renderer identity mismatch')
                    source = Path(job['render_path']).resolve()
                    relative = source.relative_to(rendering['destination'].resolve())
                    target = output / 'renders' / paper['id'] / str(page)
                    target.mkdir(parents=True, exist_ok=False)
                    (target / 'identity.json').write_text(json.dumps(job['identity'], indent=2), encoding='utf-8')
                    # Workers share staging until every engine has finished this page.
                    job = dict(job, render_path=str(source))
                    # JSON round trip isolates the immutable shared payload from renderer state.
                    job = json.loads(json.dumps(job))
                    history.append(dict(event='rendered', paper_id=paper['id'], page=page, time=now,
                                        render_path=job['render_path'], identity=job['identity']))
                    # One owner creates shared ancestors before the three workers
                    # create their independent model directories (Windows mkdir race).
                    (output / 'results' / paper['id'] / str(page)).mkdir(parents=True, exist_ok=False)
                    for model in MODELS:
                        inboxes[model].put(job, timeout=.1)
                        tuples[(paper['id'], page, model)]['status'] = 'queued'
                    rendering = None
            if rendering is None and cursor < len(tasks) and len(inflight) < max_inflight:
                paper, page = tasks[cursor]
                cursor += 1
                inflight[(paper['id'], page)] = set()
                peak = max(peak, len(inflight))
                rendering = launch_render(paper, page)
            time.sleep(.005)
        for inbox in inboxes.values():
            inbox.put(None, timeout=.1)
        deadline = time.monotonic() + task_timeout
        for worker in workers.values():
            worker.join(max(0, deadline - time.monotonic()))
            if worker.is_alive():
                raise TimeoutError('worker close timeout')
            if worker.exitcode != 0:
                raise RuntimeError(f'worker shutdown failed: {worker.exitcode}')
        while True:
            try:
                consume(events.get_nowait())
            except queue.Empty:
                break
    except KeyboardInterrupt:
        status, error = 'interrupted', 'KeyboardInterrupt'
    except BaseException:
        status, error = 'failed', traceback.format_exc()
    finally:
        cancelled.set()
        barrier.set()
        # Bounded graceful wait, then terminate/kill; no status/archive before joins.
        for worker in workers.values():
            if worker.pid is not None:
                worker.join(.2)
        for worker in workers.values():
            if worker.pid is not None and worker.is_alive():
                worker.terminate()
        for worker in workers.values():
            if worker.pid is not None:
                worker.join(2)
                if worker.is_alive():
                    worker.kill()
                    worker.join()
        # Preserve completed partial results already emitted before cancellation.
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            try:
                consume(event)
            except RuntimeError:
                pass
        history.append(dict(event='workers_stopped', time=time.monotonic()))
        for inbox in inboxes.values():
            inbox.cancel_join_thread()
            inbox.close()
        events.close()
        events.cancel_join_thread()
    if status != 'completed' and rendering is not None:
        page_key = (rendering['paper']['id'], rendering['page'])
        for model in MODELS:
            record = tuples[(*page_key, model)]
            if record['status'] == 'pending':
                record['status'] = 'failed' if status == 'failed' else 'cancelled'
                record['error'] = error
    for record in tuples.values():
        if record['status'] not in ('completed', 'failed', 'pending'):
            record['status'] = 'cancelled'
    retained = rendering is not None and rendering['thread'].is_alive()
    if not retained:
        if staging.resolve().parent != output.parent or staging.is_symlink() or getattr(os.path, 'isjunction', lambda p: False)(staging):
            raise RuntimeError('unsafe render staging cleanup path')
        shutil.rmtree(staging)
    counts = {name: sum(t['status'] == name for t in tuples.values()) for name in ('completed', 'failed', 'pending', 'cancelled')}
    completed_page_keys = {(p['id'], n) for p, n in tasks
                           if all(tuples[(p['id'], n, m)]['status'] == 'completed' for m in MODELS)}
    completed_pages = len(completed_page_keys)
    completed_papers = sum(all((p['id'], n) in completed_page_keys
                               for n in range(1, p['page_count'] + 1)) for p in papers)
    elapsed = time.monotonic() - started
    summary = dict(status=status, error=error, runtime_fingerprint=fingerprint, package_fingerprint=package_fingerprint, env_manifest_sha256=manifest_sha256, events=history,
                   tuples=list(tuples.values()), workers=[dict(model=m, pid=p.pid, exitcode=p.exitcode) for m,p in workers.items()],
                   metrics=dict(peak_inflight=peak, elapsed=elapsed, completed_pages=completed_pages,
                                completed_papers=completed_papers, pages_per_minute=completed_pages*60/elapsed,
                                papers_per_hour=completed_papers*3600/elapsed, **counts),
                   retained_render_staging=str(staging) if retained else None)
    (output / 'status.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    files = {}
    for path in sorted(output.rglob('*')):
        if path.is_file():
            files[path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(schema='parsing-hybrid-files/2', outputs=files)
    temporary = output / 'manifest.json.part'
    temporary.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    temporary.replace(output / 'manifest.json')
    return summary






