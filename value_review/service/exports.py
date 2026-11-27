"""Exports of a version (OP-09, ADR-003): JSON in the LLM output's terms plus the review, and a flat CSV.

Both are built from the version's stored ``values`` and ``state`` with the paper's original, so an export
never depends on the current working copy. Values are written exactly as stored (BR-05), with one exception in
the CSV only: a cell a spreadsheet would run as a formula gets a leading apostrophe (see ``cell``).
"""
import csv
import io
import json
import re
import zipfile

from ..domain.review_schema import label as field_label

CSV_COLUMNS = ['paper', 'version', 'observation_id', 'record', 'record_id', 'column', 'feature_id', 'value', 'unit',
               'original_value', 'original_unit', 'status', 'note', 'by', 'at', 'origin', 'needs_check']
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
PLAIN_NUMBER = re.compile(r'[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?')


def cell(value):
    """A CSV cell that a spreadsheet will not run as a formula (CSV injection). Text starting with =, +, -, @, tab
    or carriage return gets a leading apostrophe, which Excel shows as text; a plain number such as -5 or +1.5e3
    is left as it is. Everything else is unchanged; the JSON export is never escaped."""
    text = '' if value is None else str(value)
    if text.startswith(FORMULA_START) and not PLAIN_NUMBER.fullmatch(text):
        return "'" + text
    return text


def export_json(original, version):
    state, rows = version['state'], {r['observation_id']: r for r in version['values']}
    edits = state['record_edits']
    records = []
    for r in original['records']:
        e = edits.get(r['record_id'])
        records.append({'record_id': r['record_id'], 'source_label': e['label'] if e else r['label'],
                        'condition_summary': e['summary'] if e else r['summary'], 'origin': 'model',
                        'model_label': r['label'] if e else None, 'model_condition_summary': r['summary'] if e else None,
                        'record_kind': r['kind'], 'statistic_as_reported': r['statistic'],
                        'replicate_count': r['replicate_count'], 'notes': r['notes']})
    for r in state['added_records']:
        records.append({'record_id': r['record_id'], 'source_label': r['label'], 'condition_summary': r['summary'],
                        'origin': 'reviewer', 'model_label': None, 'model_condition_summary': None, 'by': r['by'], 'at': r['at']})

    # One evidence entry per observation and box: removals and redraws are per value (contract, OP-09).
    evidence = []
    for o in original['observations']:
        oid = o['observation_id']
        b = state['boxes'].get(oid) or {'removed': [], 'redrawn': {}, 'added': []}
        for e in o['evidence']:
            redraw = b['redrawn'].get(e['evidence_id'])
            evidence.append({'evidence_id': e['evidence_id'], 'observation_ids': [oid], 'origin': 'model',
                             'page_number': redraw['page'] if redraw else e['page'],
                             'bbox': redraw['bbox'] if redraw else e['bbox'],
                             'model_bbox': e['bbox'] if redraw else None,
                             'removed': e['evidence_id'] in b['removed'],
                             'role': e['role'], 'literal_text': e['text'], 'location_quality': e['location_quality']})
    for oid, b in state['boxes'].items():
        for i, box in enumerate(b['added']):
            evidence.append({'evidence_id': f'{oid}#added{i + 1}', 'observation_ids': [oid], 'origin': 'reviewer',
                             'page_number': box['page'], 'bbox': box['bbox'], 'model_bbox': None, 'removed': False,
                             'by': box['by'], 'at': box['at']})

    def review(row):
        return {'status': row['status'], 'value': row['value'], 'unit': row['unit'], 'feature_id': row['feature_id'],
                'record_ids': row['record_ids'], 'note': row['note'], 'by': row['by'], 'at': row['at'],
                'origin': row['origin'], 'needs_check': row['needs_check']}

    observations = []
    for o in original['observations']:
        observations.append({'observation_id': o['observation_id'], 'feature_id': o['feature_id'],
                             'record_ids': o['record_ids'], 'candidate_record_ids': o['candidate_record_ids'],
                             'assignment_status': o['assignment_status'], 'scope': o['scope'],
                             'source_status': o['source_status'], 'value_as_reported': o['value'],
                             'unit_as_reported': o['unit'], 'evidence_ids': [e['evidence_id'] for e in o['evidence']],
                             'derivation': o['derivation'], 'flags': o['flags'], 'notes': o['notes'],
                             'review': review(rows[o['observation_id']])})
    for v in state['added_values']:
        observations.append({'observation_id': v['observation_id'], 'feature_id': v['feature_id'],
                             'record_ids': v['record_ids'], 'value_as_reported': None, 'unit_as_reported': None,
                             'review': review(rows[v['observation_id']])})
    return {'schema': 'value-review-export/1', 'paper': version['paper'], 'version': version['n'],
            'at': version['at'], 'by': version['by'], 'source': version['source'], 'schema_ref': version.get('schema_ref'),
            'records': records, 'evidence': evidence, 'observations': observations}


DELIMITERS = {',': ',', ';': ';', 'tab': '\t'}


def _text(text, encoding):
    """The CSV bytes: UTF-8, with a BOM unless ``encoding`` is "utf8" (OP-T03)."""
    return (text if encoding == 'utf8' else '﻿' + text).encode('utf-8')


def export_csv(version, delimiter=',', encoding='utf8bom', labels=None):
    """RFC 4180 quoting with the stored separator, one row per value in the version's order; UTF-8 with a BOM by
    default (OP-T03 of 42-settings-interface-contract.md). ``labels`` are the field names of the version's schema
    (BR-R07); a field id they do not hold keeps the old guide's label."""
    labels = labels or {}
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=DELIMITERS[delimiter], lineterminator='\r\n')
    writer.writerow(CSV_COLUMNS)
    for r in version['values']:
        writer.writerow([cell(x) for x in (
            version['paper'], version['n'], r['observation_id'], '; '.join(r['record_labels']),
            '; '.join(r['record_ids']), field_label(labels, r['feature_id']), r['feature_id'],
            r['value'], r['unit'], r['original_value'], r['original_unit'],
            r['status'], r['note'], r['by'], r['at'], r['origin'], 'yes' if r['needs_check'] else 'no')])
    return _text(buf.getvalue(), encoding)


def latest_zip(items, delimiter=',', encoding='utf8bom', labels_of=None):
    """``items``: [(original, version)] for papers with a version. Latest JSON and CSV of each, plus summary.csv;
    every CSV uses the stored separator and encoding. ``labels_of(version)`` gives that version's field names."""
    buf = io.BytesIO()
    summary = io.StringIO()
    writer = csv.writer(summary, delimiter=DELIMITERS[delimiter], lineterminator='\r\n')
    writer.writerow(['paper', 'version', 'at', 'by', 'total', 'pending', 'accepted', 'corrected', 'rejected', 'unsure',
                     'added_values', 'added_records', 'edited_records'])
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for original, version in items:
            stem = f"paper-{version['paper']}-v{version['n']}"
            z.writestr(f'{stem}.json', json.dumps(export_json(original, version), ensure_ascii=False, indent=1))
            z.writestr(f'{stem}.csv', export_csv(version, delimiter, encoding, labels_of(version) if labels_of else None))
            c = version['counts']
            writer.writerow([cell(x) for x in (
                version['paper'], version['n'], version['at'], version['by'], c['total'], c['pending'],
                c['accepted'], c['corrected'], c['rejected'], c['unsure'], c['added_values'],
                c['added_records'], c['edited_records'])])
        z.writestr('summary.csv', _text(summary.getvalue(), encoding))
    return buf.getvalue()
