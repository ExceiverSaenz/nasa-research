"""Add model hypotheses, retaining B decisions and original inventory verbatim."""
import copy
import json
from pathlib import Path


def load_mapping():return json.loads((Path(__file__).parent/'grobid_mapping.json').read_text(encoding='utf-8'))


def mapped(node,mapping):
    tags=[a['tag'] for a in node['ancestors']]
    contexts={'any'}
    if 'teiHeader' not in tags and (any(t in tags for t in ('biblStruct','listBibl')) or node['tag']=='biblStruct'):contexts.add('bibliography')
    for tag,context in [('teiHeader','header'),('body','body'),('abstract','abstract'),('note','note'),('figure','figure')]:
        if tag in tags:contexts.add(context)
    for rule in mapping['rules']:
        if rule['tag']==node['tag'] and rule['context'] in contexts and ('type' not in rule or node['attributes'].get('type')==rule['type']):return rule
    return None


def reconcile_dimension(previous,claims):
    old=copy.deepcopy(previous);decision=copy.deepcopy(previous);value=old['operational_proposal']
    allvalues=list(dict.fromkeys(old.get('alternatives',[])+([value] if value is not None else [])+[c['value'] for c in claims]))
    usable=[c for c in claims if c['scope']=='whole_region' and c['alignment_status'] in ('aligned_unique','aligned_fragment_set')]
    values=set(c['value'] for c in usable)
    conflicts=[c for c in claims if value is not None and c['value']!=value]
    if conflicts or len(values)>1:decision['status']='unresolved_conflict'
    elif value is None and len(values)==1:decision.update(operational_proposal=next(iter(values)),status='model_inferred')
    elif value is not None and usable:decision['status']='agreement_unvalidated'
    decision.update(alternatives=allvalues,probability=None,independent_confirmation=False,warning='Requiere validación humana',review_stage='after_full_mvp',requires_human_validation=True)
    return dict(B_decision=old,grobid_claims=claims,C_decision=decision)


def integrate_grobid(B,evidence,links,mapping):
    if evidence['run'].get('pdf_sha256')!=B['native_pdf_sha256']:raise ValueError('PDF identity mismatch')
    C=copy.deepcopy(B);nodes={n['id']:n for n in evidence['nodes']};lmap={l['evidence_ref']:l for l in links};byunit={i['unit_ref']:[] for i in B['inventory']};unmapped=[]
    for n in evidence['nodes']:
        rule=mapped(n,mapping);link=lmap[n['id']]
        if not rule:unmapped.append(dict(evidence_ref=n['id'],reason='unmapped_model_label'));continue
        proposals=link['matches'] if link['status'] in ('aligned_unique','aligned_fragment_set') else link['candidates']
        for match in proposals:
            if match['unit_ref'] not in byunit:raise ValueError('unknown unit')
            for dim,val in rule['values'].items():
                byunit[match['unit_ref']].append(dict(dimension=dim,value=val,strength='model_inferred',scope='fragment' if rule.get('force_fragment') else match.get('scope','candidate'),alignment_status=link['status'],evidence_ref=n['id'],source=copy.deepcopy(n['source']),dependency_refs=[B['native_pdf_sha256']],probability=None))
    result=[]
    for p in B['classification_proposals']:
        claims=byunit[p['unit_ref']];dimensions={d:reconcile_dimension(prior,[c for c in claims if c['dimension']==d]) for d,prior in p['decisions'].items()}
        result.append(dict(unit_ref=p['unit_ref'],dimensions=dimensions,observation='observed_by_grobid' if claims else 'not_observed_by_grobid',inherited_warnings=copy.deepcopy(p['inherited_warnings']),warning='Requiere validación humana',applied_to_B=False))
    sections=[];memberships=[];continuities=[];associations=[]
    for n in evidence['nodes']:
        rule=mapped(n,mapping);link=lmap[n['id']];refs=[m['unit_ref'] for m in link['matches']]
        if rule and rule['values'].get('document_role')=='section_heading':
            sections.append(dict(evidence_ref=n['id'],heading_candidates=refs,declared_level=None,parent_section_ref=None,status='model_heading_candidate',B_section_candidates=[s['id'] for s in B['document_structure']['sections'] if set(s['heading_candidates']) & set(refs)]))
        if n['tag']=='p':
            parent=n.get('parent_ref');visited=set();heads=[]
            while parent and parent not in visited:
                visited.add(parent);ancestor=nodes[parent]
                if ancestor['tag']=='div':
                    heads=[x['id'] for x in evidence['nodes'] if x['parent_ref']==parent and x['tag']=='head'];break
                parent=ancestor.get('parent_ref')
            for id in refs:memberships.append(dict(unit_ref=id,section_evidence_candidates=heads,status='model_membership_candidate',evidence_ref=n['id'],physical_context_changed=False))
            for a,b in zip(refs,refs[1:]):
                ia=next(i for i in B['inventory'] if i['unit_ref']==a);ib=next(i for i in B['inventory'] if i['unit_ref']==b)
                continuities.append(dict(type='paragraph_continues',**{'from':a,'to':b},evidence_ref=n['id'],status='candidate_only',applied=False,blocked_between_independent_routes=ia.get('route')!=ib.get('route'),text_concatenated=False))
        if n['tag']=='ref' and n.get('target'):
            for target in n['target'].split():
                targets=[x['id'] for x in evidence['nodes'] if '#'+str(x.get('xml_id'))==target]
                associations.append(dict(type='mentions',source_evidence_ref=n['id'],target_literal=target,target_evidence_candidates=targets,status='candidate_only',not_caption_association=True))
        if n['tag']=='figure':
            desc=[x for x in evidence['nodes'] if x['parent_ref']==n['id'] and x['tag'] in ('head','figDesc')]
            for x in desc:associations.append(dict(type='caption_of',source_evidence_ref=x['id'],target_evidence_candidates=[n['id']],status='candidate_only',applied=False))
    C.update(schema_version='grobid-C/1',grobid_evidence=copy.deepcopy(evidence),grobid_alignment=copy.deepcopy(links),grobid_mapping=copy.deepcopy(mapping),grobid_proposals=result,grobid_unmapped_labels=unmapped,
        grobid_structure=dict(section_candidates=sections,membership_candidates=memberships,continuity_candidates=continuities,association_candidates=associations),grobid_policy=dict(models_executed_by_integrator=False,model_response_run_ref=evidence['run'].get('run_id'),baseline_policy_preserved=True,review_stage='after_full_mvp'),status='technically_integrated_pending_semantic_validation')
    return C
