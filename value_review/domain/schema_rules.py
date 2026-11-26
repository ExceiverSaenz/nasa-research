"""Business rules of a schema's content (BR-S02 to BR-S04), checked when a version is saved (OP-S05).

The shape is checked first by schema-content.schema.json; these are the rules JSON Schema cannot express. Each problem
is ``{ref, rule}`` with ``ref`` a JSON pointer into the content, the same shape as ``rules.check_state``.
"""
import re

ID = re.compile(r'[a-z][a-z0-9_]{0,63}')
NAME_MAX = 120


def same_name(name):
    """Names compare ignoring case and repeated spaces (BR-S03)."""
    return ' '.join(name.split()).casefold()


def check_name(name, ref):
    """Problems of one name: empty, or longer than the limit."""
    text = name.strip()
    if not text:
        return [{'ref': ref, 'rule': 'empty_name'}]
    if len(text) > NAME_MAX:
        return [{'ref': ref, 'rule': 'too_long'}]
    return []


def check_schema(content):
    out = []
    seen_ids = set()
    group_names = {}
    field_ids = {f['field_id'] for g in content['groups'] for f in g['fields']}

    def check_id(value, ref):
        if not ID.fullmatch(value):
            out.append({'ref': ref, 'rule': 'bad_id'})
        elif value in seen_ids:
            out.append({'ref': ref, 'rule': 'duplicate_id'})
        seen_ids.add(value)

    for gi, group in enumerate(content['groups']):
        gref = f'/groups/{gi}'
        check_id(group['group_id'], gref + '/group_id')
        problems = check_name(group['name'], gref + '/name')
        out += problems
        if not problems:
            key = same_name(group['name'])
            if key in group_names:
                out.append({'ref': gref + '/name', 'rule': 'duplicate_name'})
            group_names[key] = gi
        names = set()
        for fi, field in enumerate(group['fields']):
            fref = f'{gref}/fields/{fi}'
            check_id(field['field_id'], fref + '/field_id')
            problems = check_name(field['name'], fref + '/name')
            out += problems
            if not problems:
                key = same_name(field['name'])
                if key in names:
                    out.append({'ref': fref + '/name', 'rule': 'duplicate_name'})
                names.add(key)
            kind = field['type']
            if field['unit'].strip() and kind != 'number':
                out.append({'ref': fref + '/unit', 'rule': 'unit_not_allowed'})
            if field['allowed'] and kind != 'category':
                out.append({'ref': fref + '/allowed', 'rule': 'allowed_not_allowed'})
            if kind == 'calculated':
                if not field['formula'].strip():
                    out.append({'ref': fref + '/formula', 'rule': 'formula_required'})
                for ii, used in enumerate(field['inputs']):
                    if used == field['field_id']:
                        out.append({'ref': f'{fref}/inputs/{ii}', 'rule': 'self_reference'})
                    elif used not in field_ids:
                        out.append({'ref': f'{fref}/inputs/{ii}', 'rule': 'unknown_input'})
            elif field['inputs']:
                out.append({'ref': fref + '/inputs', 'rule': 'inputs_not_allowed'})
    return out


def counts(content):
    """(groups, fields) of a content, for the list and the version list."""
    return len(content['groups']), sum(len(g['fields']) for g in content['groups'])
