"""Aggregate explicit visual reviews; never invent a reference or accept a label."""
import argparse
from collections import Counter
from pathlib import Path
from .common import read,save,sha

CONDITIONS=('M0','M1','R')
DIMENSIONS=('presence','classification','separation','geometry','linkage','duplicates')
STATES={'presence':{'present','partial','missing','indeterminate'},
        **{d:{'correct','incorrect','partial','indeterminate','not_applicable'} for d in DIMENSIONS if d!='presence'}}

def aggregate(status,reviews):
    totals={c:{d:Counter() for d in DIMENSIONS} for c in CONDITIONS};pages=[]
    label_totals={c:Counter() for c in CONDITIONS};changes=[]
    expected={x['page'] for x in status['pages']}
    if set(reviews)!=expected:raise ValueError('Every document page must be accounted for')
    for page in sorted(expected):
        review=reviews[page]
        if not review.get('whole_page_inventory_complete') or not review.get('reviewer'):raise ValueError('Visual inventory/reviewer missing on page '+str(page))
        units=review['manual_units']
        if not units and not (review.get('page_is_blank') or review.get('not_evaluable_reason')):raise ValueError('Empty reference without explicit explanation')
        if len({x['id'] for x in units})!=len(units):raise ValueError('Duplicate reference ID')
        counts={c:{d:Counter() for d in DIMENSIONS} for c in CONDITIONS}
        for unit in units:
            if not unit.get('evidence'):raise ValueError('Unit evidence required')
            for c in CONDITIONS:
                observation=unit['conditions'][c]
                for dimension in DIMENSIONS:
                    value=observation[dimension]
                    if value not in STATES[dimension]:raise ValueError('Unsupported review status')
                    counts[c][dimension][value]+=1;totals[c][dimension][value]+=1
        for case in review.get('label_cases',[]):
            if not case.get('visible') or not case.get('evidence'):raise ValueError('Recurrence denominator requires visible inspected label evidence')
            for c in CONDITIONS:
                state=case['conditions'][c]
                if state not in {'recognized_linked','recognized_unlinked','ambiguous','not_located_in_inspected_fields','not_evaluated'}:raise ValueError('Unknown label state')
                label_totals[c][state]+=1
        for change in review.get('changes',[]):
            if change['classification'] not in ('mejora','regresion','equivalente','indeterminado') or change['attribution'] not in ('localized_recovery','reconciliation','manual_adjudication','representation_only') or not change.get('evidence'):raise ValueError('Change needs attribution, class and evidence')
            changes.append(dict(page=page,**change))
        pages.append(dict(page=page,reference_units=len(units),results=counts,
            reading_cases=review.get('reading_cases',[]),continuity_cases=review.get('continuity_cases',[]),
            changed_transcription_or_table_structure=review.get('transcription_table_cases',[]),
            limitations=review.get('limitations',[]),execution=next(x for x in status['pages'] if x['page']==page)))
    recurrence={c:dict(counts=label_totals[c],visible_denominator=sum(label_totals[c].values()),
                     not_located_in_inspected_fields=label_totals[c]['not_located_in_inspected_fields']) for c in CONDITIONS}
    return dict(status='visual_review_aggregated_not_independent_GT',pages=pages,totals=totals,label_recurrence=recurrence,
        change_ledger=changes,unexamined_reading_or_transcription_pages=[p['page'] for p in pages if not p['reading_cases'] or not p['changed_transcription_or_table_structure']],
        conclusion='requires_explicit_evidence_based_report_not_a_count_of_boxes',automatic_recovery=False)

def finalize(source,destination):
    source=Path(source);destination=Path(destination)
    if destination.exists():raise FileExistsError('Fresh summary destination required')
    status=read(source/'document-status.json')
    files={p['page']:source/('page-%04d'%p['page'])/'review-template.json' for p in status['pages']}
    result=aggregate(status,{page:read(f) for page,f in files.items()})
    destination.mkdir(parents=True)
    save(destination/'document-comparison.json',result)
    save(destination/'manifest.json',dict(inputs={str(f):sha(f) for f in files.values()},document_status_sha256=sha(source/'document-status.json')))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reviews',required=True);p.add_argument('--output',required=True);a=p.parse_args();finalize(a.reviews,a.output)
