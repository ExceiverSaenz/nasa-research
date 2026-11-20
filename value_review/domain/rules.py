"""Rules every working copy must follow before it is stored (contract, "Rules checked on every state write").

``check_state`` returns a list of ``{'ref', 'rule'}`` problems; empty means the state is acceptable.
Shape problems (JSON Schema) are reported separately by ``shape_problems``.
"""
from .. import schemas
from ..ingest import features

MAX_PROBLEMS = 50


def shape_problems(state):
    return [{'pointer': p, 'message': m} for p, m in schemas.errors('state', state)[:MAX_PROBLEMS]]


def check_state(original, state, submit=True):
    """Business rules on a schema-valid state. ``submit`` adds BR-04 (a draft may hold an unfinished reason)."""
    out = []

    def bad(ref, rule):
        if len(out) < MAX_PROBLEMS:
            out.append({'ref': ref, 'rule': rule})

    model_obs = {o['observation_id']: o for o in original['observations']}
    model_recs = {r['record_id'] for r in original['records']}
    pages = {p['number'] for p in original['pages']}
    known_features = set(features.LABELS) | {f['feature_id'] for f in original['features']}

    # Reviewer ids: unique, and never the id of a model item.
    added_recs = [r['record_id'] for r in state['added_records']]
    added_vals = [v['observation_id'] for v in state['added_values']]
    seen = set()
    for rid in added_recs + added_vals:
        if rid in seen or rid in model_obs or rid in model_recs:
            bad(rid, 'duplicate_id')
        seen.add(rid)
    records = model_recs | set(added_recs)
    values = set(model_obs) | set(added_vals)

    for oid, d in state['decisions'].items():
        if oid not in values:
            bad(oid, 'unknown_observation')
        if submit and d['verdict'] in ('rejected', 'unsure') and not d['note'].strip():
            bad(oid, 'reason_required')  # BR-04
        if d['verdict'] == 'corrected' and not d.get('value', '').strip():
            bad(oid, 'value_required')

    for oid, m in state['column_moves'].items():
        if oid not in model_obs:
            bad(oid, 'unknown_observation')
        if m['feature_id'] not in known_features:
            bad(oid, 'unknown_feature')

    for oid, m in state['record_moves'].items():
        if oid not in model_obs:
            bad(oid, 'unknown_observation')
        for rid in m['record_ids']:
            if rid not in records:
                bad(f'{oid}:{rid}', 'unknown_record')

    for rid in state['record_edits']:
        if rid not in model_recs:
            bad(rid, 'unknown_record')

    for v in state['added_values']:
        if v['feature_id'] not in known_features:
            bad(v['observation_id'], 'unknown_feature')
        for rid in v['record_ids']:
            if rid not in records:
                bad(f"{v['observation_id']}:{rid}", 'unknown_record')

    for oid, b in state['boxes'].items():
        if oid not in values:
            bad(oid, 'unknown_observation')
            continue
        model_ev = {e['evidence_id'] for e in model_obs[oid]['evidence']} if oid in model_obs else set()
        for eid in list(b['removed']) + list(b['redrawn']):
            if eid not in model_ev:
                bad(f'{oid}:{eid}', 'unknown_evidence')
        for i, box in enumerate(list(b['redrawn'].values()) + b['added']):
            if box['page'] not in pages:
                bad(f'{oid}:page {box["page"]}', 'page_out_of_range')
            x0, y0, x1, y1 = box['bbox']
            if x1 <= x0 or y1 <= y0:
                bad(f'{oid}:box {i}', 'empty_box')
    return out
