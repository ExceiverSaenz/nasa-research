"""Launching a run, OP-X04 and OP-X06 (72-extraction-interface-contract.md; ADR-025).

Papers are extracted by background threads inside the service, at most "papers at the same time" (Settings) per run.
The state of every paper is saved in <run>/papers.json after each change, so a restart loses nothing done: a run that
was running comes back Paused, and the papers that were extracting go back to Queued (AC-X10). Each finished paper is
written to the workspace, recorded in the run's manifest and loaded into Review at once. A paper with a Review version in
this run is never extracted again (BR-X05).
"""
import json
import math
import threading
import time
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from ...storage import StorageError, atomic_write_bytes
from .. import sources as pairs
from .. import workspace
from ..errors import ApiError
from ..workspace import RESULTS
from . import models, results, work

STATE = 'papers.json'
SECONDS_PER_PAPER = 90   # the estimate before any paper of this model has been timed (OQ-X02)


class LaunchIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    papers: list[str] | None = Field(default=None, max_length=5000)   # None: every paper without results


def _seconds(start, end):
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    return max(0.0, (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds())


class Launcher:
    def __init__(self, ctx):
        self.ctx = ctx
        self.locks = {}            # run id -> lock around its papers.json
        self.jobs = {}             # run id -> {'stop': None | 'pause' | 'cancel', 'threads': [...]}
        self.guard = threading.Lock()
        self.page_counts = {}

    # --- files -----------------------------------------------------------------------
    def lock(self, rid):
        with self.guard:
            return self.locks.setdefault(rid, threading.RLock())

    def state_path(self, rid):
        return self.ctx.runs.run_dir(rid) / STATE

    def read_state(self, rid):
        try:
            data = json.loads(self.state_path(rid).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        return {'papers': data.get('papers') or {}, 'sessions': data.get('sessions') or []}

    def write_state(self, rid, state):
        atomic_write_bytes(self.state_path(rid), (json.dumps(state, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))

    def folder(self, run):
        from pathlib import Path
        return Path(self.ctx.config.workspace) / RESULTS / run['set'] / run['folder']

    def reviewed(self, run):
        """Papers of this run that have a version in Review (BR-X05)."""
        sid = workspace.source_id(run['set'], run['folder'])
        root = pairs.source_dir(self.ctx.config.data, sid) / 'annotations' / 'versions'
        try:
            return {p.name for p in root.iterdir() if p.is_dir() and any(p.glob('v*.json'))}
        except OSError:
            return set()

    def has_result(self, run, paper):
        from ...config import RESULT_SUFFIX
        return self.ctx.config.workspace is not None and (self.folder(run) / f'{paper}{RESULT_SUFFIX}').is_file()

    # --- views -------------------------------------------------------------------------
    def pages(self, run, paper):
        """The page count of a set PDF, remembered by size and modification time."""
        path = work.pdf_path(self.ctx, run, paper)
        try:
            st = path.stat()
        except OSError:
            return None
        key = (str(path), st.st_size, st.st_mtime_ns)
        if key not in self.page_counts:
            import pypdfium2 as pdfium
            with results.PDFIUM:
                try:
                    doc = pdfium.PdfDocument(str(path))
                    self.page_counts[key] = len(doc)
                    doc.close()
                except Exception:   # a damaged PDF: no count
                    self.page_counts[key] = None
        return self.page_counts[key]

    def titles(self, run):
        """Titles of the papers already loaded into Review for this run."""
        sid = workspace.source_id(run['set'], run['folder'])
        folder = pairs.source_dir(self.ctx.config.data, sid) / 'originals'
        out = {}
        try:
            for p in folder.glob('*.json'):
                try:
                    out[p.stem] = json.loads(p.read_text(encoding='utf-8'))['document']['title']
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        except OSError:
            pass
        return out

    def papers(self, run):
        state, reviewed, titles = self.read_state(run['id']), self.reviewed(run), self.titles(run)
        out = []
        for p in work.set_papers(self.ctx, run):
            row = dict(state['papers'].get(p) or {})
            status = row.get('status') or ('done' if self.has_result(run, p) else 'no_results')
            if p in reviewed and status in ('no_results', 'queued', 'failed'):
                status = 'skipped_reviewed'
            out.append({'paper': p, 'status': status, 'reviewed': p in reviewed, 'error': row.get('error'),
                        'title': titles.get(p), 'pages': self.pages(run, p),
                        'attempts': row.get('attempts', 0), 'usd': row.get('usd'), 'seconds': row.get('seconds')})
        return out

    def progress(self, run):
        """Counts, the actual cost and time, for the run view."""
        state = self.read_state(run['id'])
        counts = {k: 0 for k in ('queued', 'extracting', 'done', 'failed')}
        usd, unknown = 0.0, False
        for row in state['papers'].values():
            if row.get('status') in counts:
                counts[row['status']] += 1
            if row.get('status') == 'done':
                if row.get('usd') is None:
                    unknown = True
                else:
                    usd += row['usd']
        seconds = sum(_seconds(s['started_at'], s.get('ended_at') or self.ctx.clock()) for s in state['sessions'])
        actual = {'usd': None if unknown and not usd else round(usd, 4), 'seconds': round(seconds, 1)} if state['sessions'] else None
        return {'counts': counts, 'actual': actual}

    def estimate(self, run, papers):
        provider, model = run['model'].split(':', 1) if run['model'] else (None, None)
        price = models.price(provider, model) if model else None
        n = len(papers)
        settings = self.ctx.settings_now()['extraction']
        from ..keys import per_paper
        usd = round(n * per_paper(price), 2) if price else None
        timed = [r['seconds'] for rid in self.ctx.runs.ids() for r in self.read_state(rid)['papers'].values()
                 if r.get('status') == 'done' and r.get('seconds') and r.get('model') == run['model']]
        each = sum(timed) / len(timed) if timed else SECONDS_PER_PAPER
        minutes = math.ceil(math.ceil(n / settings['parallel']) * each / 60) if n else 0
        key = next((k for k in self.ctx.secrets.read()['keys'] if k['id'] == run['key_id']), None)
        return {'papers': n, 'usd': usd, 'minutes': minutes, 'price_known': price is not None,
                'over_warning': bool(usd is not None and settings['warn_usd'] and usd > settings['warn_usd']),
                'warn_usd': settings['warn_usd'],
                'limit_unchecked': bool(price is None and key and key.get('monthly_limit_usd') is not None)}

    def to_extract(self, run, chosen):
        """The papers a launch extracts: the chosen ones (default: every paper without results), less those with a Review
        version and those already done."""
        rows = {r['paper']: r for r in self.papers(run)}
        wanted = list(dict.fromkeys(chosen)) if chosen is not None else [p for p, r in rows.items() if r['status'] in ('no_results', 'failed')]
        missing = [p for p in wanted if p not in rows]
        if missing:
            raise ApiError(404, 'paper_not_found', f'Not in the paper set: {", ".join(missing[:10])}')
        return [p for p in wanted if rows[p]['status'] in ('no_results', 'failed', 'queued')]

    # --- running -------------------------------------------------------------------------
    def set_paper(self, rid, paper, **values):
        with self.lock(rid):
            state = self.read_state(rid)
            state['papers'][paper] = {**(state['papers'].get(paper) or {}), **values}
            self.write_state(rid, state)

    def start(self, run):
        """Start the workers of a run whose papers are queued (its status is already running)."""
        rid = run['id']
        n = self.ctx.settings_now()['extraction']['parallel']
        with self.guard:
            job = self.jobs.get(rid)
            if job and job['live'] > 0:   # workers still on it pick up the newly queued papers
                job['stop'] = None
                return
            job = {'stop': None, 'threads': [], 'live': n}
            self.jobs[rid] = job
        with self.lock(rid):
            state = self.read_state(rid)
            state['sessions'].append({'started_at': self.ctx.clock(), 'ended_at': None})
            self.write_state(rid, state)
        _n, prompt = work.current_prompt(self.ctx, run)
        for i in range(n):
            t = threading.Thread(target=self.worker, args=(run, prompt, job), daemon=True, name=f'run-{rid}-{i}')
            job['threads'].append(t)
        for t in job['threads']:
            t.start()

    def next_paper(self, rid):
        with self.lock(rid):
            state = self.read_state(rid)
            paper = next((p for p, r in state['papers'].items() if r.get('status') == 'queued'), None)
            if paper:
                state['papers'][paper].update(status='extracting', started_at=self.ctx.clock())
                self.write_state(rid, state)
            return paper

    def worker(self, run, prompt, job):
        rid = run['id']
        try:
            while job['stop'] is None:
                paper = self.next_paper(rid)
                if paper is None:
                    break
                self.extract(run, prompt, paper, job)
        finally:
            self.done_worker(run, job)

    def extract(self, run, prompt, paper, job):
        rid = run['id']
        try:
            answer, result, attempts = work.extract_one(self.ctx, run, prompt, paper, lambda: job['stop'] == 'cancel')
            folder = self.folder(run)
            results.write_result(folder, paper, result)
            self.update_manifest(run, paper, answer)
            with self.ctx.ingest_lock:
                workspace.load_papers(self.ctx.config, run['set'], run['folder'], [paper])
        except models.ModelError as error:
            self.set_paper(rid, paper, status='failed', error=error.message, code=error.code, finished_at=self.ctx.clock())
            return
        except (StorageError, OSError) as error:
            self.set_paper(rid, paper, status='failed', error=f'Could not write the result: {getattr(error, "strerror", None) or error}',
                           code='storage_error', finished_at=self.ctx.clock())
            return
        except Exception:   # an unexpected failure ends this paper, never the run
            self.set_paper(rid, paper, status='failed', error='Unexpected failure while extracting this paper.', code='internal',
                           finished_at=self.ctx.clock())
            return
        self.set_paper(rid, paper, status='done', error=None, code=None, attempts=attempts, usd=answer.usd,
                       seconds=answer.seconds, input_tokens=answer.input_tokens, output_tokens=answer.output_tokens,
                       model=run['model'], finished_at=self.ctx.clock())

    def update_manifest(self, run, paper, answer):
        folder = self.folder(run)
        with self.lock(run['id']):
            try:
                manifest = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                manifest = self.manifest(run)
            manifest['papers'][paper] = {'extracted_at': self.ctx.clock(), 'input_tokens': answer.input_tokens,
                                         'output_tokens': answer.output_tokens, 'usd': answer.usd, 'seconds': answer.seconds}
            results.write_manifest(folder, manifest)

    def manifest(self, run):
        _content, meta = self.ctx.schema_version(run['schema_ref']['id'], run['schema_ref']['version'])
        return {'schema': 'value-review-run-manifest/1', 'run_id': run['id'], 'name': run['name'], 'set': run['set'],
                'schema_ref': run['schema_ref'], 'schema_name': meta['name'] if meta else None,
                'prompt_version': run['prompt_version'], 'system_prompt_version': run['system_prompt_version'],
                'model': run['model'], 'launched_at': run['launched_at'], 'finished_at': None, 'papers': {}}

    def done_worker(self, run, job):
        """The last worker of a run to stop settles its status: complete, paused or cancelled."""
        rid = run['id']
        with self.guard:
            job['live'] -= 1
            if job['live'] > 0:   # the last worker to stop settles the run
                return
        try:
            self.settle(rid, job)
        finally:
            with self.guard:   # only once the status is saved, so a run is never seen idle and still "running"
                if self.jobs.get(rid) is job:
                    self.jobs.pop(rid)

    def settle(self, rid, job):
        with self.ctx.lock, self.lock(rid):
            state = self.read_state(rid)
            if job['stop'] == 'cancel':
                for row in state['papers'].values():
                    if row.get('status') == 'queued':
                        row.update(status='no_results')
            if state['sessions'] and not state['sessions'][-1].get('ended_at'):
                state['sessions'][-1]['ended_at'] = self.ctx.clock()
            self.write_state(rid, state)
            current, _problem = self.ctx.runs.read(rid)
            if current is None:
                return
            queued = any(r.get('status') == 'queued' for r in state['papers'].values())
            status = 'paused' if job['stop'] == 'pause' or (queued and job['stop'] != 'cancel') else (
                'cancelled' if job['stop'] == 'cancel' else 'complete')
            current.update(status=status, finished_at=self.ctx.clock() if status in ('complete', 'cancelled') else None)
            self.ctx.runs.write(current)
            if status in ('complete', 'cancelled') and (self.folder(current) / 'run.json').is_file():
                manifest = json.loads((self.folder(current) / 'run.json').read_text(encoding='utf-8'))
                results.write_manifest(self.folder(current), {**manifest, 'name': current['name'], 'finished_at': current['finished_at']})

    def recover(self):
        """After a restart: running runs become paused; papers that were extracting go back to the queue (AC-X10)."""
        for rid in self.ctx.runs.ids():
            run, _problem = self.ctx.runs.read(rid)
            if not run or run['status'] != 'running':
                continue
            state = self.read_state(rid)
            for row in state['papers'].values():
                if row.get('status') == 'extracting':
                    row['status'] = 'queued'
            for s in state['sessions']:
                s['ended_at'] = s.get('ended_at') or s['started_at']
            self.write_state(rid, state)
            self.ctx.runs.write({**run, 'status': 'paused'})

    def busy(self, rid):
        with self.guard:
            job = self.jobs.get(rid)
            return bool(job and job['live'] > 0)


def install_launch(app, ctx, api):
    launcher = Launcher(ctx)
    ctx.launcher = launcher
    launcher.recover()

    def save(run):
        try:
            ctx.runs.write(run)
        except StorageError as error:
            raise ApiError(500, 'storage_error', str(error)) from None

    @app.get(f'{api}/runs/{{rid}}/papers')
    def run_papers(rid: str):
        return {'papers': launcher.papers(ctx.read_run(rid))}

    @app.get(f'{api}/runs/{{rid}}/estimate')
    def run_estimate(rid: str, papers: str | None = Query(default=None, max_length=50000)):
        run = ctx.read_run(rid)
        chosen = [p for p in papers.split(',') if p] if papers else None
        return launcher.estimate(run, launcher.to_extract(run, chosen))

    def queue(run, papers):
        with launcher.lock(run['id']):
            state = launcher.read_state(run['id'])
            for p in papers:
                state['papers'][p] = {**(state['papers'].get(p) or {}), 'status': 'queued', 'error': None, 'code': None}
            launcher.write_state(run['id'], state)

    @app.post(f'{api}/runs/{{rid}}/launch', status_code=202)
    def launch(rid: str, payload: LaunchIn):
        with ctx.lock:
            run = ctx.read_run(rid)
            if run['status'] in ('running', 'paused') or launcher.busy(rid):
                raise ApiError(409, 'run_running', 'This run is running or paused: resume or cancel it first.')
            work.require_ready(ctx, run)
            papers = launcher.to_extract(run, payload.papers)
            if not papers:
                raise ApiError(422, 'nothing_to_extract', 'Every chosen paper already has results or a Review version.')
            if run['status'] == 'draft':   # the first launch fixes the prompt and System prompt versions (BR-X01, BR-X06)
                n, _text = work.current_prompt(ctx, run)
                from ...storage.prompts import PromptStore
                version, _problem = PromptStore(ctx.runs.run_dir(rid)).read_version(n)
                run.update(prompt_version=n, system_prompt_version=version['system_prompt_version'] if version else None,
                           launched_at=ctx.clock())
                launcher.folder(run).mkdir(parents=True, exist_ok=True)
                if not (launcher.folder(run) / 'run.json').is_file():
                    results.write_manifest(launcher.folder(run), launcher.manifest(run))
            run.update(status='running', finished_at=None)
            save(run)
            queue(run, papers)
        launcher.start(run)
        return {'run': ctx.view(ctx.read_run(rid)), 'queued': papers}

    @app.post(f'{api}/runs/{{rid}}/pause')
    def pause(rid: str):
        run = ctx.read_run(rid)
        with launcher.guard:
            job = launcher.jobs.get(rid)
        if run['status'] != 'running' or not job:
            raise ApiError(409, 'not_running', 'This run is not running.')
        job['stop'] = 'pause'   # the papers being extracted finish; no new one starts
        return ctx.view(ctx.read_run(rid))

    @app.post(f'{api}/runs/{{rid}}/resume', status_code=202)
    def resume(rid: str):
        with ctx.lock:
            run = ctx.read_run(rid)
            if run['status'] != 'paused':
                raise ApiError(409, 'not_paused', 'This run is not paused.')
            if launcher.busy(rid):
                raise ApiError(409, 'run_running', 'The run is still finishing its current papers. Try again in a moment.')
            work.require_ready(ctx, run)
            save({**run, 'status': 'running'})
        launcher.start(ctx.read_run(rid))
        return ctx.view(ctx.read_run(rid))

    @app.post(f'{api}/runs/{{rid}}/cancel')
    def cancel(rid: str):
        with ctx.lock:
            run = ctx.read_run(rid)
            if run['status'] not in ('running', 'paused'):
                raise ApiError(409, 'not_running', 'This run is not running or paused.')
            with launcher.guard:
                job = launcher.jobs.get(rid)
            if job:
                job['stop'] = 'cancel'   # the papers being extracted finish and are kept
                return ctx.view(run)
            # paused with no worker: settle now
            launcher.done_worker(run, {'stop': 'cancel', 'threads': [], 'live': 1})
        return ctx.view(ctx.read_run(rid))

    @app.post(f'{api}/runs/{{rid}}/papers/{{paper}}/retry', status_code=202)
    def retry(rid: str, paper: str):
        with ctx.lock:
            run = ctx.read_run(rid)
            row = next((r for r in launcher.papers(run) if r['paper'] == paper), None)
            if row is None:
                raise ApiError(404, 'paper_not_found', f'Paper {paper} is not in the paper set')
            if row['status'] != 'failed':
                raise ApiError(409, 'not_failed', 'Only a failed paper can be retried.')
            if run['status'] == 'paused':
                raise ApiError(409, 'run_paused', 'Resume the run to retry this paper.')
            work.require_ready(ctx, run)
            queue(run, [paper])
            if run['status'] != 'running':
                save({**run, 'status': 'running', 'finished_at': None})
        launcher.start(ctx.read_run(rid))
        return {'run': ctx.view(ctx.read_run(rid)), 'queued': [paper]}

    def wait_idle(timeout=10):
        """Tests: wait until no run has a live worker."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with launcher.guard:
                if not launcher.jobs:
                    return True
            time.sleep(0.02)
        return False

    launcher.wait_idle = wait_idle
    return launcher
