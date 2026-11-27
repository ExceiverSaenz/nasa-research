"""Normalize, the pure part (90-normalize-specification.md, BR-N02, BR-N03, BR-N05, BR-N07, BR-N09; ADR-033).

What Normalize reads from Review, the formats and patterns found in the reviewed values, the first draft of a rule,
whether a normalized value is Outdated, and the rows of the final dataset. Nothing here reads or writes a file: the
service passes the Review versions, the schema's fields and the stored rules and values. Review versions are only read.
"""
import re

DIGIT = re.compile(r'\d')
NUM = r'[-+−]?\d+(?:[.,]\d+)?(?:\s*[×x]\s*10[⁻\-]?[\d⁰¹²³⁴⁵⁶⁷⁸⁹]+)?'
PM = re.compile(r'±|\+/-|\+-')
RANGE = re.compile(rf'{NUM}\s*(?:[–—~]|-(?=\s*\d)|\bto\b)\s*{NUM}')
INEQ = re.compile(r'^\s*(?:[<>≤≥≈~]|&lt;|&gt;|less than|more than|greater than|above|below|up to|at least|at most)', re.I)
WORDS = re.compile(r'\b(?:about|approx\w*|around|close to|nearly|roughly|room temperature|RT)\b', re.I)
BAL = re.compile(r'^\s*bal(?:ance)?\.?\s*$', re.I)

BATCH = 50   # values of one feature per model call (ADR-034)
STATUSES = ('to_validate', 'accepted', 'corrected', 'rejected', 'unsure')
VALIDATED = ('accepted', 'corrected')
NUMBER_FIELDS = ['Value', 'Uncertainty (±)', 'Lower and upper bound', 'Qualifier (<, >, ≈)']

# key -> (name, quick actions); the first action is the one "Draft the rule" writes
PATTERNS = {
    'pm': ('Value ± uncertainty', ['Split into value and uncertainty', 'Keep the value only']),
    'unit': ('Another unit', ['Convert to {unit} and say so', 'Flag for me, do not convert']),
    'range': ('Range', ['Keep lower and upper bound', 'Use the midpoint, flag it', 'Flag for me']),
    'ineq': ('Inequality', ['Keep value with qualifier', 'Flag for me']),
    'words': ('Value in words', ['Normalize with ≈ and flag it', 'Leave empty and flag it']),
    'bal': ('“bal.” (the base element)', ['Calculate the remainder, flag it', 'Keep the text “bal.”']),
    'plain': ('Plain value', ['Copy the number', 'Flag for me']),
    'allowed': ('Already an allowed value', ['Keep it', 'Flag for me']),
    'other': ('Not one of the allowed values', ['Map it to the closest allowed value and flag it', 'Flag for me']),
}
ANYTHING = ('Anything else', ['Flag it for me and leave the value as reviewed', 'Leave the value as reviewed'])


def value_id(paper, observation_id):
    """Stable id of a reviewed value across versions of its paper (OP-N08)."""
    return f'{paper}~{observation_id}'


def reviewed_values(versions):
    """BR-N02: the values of each paper's latest submitted version, without rejected or empty ones.

    ``versions``: {paper: latest version dict, or None}. Returns [{id, paper, observation_id, version_n, feature_id,
    record_ids, record_labels, value, unit}] in paper order, then the version's order."""
    out = []
    for paper, version in versions.items():
        if not version:
            continue
        for v in version['values']:
            text = (v.get('value') or '').strip()
            if v['status'] == 'rejected' or not text:
                continue
            out.append({'id': value_id(paper, v['observation_id']), 'paper': paper, 'observation_id': v['observation_id'],
                        'version_n': version['n'], 'feature_id': v['feature_id'], 'record_ids': list(v['record_ids']),
                        'record_labels': list(v['record_labels']), 'value': text, 'unit': (v.get('unit') or '').strip()})
    return out


def _same_unit(a, b):
    squash = lambda u: re.sub(r'[\s.]', '', u or '').casefold().replace('µ', 'u').replace('μ', 'u')   # noqa: E731
    return squash(a) == squash(b)


def pattern_of(field, value, unit):
    """The pattern key of one reviewed value (BR-N05). Worked out without a model."""
    text = value.strip()
    if field['type'] == 'category':
        allowed = {a.strip().casefold() for a in field['allowed']}
        return 'allowed' if text.casefold() in allowed else 'other'
    if BAL.match(text):
        return 'bal'
    if not DIGIT.search(text) or WORDS.search(text):
        return 'words'
    if PM.search(text):
        return 'pm'
    if RANGE.search(text):
        return 'range'
    if INEQ.match(text):
        return 'ineq'
    if field['unit'] and unit and not _same_unit(unit, field['unit']):
        return 'unit'
    return 'plain'


def shown(value, unit):
    return f'{value} {unit}'.strip() if unit and unit not in value else value


def formats(field, values):
    """Formats found (BR-N05): [{name, n, example}], most frequent first. Numbers: one entry per unit, and one per text
    without digits; text and categories: one entry per distinct value."""
    groups = {}
    for v in values:
        if field['type'] in ('number', 'calculated') and DIGIT.search(v['value']):
            name = v['unit'] or 'no unit'
        elif field['type'] in ('number', 'calculated'):
            name = f'“{v["value"]}”'
        else:
            name = v['value']
        key = name.casefold()
        if key not in groups:
            groups[key] = {'name': name, 'n': 0, 'example': shown(v['value'], v['unit'])}
        groups[key]['n'] += 1
    return sorted(groups.values(), key=lambda g: (-g['n'], g['name'].casefold()))


def patterns(field, values):
    """Patterns found (BR-N05): [{key, name, n, example, options}], most frequent first; none for text fields."""
    if field['type'] not in ('number', 'category'):
        return []
    found = {}
    for v in values:
        key = pattern_of(field, v['value'], v['unit'])
        if key not in found:
            name, options = PATTERNS[key]
            found[key] = {'key': key, 'name': name, 'n': 0, 'example': shown(v['value'], v['unit']),
                          'options': [o.format(unit=field['unit'] or 'the target unit') for o in options]}
        found[key]['n'] += 1
    return sorted(found.values(), key=lambda p: -p['n'])


def draft_rule(field, found):
    """The first rule "Draft the rule" writes (ADR-036): one case per pattern found, with a real example, plus
    "Anything else". Not saved."""
    target = f' to {field["unit"]}' if field['type'] == 'number' and field['unit'] else ''
    if field['type'] == 'category' and field['allowed']:
        target = ' to one of its allowed values (' + ', '.join(field['allowed']) + ')'
    lines = [f'Normalize {field["label"]}{target}. Keep the value as the paper reports it.']
    for p in found:
        example = f' (e.g. {p["example"]})' if p['example'] else ''
        lines.append(f'- {p["name"]}{example}: {p["options"][0].rstrip(".")}.')
    lines.append(f'- {ANYTHING[0]}: {ANYTHING[1][0].lower()}.')
    return '\n'.join(lines)


def as_reviewed(field, values):
    """The field as Normalize treats it (BR-N03): a text field whose reviewed values mostly hold a number (60 % or more,
    as in the seeded "Tensile properties" v1, where every field is text) is treated as a number without a target unit.
    ``schema_type`` keeps the schema's own type."""
    out = {**field, 'schema_type': field['type']}
    if field['type'] == 'text' and values and sum(1 for v in values if DIGIT.search(v['value'])) >= 0.6 * len(values):
        out['type'] = 'number'
    return out


def default_decision(field):
    """BR-N03: what a feature is before any rule is saved."""
    if field['type'] == 'calculated':
        return 'calc'
    return 'keep' if field['type'] == 'text' else 'none'


def default_output_fields(field):
    if field['type'] == 'number':
        return [{'label': label, 'on': True} for label in NUMBER_FIELDS]
    return [{'label': 'Value', 'on': True}]


def is_outdated(stored, current_versions, rule_n):
    """BR-N07: a normalized value is Outdated when its paper has a newer version, or its rule a newer version, than
    the ones it was made from. ``current_versions``: {paper: latest version number}."""
    return stored['version_n'] != current_versions.get(stored['paper']) or stored['rule_version'] != rule_n


def batches(items, size=BATCH):
    return [items[i:i + size] for i in range(0, len(items), size)] or []


def answer_by_id(batch, answer):
    """The model's results for one batch, one per value (BR-N06). A value the answer leaves out, or an id it invents,
    never fills anything: the left-out value comes back flagged and not normalized."""
    wanted = {v['id'] for v in batch}
    got = {}
    for r in answer.get('results') or []:
        if r.get('id') in wanted and r['id'] not in got:
            got[r['id']] = r
    out = {}
    for v in batch:
        r = got.get(v['id'])
        if r is None:
            out[v['id']] = {'case': 'Not normalized', 'fields': [], 'unit': None, 'display': v['value'], 'flag': True,
                            'note': 'The model did not return this value. It was left as reviewed.'}
        else:
            out[v['id']] = {'case': (r.get('case') or 'Anything else').strip()[:120] or 'Anything else',
                            'fields': [{'name': str(f.get('name', ''))[:80], 'value': None if f.get('value') is None else str(f['value'])[:200]}
                                       for f in (r.get('fields') or [])][:12],
                            'unit': r.get('unit'), 'display': str(r.get('display') or '')[:300], 'flag': bool(r.get('flag')),
                            'note': str(r.get('note') or '')[:1000]}
    return out
