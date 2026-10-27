"""Additive native evidence integration. Never rewrites approved classifications/order."""
import copy
from .align import align_native, compact
from .claims import reconcile_claims


def integrate(baseline, native):
    links=align_native(native,baseline); linked={l['unit_ref']:l for l in links}
    inventory=baseline['inventory']; units={i['unit_ref']:i['original_unit'] for i in inventory}
    fields={}
    for e in native['evidence']:
        if e['kind'] in ('xmp','pdf_metadata'):
            fields.setdefault(e['data']['field'],[]).append(e)
    def text(id):return linked[id]['native_text'] or units[id].get('original_record',{}).get('text','') or ''
    def claim(value,strength,refs,reason):return dict(value=value,strength=strength,evidence_refs=refs,reason=reason)
    def y(id):return (units[id].get('bbox_xyxy') or [0,0,0,0])[1]
    titles=[compact(v) for k in ('dc:title','title') for e in fields.get(k,[]) for v in e['data']['values'] if compact(v)]
    sections=[]; outline_sections={}
    for e in native['evidence']:
        if e['kind']!='outline':continue
        d=e['data']; title=compact(d['title'])
        if title in titles:continue  # Native article root is preserved in evidence, not a body section.
        candidates=[id for id,u in units.items() if u['page']==e['page'] and linked[id]['evidence_refs'] and compact(text(id))==title]
        s=dict(id='section:'+e['id'],title=d['title'],page=e['page'],declared_level=d['level'],parent_section_ref=None,
            heading_candidates=candidates,status='aligned_unique' if len(candidates)==1 else 'ambiguous_alignment' if candidates else 'unlocated',
            evidence_refs=[e['id']],hierarchy_status='declared_by_pdf',requires_human_validation=True,warning='Requiere validación humana')
        sections.append(s);outline_sections[e['id']]=s
    for e in native['evidence']:
        if e['id'] not in outline_sections:continue
        parent=e['data'].get('parent_ref');seen={e['id']}
        while parent and parent not in outline_sections and parent not in seen:
            seen.add(parent);p=next((x for x in native['evidence'] if x['id']==parent),None);parent=p['data'].get('parent_ref') if p else None
        if parent in outline_sections and parent not in seen:outline_sections[e['id']]['parent_section_ref']=outline_sections[parent]['id']
    headings={id:s for s in sections for id in s['heading_candidates']}
    anchors=[id for s in sections if s['status']=='aligned_unique' for id in s['heading_candidates']]
    title_anchors=[id for id in units if linked[id]['evidence_refs'] and compact(text(id)) in titles]
    if not anchors:
        # Existing title evidence can delimit context; it does not declare a hierarchy.
        anchors=[id for id,u in units.items() if u['classification'].get('category',{}).get('value')=='title' and id not in title_anchors and compact(text(id)) not in {'abstract','keywords','articleinfo','articleinformation'} and linked[id]['evidence_refs']]
    first=min(((units[id]['page'],y(id)) for id in anchors),default=None)
    title_page=min((units[id]['page'] for id in title_anchors),default=None)
    def front(id):
        u=units[id];record=u.get('original_record',{})
        context=(u['page'],y(id))<first if first else title_page is not None and u['page']==title_page
        return context and record.get('native_type')!='ref_text' and linked[id]['status']=='span_centers_supported'
    proposals=[];abstract_headers=[id for id in units if front(id) and compact(text(id))=='abstract']
    for index,item in enumerate(inventory):
        id=item['unit_ref'];u=units[id];old=u['classification'];refs=linked[id]['evidence_refs'];t=compact(text(id));claims={};unapplied=[]
        for dim in ('category','function'):
            claims[dim]=[claim(old.get(dim,{}).get('value'),'retained',[f'baseline:/inventory/{index}/original_unit/classification/{dim}'],'classification retained unchanged')]
        claims['document_role']=[]
        claims['flow']=[claim({'main':'main_body','metadata':'front_matter','notes':'notes','bibliography':'bibliography','editorial_navigation':'editorial_navigation'}.get(item.get('route'),item.get('route')),'retained',[f'baseline:/inventory/{index}/route'],'approved route retained unchanged')]
        def role(value,strength,evidence,reason,function=None,flow=None):
            claims['document_role'].append(claim(value,strength,evidence,reason))
            if function:claims['function'].append(claim(function,strength,evidence,reason))
            if flow:claims['flow'].append(claim(flow,strength,evidence,reason))
        if id in headings:
            s=headings[id];role('section_heading','direct' if s['status']=='aligned_unique' else 'inferred',refs+s['evidence_refs'],'PDF outline and localized matching text',function='main_body')
        for key in ('dc:title','title'):
            for e in fields.get(key,[]):
                if t and any(t==compact(v) for v in e['data']['values']) and front(id):role('article_title','direct',refs+[e['id']],'exact native title in front matter',function='metadata',flow='front_matter')
        for e in fields.get('dc:creator',[])+fields.get('author',[]):
            names=[compact(v) for v in e['data']['values'] if compact(v)]
            if front(id) and t and any(n in t for n in names):
                remainder=t
                for name in sorted(names,key=len,reverse=True):remainder=remainder.replace(name,'')
                remainder=remainder.replace('and','')
                if not remainder or remainder.isdigit():role('authorship','direct',refs+[e['id']],'localized author-list text explained by declared names and numeric markers',function='metadata',flow='front_matter')
                else:unapplied.append(claim('author_name_mention','candidate',refs+[e['id']],'name match alone does not establish authorship; additional text remains'))
        for key in ('dc:subject','prism:copyright'):
            for e in fields.get(key,[]):
                values=[compact(v) for v in e['data']['values'] if compact(v)]
                if front(id) and values and (t in values or key=='dc:subject' and all(v in t for v in values)):
                    role('keywords' if key=='dc:subject' else 'copyright','direct',refs+[e['id']],'declared field localized in front matter',function='metadata',flow='front_matter')
        if id in abstract_headers:role('abstract_heading','inferred',refs,'explicit heading in front context',function='metadata',flow='front_matter')
        if front(id) and not claims['document_role'] and abstract_headers:
            box=u.get('bbox_xyxy'); ah=[a for a in abstract_headers if y(a)<y(id) and abs(units[a]['bbox_xyxy'][0]-box[0])<max(1,box[2]-box[0])*.12]
            if ah and old.get('category',{}).get('value')=='text':role('abstract_body_candidate','inferred',refs+sum((linked[a]['evidence_refs'] for a in ah),[]),'body text under abstract heading before first section; contextual inference',function='metadata',flow='front_matter')
        if front(id) and not claims['document_role']:
            words=text(id).casefold().split()
            if any(w.strip('.,;:') in {'university','institute','laboratory','department','laboratories'} for w in words):role('affiliation_candidate','inferred',refs,'organization cue in front context; not an identity proof',function='metadata',flow='front_matter')
        decisions={d:reconcile_claims(c) for d,c in claims.items()}
        proposals.append(dict(unit_ref=id,decisions=decisions,unapplied_native_candidates=unapplied,inherited_warnings=copy.deepcopy(old.get('warnings',[])),original_route=item.get('route'),applied_to_baseline=False))
    if not sections:
        for id,u in units.items():
            if u['classification'].get('category',{}).get('value')=='title' and not front(id):
                sections.append(dict(id='section:candidate:'+id,title=text(id),page=u['page'],declared_level=None,parent_section_ref=None,heading_candidates=[id],status='unresolved_heading_candidate',hierarchy_status='unknown',evidence_refs=linked[id]['evidence_refs'],requires_human_validation=True,warning='Requiere validación humana'))
    stepmap={s['id']:s for s in baseline['steps']};sequence=[]
    for sid in baseline['routes'].get('main',{}).get('expanded_sequence',[]):
        step=stepmap[sid]
        if step['kind']=='content' and step['unit_ref'] not in sequence:sequence.append(step['unit_ref'])
    pmap={p['unit_ref']:p for p in proposals};uniquehead={s['heading_candidates'][0]:s for s in sections if s['status']=='aligned_unique'}
    memberships=[];active=None;paragraphs=[];continuities=[];previous=None
    for id in sequence:
        if id in uniquehead:active=uniquehead[id];previous=None;continue
        p=pmap[id];u=units[id];category=p['decisions']['category']['operational_proposal'];role=p['decisions']['document_role']['operational_proposal']
        if p['decisions']['flow']['operational_proposal']=='front_matter':continue
        visual=category in ('figure','table','caption') or u.get('structural_kind')=='group'
        memberships.append(dict(unit_ref=id,spatial_section_candidate=active['id'] if active else None,thematic_section_candidates=[] if visual else [active['id']] if active else [],status='physical_context_only' if visual else 'inferred_from_provisional_order' if active else 'unknown',alternatives_preserved=True,warning='Requiere validación humana; depende del recorrido provisional'))
        if category=='text' and not role:
            paragraphs.append(dict(id='paragraph-fragment:'+id,fragment_refs=[id],status='fragment_preserved',text_concatenated=False))
            if previous:
                a=text(previous).rstrip();b=text(id).lstrip();ba=units[previous].get('bbox_xyxy');bb=u.get('bbox_xyxy')
                boundary=units[previous]['page']!=u['page'] or ba and bb and bb[0]>ba[2]
                if boundary and a and b and (a[-1] not in '.!?:;' and b[0].islower() or a.endswith('-')):
                    continuities.append(dict(type='paragraph_continues',**{'from':previous,'to':id},status='candidate_only',evidence_refs=list(dict.fromkeys(linked[previous]['evidence_refs']+linked[id]['evidence_refs'])),reason='open ending/start and column or page boundary in approved provisional traversal',alternatives=['separate_paragraphs'],warning='Requiere validación humana; no concatenar',applied=False))
            previous=id
        elif not visual:previous=None
    covered={m['unit_ref'] for m in memberships}
    for item in inventory:
        id=item['unit_ref']
        if id in covered:continue
        heading=uniquehead.get(id)
        memberships.append(dict(unit_ref=id,spatial_section_candidate=heading['id'] if heading else None,thematic_section_candidates=[],
            status='heading_of_section' if heading else 'deferred' if item['disposition']=='deferred_child_reference' else 'outside_main_route' if item.get('route')!='main' else 'unresolved_or_front_matter',
            alternatives_preserved=True,warning='Requiere validación humana'))
    return dict(schema_version='native-structure-v2.B-native.1',paper_id=baseline['paper_id'],document=baseline['document'],inventory=copy.deepcopy(inventory),approved_routes=copy.deepcopy(baseline['routes']),approved_steps=copy.deepcopy(baseline['steps']),
        native_pdf_sha256=native['pdf_sha256'],native_evidence=copy.deepcopy(native['evidence']),native_pages=copy.deepcopy(native['pages']),missing_native_information=native['missing_information'],evidence_links=links,classification_proposals=proposals,
        contradictions=[dict(unit_ref=p['unit_ref'],dimension=d,**decision) for p in proposals for d,decision in p['decisions'].items() if decision['status']=='conflict'],
        document_structure=dict(sections=sections,memberships=memberships,paragraph_fragments=paragraphs,continuity_candidates=continuities),
        policy=dict(originals_unchanged=True,order_unchanged=True,proposals_applied=False,review_stage='after_full_mvp',warning='Requiere validación humana',probabilities_calibrated=False,models_executed=False))
