"""Invariant checking and counts, never inventing semantic accuracy without reference."""
from collections import Counter


def validate_C(B,C):
    for field in ('inventory','approved_routes','approved_steps','classification_proposals','native_evidence','evidence_links','document_structure'):
        if B[field]!=C[field]:raise ValueError('B mutation: '+field)
    ids=[i['unit_ref'] for i in B['inventory']];nodes={n['id']:n for n in C['grobid_evidence']['nodes']}
    if len(set(ids))!=len(ids):raise ValueError('duplicate inventory')
    pids=[p['unit_ref'] for p in C['grobid_proposals']]
    if sorted(pids)!=sorted(ids):raise ValueError('incomplete proposals')
    allnodes=C['grobid_evidence']['nodes']+C['grobid_evidence']['unmapped_nodes'];account=C['grobid_evidence']['accounting']
    if len({n['id'] for n in allnodes})!=len(allnodes) or account['xml_nodes']!=len(allnodes) or account['selected_nodes']!=len(nodes):raise ValueError('TEI node accounting mismatch')
    for n in nodes.values():
        if n['source']['derived_from_pdf_sha256']!=B['native_pdf_sha256'] or n['source']['tei_sha256']!=C['grobid_evidence']['tei_sha256']:raise ValueError('source identity mismatch')
        seen={n['id']};parent=n['parent_ref']
        while parent:
            if parent not in nodes or parent in seen:raise ValueError('invalid TEI parent graph')
            seen.add(parent);parent=nodes[parent]['parent_ref']
    native={n['id']:n for n in B['native_evidence']};links=C['grobid_alignment']
    if len(links)!=len(nodes) or {l['evidence_ref'] for l in links}!=set(nodes):raise ValueError('evidence/link accounting')
    deferred={i['unit_ref'] for i in B['inventory'] if i['disposition']=='deferred_child_reference'}
    for l in links:
        for ref in l['native_span_refs']:
            try:
                value=native[ref['evidence_ref']]
                for token in ref['pointer'].lstrip('/').split('/'):value=value[int(token)] if isinstance(value,list) else value[token]
                if 'text' not in value:raise ValueError()
            except (KeyError,IndexError,TypeError,ValueError) as exc:raise ValueError('dangling native span pointer') from exc
        for m in l['matches']+l['candidates']:
            if m['unit_ref'] not in ids or m['unit_ref'] in deferred:raise ValueError('invalid/deferred unit link')
    for p,prior in zip(C['grobid_proposals'],B['classification_proposals']):
        if p['unit_ref']!=prior['unit_ref']:raise ValueError('proposal order changed')
        if set(p['dimensions'])!=set(prior['decisions']):raise ValueError('dimension omission')
        for dim,d in p['dimensions'].items():
            if d['B_decision']!=prior['decisions'][dim]:raise ValueError('previous decision mutation')
            if d['C_decision']['probability'] is not None:raise ValueError('fabricated probability')
            old=d['B_decision']['operational_proposal'];new=d['C_decision']['operational_proposal']
            if old is not None and old!=new:raise ValueError('conflict overrides known B')
            for claim in d['grobid_claims']:
                if claim['evidence_ref'] not in nodes or claim['strength']!='model_inferred':raise ValueError('invalid claim provenance')
            if old is None and new is not None and not any(c['scope']=='whole_region' and c['alignment_status'] in ('aligned_unique','aligned_fragment_set') and c['value']==new for c in d['grobid_claims']):raise ValueError('partial/ambiguous claim promoted')
    structure=C['grobid_structure']
    for s in structure['section_candidates']:
        if s['evidence_ref'] not in nodes or any(u not in ids for u in s['heading_candidates']) or s['parent_section_ref'] is not None:raise ValueError('invalid/invented model hierarchy')
    for m in structure['membership_candidates']:
        if m['unit_ref'] not in ids or m['evidence_ref'] not in nodes or any(h not in nodes for h in m['section_evidence_candidates']):raise ValueError('invalid membership')
    for r in structure['continuity_candidates']:
        if r['from'] not in ids or r['to'] not in ids or r['evidence_ref'] not in nodes or r['applied'] or r['text_concatenated']:raise ValueError('invalid continuity')
    for r in structure['association_candidates']:
        if r['source_evidence_ref'] not in nodes or any(t not in nodes for t in r['target_evidence_candidates']):raise ValueError('invalid association')
    return dict(B_preserved=True,inventory_and_order_preserved=True,all_claims_traceable=True,deferred_policy_preserved=True,quality_validated=False)


def compare_B_C(B,C,reference=None):
    checks=validate_C(B,C);rows=[]
    for p,item in zip(C['grobid_proposals'],B['inventory']):
        for dim,d in p['dimensions'].items():
            before=d['B_decision']['operational_proposal'];after=d['C_decision']['operational_proposal']
            rows.append(dict(unit_ref=p['unit_ref'],page=item['page'],category=item['original_unit']['classification']['category']['value'],dimension=dim,B=before,C=after,status=d['C_decision']['status'],changed=before!=after,partial_claims=sum(c['scope']!='whole_region' for c in d['grobid_claims'])))
    def counts(sub):return dict(dimensions=len(sub),changes=sum(r['changed'] for r in sub),conflicts=sum(r['status']=='unresolved_conflict' for r in sub),abstentions=sum(r['C'] is None for r in sub),transitions=dict(Counter(str(r['B'])+' → '+str(r['C']) for r in sub)))
    report=dict(verification=checks,denominators=dict(units=len(B['inventory']),TEI_entities=len(C['grobid_evidence']['nodes']),decision_dimensions=len(rows)),global_counts=counts(rows),
        by_page={str(p):counts([r for r in rows if r['page']==p]) for p in sorted({r['page'] for r in rows})},by_category={str(c):counts([r for r in rows if r['category']==c]) for c in {r['category'] for r in rows}},by_dimension={d:counts([r for r in rows if r['dimension']==d]) for d in {r['dimension'] for r in rows}},
        alignment=dict(Counter(l['status'] for l in C['grobid_alignment'])),unmapped_labels=len(C['grobid_unmapped_labels']),transitions=rows,order_changed=False,coverage_is_not_accuracy=True,quality=dict(status='not_evaluated',semantic_accuracy=None,macro_F1=None,reason='Independent adjudicated reference pending after_full_mvp'))
    if reference is not None:raise ValueError('Reference scoring requires an independently approved annotation contract; no surrogate GT accepted')
    return report
