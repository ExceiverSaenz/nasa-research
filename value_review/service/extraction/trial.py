"""Testing a run's prompt on 1 to 3 papers, OP-X05 (BR-X03): the papers are extracted as a launch would, the values
are shown with their page, and nothing is written (the cost still counts for the key). Tests live in memory for an hour.
Also the page images of a set's PDFs, so a value's page can be checked before any paper is loaded into Review."""
import io
import secrets as _random
import threading
import time
from pathlib import Path

import pypdfium2 as pdfium
from fastapi import Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ..errors import ApiError
from ..library import WIDTH_DEFAULT, snap_width
from ..workspace import PAPERS, _safe as safe_name
from . import models, results, work

KEEP_SECONDS = 3600


class TestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    papers: list[str] = Field(min_length=1, max_length=3)


def values_of(answer, result, fields):
    """The test's values as Test shows them: field name, record labels, value, unit, page and quote."""
    labels = {r['record_id']: r['source_label'] for r in result['records']}
    regions = {g['region_id']: g for g in result['regions']}
    evidence = {e['evidence_id']: e for e in result['evidence']}
    out = []
    for o in result['observations']:
        ev = evidence.get(o['evidence_ids'][0]) if o['evidence_ids'] else None
        region = regions.get(ev['region_id']) if ev else None
        out.append({'field_id': o['feature_id'], 'field': fields.get(o['feature_id'], o['feature_id']),
                    'records': [labels[r] for r in o['record_ids'] if r in labels], 'value': o['value_as_reported'],
                    'unit': o['unit_as_reported'] or '', 'page': region['page_number'] if region else None,
                    'quote': ev['literal_text'] if ev else '', 'found': bool(ev and ev['bbox']), 'flags': o['flags']})
    return out


def install_trial(app, ctx, api):
    tests, lock = {}, threading.Lock()

    def forget_old():
        now = time.monotonic()
        with lock:
            for tid in [t for t, job in tests.items() if now - job['_started'] > KEEP_SECONDS]:
                tests.pop(tid, None)

    def fields_of(run):
        content, _meta = ctx.schema_version(run['schema_ref']['id'], run['schema_ref']['version'])
        return {f['field_id']: f['name'] for g in (content['content']['groups'] if content else []) for f in g['fields']}

    def run_test(job, run, prompt):
        fields = fields_of(run)
        for item in job['papers']:
            item['status'] = 'extracting'
            try:
                answer, result, attempts = work.extract_one(ctx, run, prompt, item['paper'])
            except models.ModelError as error:
                item.update(status='failed', error=error.message)
                continue
            except Exception:   # an unexpected failure ends this paper, not the test
                item.update(status='failed', error='Unexpected failure while extracting this paper.')
                continue
            item.update(status='done', values=values_of(answer, result, fields), attempts=attempts,
                        usd=answer.usd, seconds=answer.seconds, completion=answer.data['completion'])
            if answer.usd is not None:
                job['usd'] = round((job['usd'] or 0) + answer.usd, 6)
        job['status'] = 'done'

    def view(job):
        return {k: v for k, v in job.items() if not k.startswith('_')}

    @app.post(f'{api}/runs/{{rid}}/tests', status_code=202)
    def start_test(rid: str, payload: TestIn):
        run = ctx.read_run(rid)
        work.require_ready(ctx, run)
        available = set(work.set_papers(ctx, run))
        papers = list(dict.fromkeys(payload.papers))
        missing = [p for p in papers if p not in available]
        if missing:
            raise ApiError(404, 'paper_not_found', f'Not in the paper set: {", ".join(missing)}')
        _n, prompt = work.current_prompt(ctx, run)
        forget_old()
        job = {'id': 't_' + _random.token_hex(4), 'run_id': rid, 'status': 'running', 'usd': None,
               'started_at': ctx.clock(), '_started': time.monotonic(),
               'papers': [{'paper': p, 'status': 'queued', 'error': None, 'values': []} for p in papers]}
        with lock:
            tests[job['id']] = job
        threading.Thread(target=run_test, args=(job, run, prompt), daemon=True, name=f'test-{job["id"]}').start()
        return view(job)

    @app.get(f'{api}/tests/{{tid}}')
    def get_test(tid: str):
        forget_old()
        with lock:
            job = tests.get(tid)
        if job is None:
            raise ApiError(404, 'test_not_found', 'No such test (tests are kept for an hour and never saved)')
        return view(job)

    @app.get(f'{api}/sets/{{set_name}}/pdfs/{{paper}}/pages/{{page}}/image')
    def set_page_image(set_name: str, paper: str, page: int, w: int = Query(WIDTH_DEFAULT, ge=400, le=2400)):
        if ctx.config.workspace is None or not safe_name(set_name) or not safe_name(paper):
            raise ApiError(404, 'paper_not_found', 'No such PDF')
        pdf = Path(ctx.config.workspace) / PAPERS / set_name / f'{paper}.pdf'
        if not pdf.is_file():
            raise ApiError(404, 'paper_not_found', 'No such PDF')
        with results.PDFIUM:
            doc = pdfium.PdfDocument(str(pdf))
            try:
                if not 1 <= page <= len(doc):
                    raise ApiError(404, 'page_not_found', f'The PDF has no page {page}')
                pg = doc[page - 1]
                try:
                    image = pg.render(scale=snap_width(w) / pg.get_width()).to_pil()
                finally:
                    pg.close()
            finally:
                doc.close()
        buf = io.BytesIO()
        image.convert('RGB').save(buf, format='PNG', compress_level=3)
        return Response(buf.getvalue(), media_type='image/png', headers={'Cache-Control': 'no-store'})
