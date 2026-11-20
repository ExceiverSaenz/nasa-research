"""Original + working copy -> effective values (ADR-004). One pure function used by versions and exports."""

STATUSES = ('pending', 'accepted', 'corrected', 'rejected', 'unsure')


def record_labels(original, state):
    """Effective name of every record: the reviewer's edit, else the model's; added records included."""
    out = {r['record_id']: r['label'] for r in original['records']}
    out.update({rid: e['label'] for rid, e in state['record_edits'].items()})
    out.update({r['record_id']: r['label'] for r in state['added_records']})
    return out


def values(original, state):
    """One row per value (version.schema.json#/$defs/value): model values in original order, then added ones."""
    labels = record_labels(original, state)
    rows = []
    for o in original['observations']:
        oid = o['observation_id']
        d = state['decisions'].get(oid)
        col = state['column_moves'].get(oid)
        rec = state['record_moves'].get(oid)
        rids = rec['record_ids'] if rec else list(o['record_ids'])
        corrected = d is not None and d['verdict'] == 'corrected'
        rows.append({
            'observation_id': oid,
            'record_ids': rids,
            'record_labels': [labels.get(r, r) for r in rids],
            'feature_id': col['feature_id'] if col else o['feature_id'],
            'original_feature_id': o['feature_id'] if col else None,
            'original_record_ids': list(o['record_ids']) if rec else None,
            'value': d['value'] if corrected else o['value'],
            'unit': d.get('unit', o['unit']) if corrected else o['unit'],
            'original_value': o['value'],
            'original_unit': o['unit'],
            'status': d['verdict'] if d else 'pending',
            'note': d['note'] if d else '',
            'by': d['by'] if d else None,
            'at': d['at'] if d else None,
            'origin': 'model',
            'needs_check': o['needs_check'],
        })
    for v in state['added_values']:
        oid = v['observation_id']
        d = state['decisions'].get(oid)
        corrected = d is not None and d['verdict'] == 'corrected'
        rows.append({
            'observation_id': oid,
            'record_ids': list(v['record_ids']),
            'record_labels': [labels.get(r, r) for r in v['record_ids']],
            'feature_id': v['feature_id'],
            'original_feature_id': None,
            'original_record_ids': None,
            'value': d['value'] if corrected else v['value'],
            'unit': d.get('unit', v['unit']) if corrected else v['unit'],
            'original_value': None,
            'original_unit': None,
            'status': d['verdict'] if d else 'pending',
            'note': d['note'] if d else v['note'],
            'by': d['by'] if d else v['by'],
            'at': d['at'] if d else v['at'],
            'origin': 'reviewer',
            'needs_check': False,
        })
    return rows


def counts(rows, state):
    out = {s: 0 for s in STATUSES}
    for r in rows:
        out[r['status']] += 1
    return {'total': len(rows), **out, 'added_values': len(state['added_values']),
            'added_records': len(state['added_records']), 'edited_records': len(state['record_edits'])}
