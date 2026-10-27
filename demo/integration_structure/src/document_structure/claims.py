"""Dimension-specific evidence reconciliation, without votes or invented confidence."""
import copy
import json


def reconcile_claims(claims):
    claims=copy.deepcopy(claims);known=[c for c in claims if c.get('value') is not None]
    key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False)
    values={key(c['value']):c['value'] for c in known}
    direct={key(c['value']):c['value'] for c in known if c['strength']=='direct'}
    inferred={key(c['value']):c['value'] for c in known if c['strength']=='inferred'}
    retained={key(c['value']):c['value'] for c in known if c['strength'].startswith('retained')}
    chosen=next(iter(direct.values())) if len(direct)==1 else None
    if not direct and len(inferred)==1:chosen=next(iter(inferred.values()))
    if not direct and not inferred and len(retained)==1:chosen=next(iter(retained.values()))
    conflict=len(values)>1
    status='conflict' if conflict else 'direct_supported' if direct else 'inferred_proposal' if inferred else 'retained_unvalidated' if known else 'unknown'
    return dict(status=status,operational_proposal=chosen,claims=claims,alternatives=list(values.values()),
        probability=None,review_stage='after_full_mvp',requires_human_validation=True,
        warning='Requiere validación humana',source_independence_not_assumed=True)
