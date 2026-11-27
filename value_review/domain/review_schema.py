"""The fields Review shows and checks, from the schema version an extraction is bound to (80-review-schema-specification.md,
BR-R01 to BR-R04, BR-R06; ADR-030 to ADR-032).

Pure functions: the service resolves the binding and passes the schema content (or None) and the original. Nothing
here writes a file, and the original is never changed (BR-01): the checks are worked out each time from the original
and the schema version, so the same two inputs always give the same answer (BR-R05).
"""
import re

from ..ingest import features

DIGIT = re.compile(r'\d')
SPLIT = re.compile(r'\s*[;,]\s*')
# Codes shown as "Check this" for a model value (BR-R04), beside the original's own (domain/checks.py).
NOT_IN_SCHEMA, NOT_ALLOWED, NOT_A_NUMBER, QUOTE_NOT_FOUND = 'field:not_in_schema', 'field:not_allowed', 'field:not_a_number', 'evidence:quote_not_found'
API_PDF = 'api_pdf'   # results written by Extraction (service/extraction/results.py)


def fields_of(content):
    """One entry per field of a schema version, in group and field order (BR-R02)."""
    out = []
    for g in content['groups']:
        for f in g['fields']:
            out.append({'field_id': f['field_id'], 'label': f['name'], 'group_id': g['group_id'], 'group': g['name'],
                        'type': f['type'], 'unit': f['unit'], 'allowed': list(f['allowed']), 'multiple': f['multiple'],
                        'description': f['description'], 'family': f['family'], 'calculated': f['type'] == 'calculated'})
    return out


def fallback_fields(original):
    """The original's own columns, when the bound schema version cannot be read (BR-R09): text fields, no group."""
    return [{'field_id': f['feature_id'], 'label': f['label'], 'group_id': None, 'group': None, 'type': 'text', 'unit': '',
             'allowed': [], 'multiple': False, 'description': '', 'family': None, 'calculated': False}
            for f in original['features']]


def targets(fields):
    """Field ids a value may be moved to or added in (BR-R03): every field that is not calculated."""
    return {f['field_id'] for f in fields if not f['calculated']}


def labels(fields):
    return {f['field_id']: f['label'] for f in fields}


def label(field_labels, feature_id):
    """The schema's name for a field id, else the old guide's label (BR-R07)."""
    return field_labels.get(feature_id) or features.label(feature_id)


def fit(field, value):
    """Why ``value`` does not fit ``field``: [] or ['not_allowed'] / ['not_a_number'] (BR-R06). Values are never parsed
    into numbers (BR-05): a number field only asks for a digit, so `710 ± 26`, `10⁻³` and `< 0.01` all fit."""
    text = (value or '').strip()
    if field is None or not text:
        return []
    if field['type'] == 'number' and not DIGIT.search(text):
        return ['not_a_number']
    if field['type'] == 'category' and field['allowed']:
        allowed = {a.strip().casefold() for a in field['allowed']}
        parts = [p for p in SPLIT.split(text) if p] if field['multiple'] else [text]
        if any(p.casefold() not in allowed for p in parts):
            return ['not_allowed']
    return []


def model_checks(original, fields, bound=True):
    """{observation_id: [codes]} for the model's values that need a check because of the schema or the evidence
    (BR-R04). ``bound`` is False when the schema could not be read: then only the evidence rule applies."""
    by_id = {f['field_id']: f for f in fields}
    api = (original.get('source') or {}).get('mode') == API_PDF
    out = {}
    for o in original['observations']:
        codes = []
        if api and not any(e.get('bbox') for e in o['evidence']):
            codes.append(QUOTE_NOT_FOUND)   # Extraction could not find the quote in the PDF (no box)
        if bound:
            field = by_id.get(o['feature_id'])
            if field is None:
                codes.append(NOT_IN_SCHEMA)
            else:
                codes += ['field:' + c for c in fit(field, o['value'])]
        if codes:
            out[o['observation_id']] = codes
    return out


def needs_check_count(original, checks):
    """Values of the original that need a check: its own (BR-06) or one from ``model_checks``."""
    return sum(1 for o in original['observations'] if o['needs_check'] or o['observation_id'] in checks)
