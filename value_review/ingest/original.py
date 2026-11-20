"""Build the immutable original of one paper from the LLM result and its PDF (BR-01, ADR-004).

The original is UI-ready: records, columns, observations with their evidence boxes and pages, and
the needs-a-check rule applied once. It is deterministic: the same inputs give the same bytes, so it
carries no timestamp and no absolute path. Sources are read only.
"""
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium

from ..domain.checks import action_codes, info_codes, needs_check
from ..storage import atomic_write_bytes
from . import features

SCHEMA = 'value-review-original/1'


class IngestError(Exception):
    """The source cannot be ingested (missing, unreadable, or not the expected format)."""


class OriginalChanged(IngestError):
    """An original exists with different content; originals are never rewritten (BR-01)."""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def page_sizes(pdf_path):
    """Displayed size of each page in points. pdfium's page size already applies the page rotation."""
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        out = []
        for i in range(len(doc)):
            page = doc[i]
            try:
                w, h = page.get_size()
            finally:
                page.close()
            out.append({'number': i + 1, 'width_pt': round(w, 2), 'height_pt': round(h, 2)})
        return out
    finally:
        doc.close()


def _bbox(value):
    if value is None:
        return None
    return [round(float(x), 4) for x in value]


def build_original(result_path, pdf_path):
    """Return the original as a dict. Raises IngestError when a source is missing or malformed."""
    result_path, pdf_path = Path(result_path), Path(pdf_path)
    for p in (result_path, pdf_path):
        if not p.is_file():
            raise IngestError(f'Missing source file: {p.name}')
    try:
        raw = result_path.read_bytes()
        data = json.loads(raw.decode('utf-8'))
        paper = data['paper']
        pid = str(paper['paper_id'])
        observations = data['observations']
        records = data['records']
        regions = {r['region_id']: r for r in data['regions']}
        evidence = {e['evidence_id']: e for e in data['evidence']}
    except (ValueError, KeyError, TypeError) as error:
        raise IngestError(f'{result_path.name} is not an extraction result: {error}') from error

    issues = []
    pdf_sha = sha256_file(pdf_path)
    if paper.get('sha256') and paper['sha256'] != pdf_sha:
        issues.append({'code': 'pdf_hash_mismatch', 'ref': pdf_path.name})
    pages = page_sizes(pdf_path)
    page_count = len(pages)

    record_ids = {r['record_id'] for r in records}
    out_obs, used_features = [], set()
    for o in observations:
        oid = o['observation_id']
        ev_out = []
        for eid in o.get('evidence_ids') or []:
            e = evidence.get(eid)
            if e is None:
                issues.append({'code': 'unknown_evidence', 'ref': f'{oid}:{eid}'})
                continue
            region = regions.get(e.get('region_id'))
            if region is None:
                issues.append({'code': 'unknown_region', 'ref': f'{eid}:{e.get("region_id")}'})
                continue
            page = region.get('page_number')
            if not isinstance(page, int) or not 1 <= page <= page_count:
                issues.append({'code': 'page_out_of_range', 'ref': f'{eid}:{page}'})
                continue
            ev_out.append({
                'evidence_id': eid, 'page': page, 'bbox': _bbox(e.get('bbox')),
                'role': e.get('role'), 'text': e.get('literal_text'),
                'location_quality': e.get('location_quality'),
                'region_id': region['region_id'], 'region_kind': region.get('kind'),
                'region_label': region.get('source_label'),
            })
        for rid in (o.get('record_ids') or []) + (o.get('candidate_record_ids') or []):
            if rid not in record_ids:
                issues.append({'code': 'unknown_record', 'ref': f'{oid}:{rid}'})
        flags = list(o.get('flags') or [])
        src, asg = o.get('source_status'), o.get('assignment_status')
        used_features.add(o['feature_id'])
        out_obs.append({
            'observation_id': oid,
            'feature_id': o['feature_id'],
            'record_ids': list(o.get('record_ids') or []),
            'candidate_record_ids': list(o.get('candidate_record_ids') or []),
            'assignment_status': asg,
            'scope': o.get('scope'),
            'source_status': src,
            'value': o.get('value_as_reported'),
            'unit': o.get('unit_as_reported'),
            'flags': flags,
            'derivation': o.get('derivation'),
            'notes': o.get('notes') or '',
            'needs_check': needs_check(flags, src, asg),
            'action': action_codes(flags, src, asg),
            'info': info_codes(flags, src),
            'evidence': ev_out,
        })

    completion = data.get('completion') or {}
    return {
        'schema': SCHEMA,
        'paper': pid,
        'source': {
            'run_id': data.get('run_id'),
            'mode': data.get('mode'),
            'result_file': result_path.name,
            'result_sha256': hashlib.sha256(raw).hexdigest(),
            'pdf_file': pdf_path.name,
            'pdf_sha256': pdf_sha,
        },
        'document': {
            'title': paper.get('title') or '',
            'page_count': page_count,
            'completion': {
                'status': completion.get('status'),
                'pages_unreviewed': list(completion.get('pages_unreviewed') or []),
                'summary': completion.get('summary') or '',
            },
        },
        'pages': pages,
        'features': [{'feature_id': f, 'label': features.label(f)} for f in sorted(used_features, key=features.sort_key)],
        'records': [{
            'record_id': r['record_id'],
            'label': r.get('source_label') or r['record_id'],
            'summary': r.get('condition_summary') or '',
            'kind': r.get('record_kind'),
            'statistic': r.get('statistic_as_reported'),
            'replicate_count': r.get('replicate_count'),
            'notes': r.get('notes') or '',
        } for r in records],
        'observations': out_obs,
        'counts': {
            'records': len(records),
            'values': len(out_obs),
            'needs_check': sum(1 for o in out_obs if o['needs_check']),
        },
        'issues': issues,
    }


def dumps(original):
    return (json.dumps(original, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


def write_original(original, out_dir):
    """Write ``<out_dir>/<paper>.json`` once. Returns 'written' or 'unchanged'.

    Raises OriginalChanged when a file with different content already exists: originals are never
    rewritten (BR-01); a new source needs its own review line (OQ-02)."""
    path = Path(out_dir) / f"{original['paper']}.json"
    data = dumps(original)
    if path.exists():
        if path.read_bytes() == data:
            return 'unchanged'
        raise OriginalChanged(f'Original for paper {original["paper"]} already exists with different content')
    atomic_write_bytes(path, data)
    return 'written'
