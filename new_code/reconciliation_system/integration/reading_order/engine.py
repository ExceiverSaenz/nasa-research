"""Pure hierarchical reading-order proposals from reconciled classification."""
import copy
import hashlib
import re
import unicodedata
from collections import Counter,defaultdict
from .layout import CONFIG,valid_box,xy_order,graph_order

VERSION='reconciled-reading-order/1'
ROUTES=('main','notes','bibliography','metadata','editorial_navigation','pending_structures')
USABLE={'native_preserved','automatic_rule','human_accepted','accepted'}


def warning(code,reason=None):
    return dict(code=code,message='Requiere validación humana',reason=reason or code,review_stage='after_full_mvp')


def sid(*parts):return 's-'+hashlib.sha256('\0'.join(parts).encode()).hexdigest()[:24]


def order_document(classified):
    if classified.get('classification_scope')!='reconciled_units_only':raise ValueError('requires reconciled units only')
    regions={r['id']:r for r in classified['regions']};groups={g['id']:g for g in classified.get('logical_units',[])}
    if len(regions)!=len(classified['regions']) or len(groups)!=len(classified.get('logical_units',[])) or set(regions)&set(groups):raise ValueError('duplicate unit ids')
    units={**regions,**groups};pages={p['identity']['physical_page']:p for p in classified['pages']}
    if len(pages)!=len(classified['pages']):raise ValueError('duplicate pages')
    children=defaultdict(list)
    for r in regions.values():
        parent=r['original_record'].get('parent')
        if parent in regions:children[parent].append(r['id'])
    inventory={id:dict(unit_ref=id,page=u['page'],kind=u['structural_kind'],disposition=None,route=None,appearance_ref=None,reference_visits=[],original_unit=copy.deepcopy(u)) for id,u in units.items()}
    steps={};capsules=[];owner={};layouts=[];decisions=[];relations=[];suspended=[];pending=[]
    rtl_pages={r['page'] for r in regions.values() if any(unicodedata.bidirectional(ch) in ('R','AL') for ch in r['original_record'].get('text',''))}
    def blocked(page):return page in rtl_pages or pages[page].get('original_status')=='blocked' or 'invalid_geometry' in pages[page].get('original_incidents',[])
    def bbox(id):
        r=regions.get(id);p=pages[units[id]['page']]['identity'];b=r.get('bbox_xyxy') if r else None
        return b if valid_box(b,p['width_px'],p['height_px']) else None
    def normalized(id):
        b=bbox(id);p=pages[units[id]['page']]['identity']
        return [b[0]/p['width_px'],b[1]/p['height_px'],b[2]/p['width_px'],b[3]/p['height_px']] if b else None
    def inherited(id):return copy.deepcopy(units[id]['classification'].get('warnings',[]))
    def route(id):
        u=regions[id];c=u['classification'];r=u['original_record'];nt=r.get('native_type');f=c['function']['value'];sub=c['subtype']['candidates']
        if nt=='ref_text' or 'bibliographic_reference' in sub:return 'bibliography'
        if nt in ('page_footnote','table_footnote','image_footnote'):return 'notes'
        if f=='metadata':return 'metadata'
        if f in ('editorial','navigation'):return 'editorial_navigation'
        return 'main'
    def make(id,kind,route_name,context='',render=None):
        stepid=sid(context,id);u=units[id];warnings=inherited(id)
        if blocked(u['page']):warnings.append(warning('unsupported_writing_direction' if u['page'] in rtl_pages else 'inherited_page_abstention'))
        st=dict(id=stepid,unit_ref=id,page=u['page'],kind=kind,route=route_name,children=[],render_unit_refs=render if render is not None else ([id] if id in regions and bbox(id) else []),
                evidence_status='abstained' if blocked(u['page']) else 'proposal',order_basis='retained_structure' if context else 'geometry_proposal',warnings=warnings)
        steps[stepid]=st;return st
    def footprint(ids):
        boxes=[normalized(id) for id in ids if id in regions and normalized(id)]
        if not boxes:return None
        return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
    def add_capsule(id,childids,bodyids,kind):
        u=units[id];p=u['page'];root=make(id,kind,'main',render=[x for x in bodyids if bbox(x)])
        root['anchor_refs']=list(bodyids);root['_box']=footprint(bodyids);root['_text']=''
        root['association_authority']=copy.deepcopy(u.get('original_group',{}).get('status','native_preserved'))
        for child in childids:
            if child not in regions:raise ValueError('association child missing')
            reference=child in owner
            visit=make(child,'reference' if reference else 'content','main',root['id'])
            visit['parent_step_ref']=root['id']
            visit['role']='visual_body' if child in bodyids else 'caption'
            visit['order_basis']='caption_first_policy' if regions[child]['classification']['category']['value']=='caption' else 'retained_membership'
            if reference:
                visit['content_appearance_ref']=owner[child];visit['warnings'].append(warning('shared_content_reference'));inventory[child]['reference_visits'].append(visit['id'])
                if child in bodyids:
                    previous=steps[owner[child]];root['order_basis']='fallback';previous['order_basis']='fallback';visit['order_basis']='fallback'
                    root['warnings'].append(warning('shared_body_ownership_fallback'));previous['warnings'].append(warning('shared_body_ownership_fallback'))
                    if previous.get('parent_step_ref'):
                        steps[previous['parent_step_ref']]['order_basis']='fallback'
                    decisions.append(dict(unit_ref=child,status='shared_body_ownership_fallback',chosen_owner_step=previous.get('parent_step_ref'),alternative_owner_steps=[root['id']]))
            else:
                owner[child]=visit['id'];inventory[child].update(disposition='content',route='main',appearance_ref=visit['id'])
            root['children'].append(visit['id'])
        inventory[id].update(disposition='structural_step',route='main',appearance_ref=root['id'])
        capsules.append(root)
        return root
    deferred=set()
    for parent,childids in sorted(children.items()):
        if regions[parent]['structural_kind']!='container':continue
        if any(bbox(x) is None for x in childids):
            st=make(parent,'deferred_structure','main');st['deferred_child_refs']=sorted(childids);st['child_sequence']=None
            st['_box']=normalized(parent);st['_text']='';st['warnings'].append(warning('deferred_children_no_order'))
            if not bbox(parent):st['warnings'].append(warning('unlocated_structure'))
            st['order_basis']='fallback';capsules.append(st)
            inventory[parent].update(disposition='structural_placeholder',route='main',appearance_ref=st['id'])
            for child in childids:
                deferred.add(child);inventory[child].update(disposition='deferred_child_reference',route='pending_structures',appearance_ref=None,parent_step_ref=st['id'])
            pending.extend(childids)
    # Build declared groups in physical order, not record ID order.
    def group_key(g):
        b=footprint(g.get('members',[]));return (g['page'],b[1] if b else float('inf'),b[0] if b else float('inf'),g['id'])
    for g in sorted(groups.values(),key=group_key):
        ids=g.get('members',[]);cap=g.get('caption_ref');state=g.get('original_group',{}).get('status')
        if not ids or any(x not in regions for x in ids) or cap not in regions:raise ValueError('invalid group references')
        if state not in USABLE or set(ids+[cap])&deferred or any(bbox(x) is None for x in ids+[cap]) or len({regions[x]['page'] for x in ids+[cap]})!=1:
            inventory[g['id']].update(disposition='pending_group_reference',route='pending_structures')
            pending.append(g['id']);decisions.append(dict(unit_ref=g['id'],status='association_alternative_only',warnings=[warning('group_not_eligible_for_expansion')]))
            continue
        layout=xy_order([dict(id=x,box=normalized(x),text=regions[x]['original_record'].get('text','')) for x in ids]);ordered=layout['order']
        root=add_capsule(g['id'],[cap]+ordered,ordered,'group')
        if layout['fallback_ids'] or (max(normalized(x)[0] for x in ids)-min(normalized(x)[0] for x in ids)>.15):
            root['warnings'].append(warning('group_member_order_provisional'))
        decisions.append(dict(unit_ref=g['id'],status='retained_group_expansion',rule='caption_first',original_status=state,alternatives=layout['alternatives']))
    for id,r in sorted(regions.items()):
        if r['structural_kind']!='container' or inventory[id]['disposition']:continue
        childids=children.get(id,[]);available=[x for x in childids if x not in owner and x not in deferred]
        nt=r['original_record'].get('native_type')
        caps=[x for x in available if 'caption' in regions[x]['classification']['category']['candidates'] or regions[x]['original_record'].get('native_type','').endswith('_caption')]
        bodies=[x for x in available if regions[x]['classification']['category']['value'] in ('figure','table') or regions[x]['original_record'].get('native_type') in ('chart_body','image_body','table_body')]
        native_links=[rel for p in classified['pages'] for rel in p.get('original_relations',[]) if rel.get('type')=='native_parent_child' and rel.get('parent')==id and rel.get('status') in USABLE]
        linked={rel.get('child') for rel in native_links}
        if nt in ('chart','image','table') and bodies and set(caps+bodies)<=linked:
            ordered=xy_order([dict(id=x,box=normalized(x),text=regions[x]['original_record'].get('text','')) for x in bodies])['order']
            orderedcaps=xy_order([dict(id=x,box=normalized(x),text=regions[x]['original_record'].get('text','')) for x in caps])['order']
            add_capsule(id,orderedcaps+ordered,ordered,'visual_structure')
        else:inventory[id].update(disposition='structural_reference',route='pending_structures',child_refs=list(childids));pending.append(id)
    for id,r in sorted(regions.items()):
        if r['structural_kind']=='container' or id in owner or id in deferred:continue
        rt=route(id);st=make(id,'content' if bbox(id) else 'unlocated_unit',rt)
        if rt=='notes':st['warnings'].append(warning('note_association_not_resolved'))
        st['_box']=normalized(id);st['_text']=r['original_record'].get('text','')
        if r['classification']['function']['value'] is None:
            st['warnings'].append(warning('routing_provisional'));st['routing_alternatives']=copy.deepcopy(r['classification']['function']['candidates'])
        if not bbox(id):st['warnings'].append(warning('unlocated_unit'));st['order_basis']='fallback'
        owner[id]=st['id'];inventory[id].update(disposition='content' if bbox(id) else 'unlocated_reference',route=rt,appearance_ref=st['id']);capsules.append(st)
    constraints=[]
    for p in classified['pages']:
        for rel in p.get('original_relations',[]):
            if rel.get('type') in ('precedes','reading_order_precedes') and rel.get('from') in units and rel.get('to') in units:
                constraints.append(copy.deepcopy(rel))
    top_for={}
    for st in capsules:
        top_for[st['unit_ref']]=st['id']
        for child in st['children']:
            visit=steps[child]
            if visit['kind']!='reference':top_for[visit['unit_ref']]=st['id']
    routes={rt:dict(sequence=[],expanded_sequence=[]) for rt in ROUTES};routes['pending_structures']['unit_refs']=sorted(set(pending))
    for rt in ROUTES[:-1]:
        for n in sorted(pages):
            batch=[s for s in capsules if s['route']==rt and s['page']==n]
            if not batch:continue
            l=xy_order([dict(id=s['id'],box=s['_box'],text=s.get('_text','')) for s in batch])
            layouts.append(dict(page=n,route=rt,tree=l['tree'],alternatives=l['alternatives']))
            explicit=[]
            for c in constraints:
                a,b=top_for.get(c['from']),top_for.get(c['to'])
                if a in l['order'] and b in l['order'] and a!=b and c.get('status') in USABLE:explicit.append(dict(**{'from':a,'to':b},basis='retained_precedence',original_relation=c))
            ordered,active,rejected=graph_order(l['order'],explicit)
            suspended.extend(dict(page=n,route=rt,**r) for r in rejected)
            for a in active:
                if blocked(n):continue
                isfallback=a['basis']=='geometry_proposal' and (a['from'] in l['fallback_ids'] or a['to'] in l['fallback_ids'] or rejected)
                relations.append(dict(type='precedes',scope='steps',**a,status='fallback' if isfallback else 'proposal'))
            for id in ordered:
                st=steps[id]
                if id in l['fallback_ids'] or blocked(n) or rejected:
                    st['order_basis']='fallback';st['warnings'].append(warning('layout_or_constraint_fallback'))
                routes[rt]['sequence'].append(id);routes[rt]['expanded_sequence'].extend([id]+st['children'])
    positions={rt:{steps[id]['unit_ref']:i for i,id in enumerate(route['expanded_sequence']) if steps[id]['kind']!='reference'} for rt,route in routes.items()}
    for c in constraints:
        a,b=c['from'],c['to'];common=next((rt for rt,pos in positions.items() if a in pos and b in pos),None)
        if not common or positions[common][a]>=positions[common][b]:
            suspended.append(dict(edge=c,reason='retained_precedence_incompatible_with_physical_or_internal_policy'))
    for root in capsules:
        if root['order_basis']=='fallback':
            for child in root['children']:
                st=steps[child];st['internal_order_basis']=st['order_basis'];st['order_basis']='fallback'
                st['warnings'].append(warning('outer_order_provisional'))
    for rt,route in routes.items():
        for a,b in zip(route['expanded_sequence'],route['expanded_sequence'][1:]):
            fallback=steps[a]['order_basis']=='fallback' or steps[b]['order_basis']=='fallback' or steps[a]['evidence_status']=='abstained' or steps[b]['evidence_status']=='abstained'
            relations.append(dict(type='next_in_route',scope='steps',**{'from':a,'to':b},route=rt,status='fallback' if fallback else 'proposal'))
    # Language cues only propose continuity at column/page transitions; no text edits.
    mainvisits=[steps[x] for x in routes['main']['expanded_sequence']]
    eligible=[]
    for i,s in enumerate(mainvisits):
        r=regions.get(s['unit_ref'])
        if s['kind']=='content' and r and r['original_record'].get('native_type')=='text' and r['classification']['category']['value']=='text':eligible.append((i,s,r))
    continuity=[]
    for (ia,a,ra),(ib,b,rb) in zip(eligible,eligible[1:]):
        ba,bb=normalized(ra['id']),normalized(rb['id']);pa,pb=ra['page'],rb['page']
        transition=pa!=pb or (ba and bb and abs((ba[0]+ba[2]-bb[0]-bb[2])/2)>CONFIG['column_transition_dx'] and ba[3]>bb[1])
        if not transition:continue
        between=mainvisits[ia+1:ib]
        deferred_barrier=any(s['kind'] in ('deferred_structure','unlocated_unit') for s in between)
        barrier=any(s.get('role') not in ('caption','visual_body') for s in between if s['kind'] not in ('group','visual_structure','reference'))
        ta=ra['original_record'].get('text','').strip();tb=rb['original_record'].get('text','').strip()
        abstained=any(blocked(n) for n in pages if pa<=n<=pb)
        status='blocked_deferred' if abstained or deferred_barrier or not ba or not bb else 'candidate_ambiguous'
        cues=[]
        if ta and tb and status!='blocked_deferred' and not barrier:
            if re.search(r'[A-Za-z]-$',ta):cues.append('trailing_hyphen')
            elif not re.search(r'[.!?:;]\s*$',ta) and tb[0].islower():cues.append('open_clause_lowercase_start')
            if cues and pb-pa in (0,1):status='candidate_supported'
        rel=dict(type='paragraph_continues',scope='units',**{'from':ra['id'],'to':rb['id']},status=status,
                 rule='geometry_and_lexical_transition_v1',evidence_refs=[ra['id'],rb['id']],cues=cues,
                 warnings=[warning('paragraph_continuation_unvalidated')])
        relations.append(rel);continuity.append(rel)
    for s in steps.values():
        s.pop('_box',None);s.pop('_text',None)
        if s['evidence_status']=='abstained':s['order_basis']='fallback'
    if any(v['disposition'] is None for v in inventory.values()):raise ValueError('unaccounted units')
    appearances=[s['unit_ref'] for s in steps.values() if s['kind']=='content']
    if len(appearances)!=len(set(appearances)):raise ValueError('duplicate content')
    if set(appearances)&deferred:raise ValueError('deferred children ordered')
    geometry_eligible=sum(r['structural_kind']!='container' and id not in deferred and bbox(id) is not None for id,r in regions.items())
    geometry_proposed=sum(s['kind']=='content' and s['evidence_status']=='proposal' and s['order_basis']!='fallback' for s in steps.values())
    metrics=dict(inventory_units=len(inventory),regions=len(regions),logical_groups=len(groups),accounted_units=len(inventory),accounting_coverage=1.0,
                 content_appearances=len(appearances),structural_placeholders=sum(s['kind']=='deferred_structure' for s in steps.values()),deferred_child_references=len(deferred),
                 fallback_steps=sum(s['order_basis']=='fallback' for s in steps.values()),steps_with_warnings=sum(bool(s['warnings']) for s in steps.values()),
                 suspended_constraints=len(suspended),continuity_candidates=dict(Counter(r['status'] for r in continuity)),duplicate_content=0,operational_cycles=0)
    metrics.update(geometry_eligible_content_units=geometry_eligible,content_positions_with_proposal=geometry_proposed,
                   content_positions_fallback=sum(s['kind']=='content' and s['order_basis']=='fallback' for s in steps.values()),
                   geometry_proposal_coverage=geometry_proposed/geometry_eligible if geometry_eligible else None,
                   geometry_abstained_content=sum(s['kind']=='content' and s['evidence_status']=='abstained' for s in steps.values()))
    return dict(schema_version=VERSION,paper_id=classified['paper_id'],document=classified['document'],status='provisional_complete_with_warnings',
                policy=dict(global_order='physical_layout',visual_internal_order='caption_first',direction='ltr_assumed',human_review='after_full_mvp'),config=copy.deepcopy(CONFIG),
                inventory=list(inventory.values()),steps=list(steps.values()),routes=routes,relations=relations,layouts=layouts,decisions=decisions,suspended_constraints=suspended,
                original_page_context=copy.deepcopy(classified['pages']),metrics=metrics,
                warnings=[warning('direction_and_semantic_order_not_independently_validated')],
                validation=dict(semantic='pending_after_full_mvp',human_action_required_now=False,original_classification_unchanged=True))
