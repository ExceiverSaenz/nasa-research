"""Classify only declared reconciliation units; parser detections are evidence."""
import copy
from collections import defaultdict
from .classifier import (CONFIG, MAP, CAPTION, SECTION, METADATA, LIST, box, norm,
                         horizontal, coverage, dimension)
import re

VERSION = 'functional-classification-reconciled/2'
RETAINED = {'Texto':'text','Títulos':'title','Figuras':'figure','Tablas':'table',
            'Captions':'caption','Ecuaciones':'equation','Márgenes':'margin','Otros':'other'}


def warning(classification, code):
    if code not in [w['code'] for w in classification['warnings']]:
        classification['warnings'].append(dict(code=code,message='Requiere validación humana',review_stage='after_full_mvp'))
    classification['requires_human_validation']=True


def classify_reconciled_document(document):
    """Declared objects/containers only; retained classes seed every decision."""
    selected=copy.deepcopy(document); allids=set(); external=[]; page_indexes={}
    for old,page in zip(document['pages'],selected['pages']):
        refs=old.get('objects',[])+old.get('containers',[])
        records={r['id']:r for r in old['records']}
        if len(records)!=len(old['records']) or len(set(refs))!=len(refs) or not set(refs)<=set(records):
            raise ValueError('invalid or duplicate reconciled selection')
        if set(records)&allids: raise ValueError('duplicate source ids across pages')
        allids.update(records)
        page['records']=[copy.deepcopy(records[rid]) for rid in refs]
        external.extend(dict(id=r['id'],page=old['identity']['physical_page'],original_record=copy.deepcopy(r))
                        for r in old['records'] if r['id'] not in set(refs))
        page_indexes[old['identity']['physical_page']]=(old,records,set(refs))
    result=_classify_selected(selected)
    byid={r['id']:r for r in result['regions']}
    groupids=set()
    for page in document['pages']:
        for g in page.get('groups',[]):
            if g['id'] in groupids or g['id'] in allids: raise ValueError('duplicate group id')
            groupids.add(g['id'])
            _,_,refs=page_indexes[page['identity']['physical_page']]
            if not g.get('members') or len(set(g['members']))!=len(g['members']) or not set(g['members'])<=refs or g.get('caption') not in refs:
                raise ValueError('group references outside reconciled selection')
    for r in result['regions']:
        page,records,refs=page_indexes[r['page']]; original=r['original_record']; c=r['classification']
        c['retained_classification']={k:copy.deepcopy(original.get(k)) for k in ('category','classification_status','classification_reason','subtype')}
        candidates=list(c['category']['candidates'])
        native=MAP.get(original['parser'],{}).get(original['native_type'],'other')
        retained=RETAINED.get(original.get('category'),'other')
        # Historical Others remains an explicit candidate, including mapped footnotes.
        if native!=retained:
            candidates.append(native);warning(c,'retained_native_category_disagreement')
        if original.get('category') not in RETAINED:warning(c,'unknown_retained_category')
        evidence=[]
        rb=box(original,page['identity'])
        eligible=page.get('status')!='blocked' and 'invalid_geometry' not in page.get('incidents',[]) and page.get('parsers',{}).get(original['parser'])=='completed'
        if rb and eligible and original.get('role')!='container':
            for other in records.values():
                if other['id'] in refs or other['parser']==original['parser'] or other.get('role')=='container' or page.get('parsers',{}).get(other['parser'])!='completed':continue
                ob=box(other,page['identity'])
                if not ob or min(coverage(rb,ob),coverage(ob,rb))<CONFIG['mutual_coverage']:continue
                oc=RETAINED.get(other.get('category'),'other')
                coarse=other['parser']=='layoutlmv3' and oc=='text' and retained in ('caption','equation','margin')
                kind='coarse_support' if coarse else ('category_support' if oc==retained else 'category_conflict')
                evidence.append(dict(record_ref=other['id'],kind=kind,retained_source_category=other.get('category'),native_type=other['native_type']))
                c['evidence_refs'].append(other['id'])
                if not coarse and oc!=retained and oc!='other':
                    candidates.append(oc);warning(c,'parser_evidence_category_conflict')
        c['parser_evidence']=evidence
        c['category']=dimension(candidates,'reconciled_preserved')
        if c['category']['status']=='abstained':warning(c,'category_ambiguous')
        if evidence:c['rule_refs'].append('external_parser_evidence-v2')
        if original.get('classification_status') in ('abstained','not_evaluable','not_supported'):
            c['category'].update(value=None,status='abstained');c['function'].update(value=None,status='abstained')
            warning(c,'retained_classification_abstention')
        related=[]
        for i,decision in enumerate(page.get('decisions',[])):
            if r['id'] in decision.get('inputs',[]): related.append(dict(page=r['page'],decision_index=i,status=decision.get('status'),function=decision.get('function'),reason=decision.get('reason')))
        c['reconciliation_decision_refs']=related
        r['member_of']=[g['id'] for g in page.get('groups',[]) if r['id'] in g['members']]
        associated=[rel for rel in page.get('relations',[]) if rel.get('type')=='has_caption' and rel.get('child')==r['id']]
        if associated and not (original.get('role')=='container'):
            funcs=[f for f in c['function']['candidates'] if f!='main_body']+['associated_content']
            newf=dimension(funcs)
            if not eligible or not rb or original.get('classification_status') in ('abstained','not_evaluable','not_supported'):
                newf.update(value=None,status='abstained')
            c['function']=newf;c['rule_refs'].append('retained_caption_relation-v2')
            c['retained_associations']=copy.deepcopy(associated)
        c['evidence_refs']=sorted(set(c['evidence_refs']));c['rule_refs']=sorted(set(c['rule_refs']))
    logical=[]
    for page in document['pages']:
        for g in page.get('groups',[]):
            member=[byid[rid] for rid in g['members']]
            cats=[x for r in member for x in r['classification']['category']['candidates']]
            c=dict(category=dimension(cats,'reconciled_group_derived'),function=dimension(['associated_content']),
                   subtype=dimension(['multipanel_group']),rule_version=VERSION,
                   rule_refs=['retained_group_membership-v2'],evidence_refs=sorted(set(g['members']+[g['caption']]+g.get('anchors',[]))),
                   retained_classification=dict(group_status=g.get('status'),member_categories={r['id']:r['original_record'].get('category') for r in member}),
                   warnings=[],requires_human_validation=False,semantic_validation='pending_after_full_mvp')
            if c['category']['value'] not in ('figure','table') or any(r['classification']['category']['value'] is None for r in member):
                c['category'].update(value=None,status='abstained');warning(c,'group_category_ambiguous')
            for w in g.get('warnings',[]):warning(c,'retained_group_'+w)
            if any(r['classification']['requires_human_validation'] for r in member):warning(c,'member_validation_pending')
            if any(r['classification']['function']['status']=='abstained' for r in member):
                c['function'].update(value=None,status='abstained');warning(c,'member_function_abstention')
            if g.get('status') in ('abstained','not_evaluable','not_supported'):
                c['category'].update(value=None,status='abstained');c['function'].update(value=None,status='abstained')
                warning(c,'retained_group_abstention')
            logical.append(dict(id=g['id'],page=page['identity']['physical_page'],structural_kind='group',
                                members=copy.deepcopy(g['members']),caption_ref=g['caption'],
                                geometry_refs=copy.deepcopy(g['members']),original_group=copy.deepcopy(g),classification=c))
    for outpage in result['pages']:
        old=page_indexes[outpage['identity']['physical_page']][0]
        outpage['original_decisions']=copy.deepcopy(old.get('decisions',[]))
        outpage['original_correspondences']=copy.deepcopy(old.get('correspondences',[]))
        outpage['original_parsers']=copy.deepcopy(old.get('parsers',{}))
        outpage['original_page_metadata']={k:copy.deepcopy(v) for k,v in old.items() if k not in ('records','objects','containers','relations','groups','decisions','correspondences')}
    result.update(classification_scope='reconciled_units_only',evidence_records=sorted(external,key=lambda x:x['id']),logical_units=logical)
    result['reconciliation_metadata']={k:copy.deepcopy(v) for k,v in document.items() if k!='pages'}
    result['metadata']={}
    for r in result['regions']:
        c=r['classification']
        if 'metadata' in c['function']['candidates']:result['metadata'].setdefault(c['subtype']['value'] or 'unresolved',[]).append(r['id'])
    result['review_queue']=[dict(unit_ref=r['id'],page=r['page'],**w) for r in result['regions']+logical for w in r['classification']['warnings']]
    return result

def _classify_selected(document):
    """Return an additive per-paper sidecar; original records are deep copied."""
    entries=[]; seen=set()
    for page in document['pages']:
        ident=page['identity']
        for r in page['records']:
            if r['id'] in seen: raise ValueError('duplicate record id')
            seen.add(r['id'])
            entries.append(dict(record=r,page=page,number=ident['physical_page'],
                                b=box(r,ident),category=RETAINED.get(r.get('category'),'other'),
                                eligible=page.get('parsers',{}).get(r['parser'])=='completed' and page.get('status')!='blocked' and 'invalid_geometry' not in page.get('incidents',[])))
    entries.sort(key=lambda e:(e['number'],e['record']['id']))
    bypage=defaultdict(list); recurring=defaultdict(list)
    for e in entries:
        bypage[e['number']].append(e)
        r=e['record']; b=e['b']; text=norm(r.get('text',''))
        if e['eligible'] and b and text and r.get('role')!='container':
            band='top' if b[3]<=CONFIG['margin_band'] else ('bottom' if b[1]>=1-CONFIG['margin_band'] else None)
            if band:
                # Only explicit page-number labels may generalize variable digits.
                keytext=re.sub(r'\d+','#',text) if r['native_type']=='page_number' else text
                recurring[(r['parser'],band,keytext)].append(e)
    repeated={}
    for group in recurring.values():
        for e in group:
            b=e['b']; tol=CONFIG['recurrence_position_tolerance']
            matches=[x for x in group if abs((x['b'][0]+x['b'][2]-b[0]-b[2])/2)<=tol and abs((x['b'][1]+x['b'][3]-b[1]-b[3])/2)<=tol]
            if len({x['number'] for x in matches})>=CONFIG['recurrence_pages']:
                repeated[e['record']['id']]=sorted(x['record']['id'] for x in matches)
    conflicts=defaultdict(list)
    for group in bypage.values():
        for i,a in enumerate(group):
            for b in group[i+1:]:
                ar,br=a['record'],b['record']
                if not a['eligible'] or not b['eligible']:continue
                if ar['parser']==br['parser'] or not a['b'] or not b['b'] or 'container' in (ar.get('role'),br.get('role')): continue
                if min(coverage(a['b'],b['b']),coverage(b['b'],a['b']))<CONFIG['mutual_coverage']: continue
                coarse=any(x['record']['parser']=='layoutlmv3' and x['category']=='text' and y['category'] in ('caption','equation','margin') for x,y in ((a,b),(b,a)))
                if a['category']!=b['category'] and 'other' not in (a['category'],b['category']) and not coarse:
                    conflicts[ar['id']].append(b); conflicts[br['id']].append(a)
    regions=[]; queue=[]
    for e in entries:
        r=e['record']; b=e['b']; cat=e['category']; nt=r['native_type']; text=r.get('text',''); tokens=text.split()
        categories=[cat]; functions=[]; subtypes=[]; rules=['retained_category_seed-v2']; evidence={r['id']}; warnings=[]
        features=dict(relative_bbox=b,token_count=len(tokens),line_count=len(text.splitlines()))
        def warn(code):
            if code not in [w['code'] for w in warnings]:
                warnings.append(dict(code=code,message='Requiere validación humana',review_stage='after_full_mvp'))
        if cat=='other': warn('unknown_native_class')
        iscontainer=r.get('role')=='container'
        if iscontainer:
            rules.append('container_preserved-v1'); warn('container_function_unresolved')
        elif nt=='ref_text': functions=['main_body']; subtypes=['bibliographic_reference']
        elif nt in ('page_footnote','table_footnote','image_footnote'):
            functions=['associated_content']; subtypes=[nt]
        elif cat=='caption':
            functions=['associated_content']; subtypes=['label_and_description' if CAPTION.match(text.strip()) else 'native_caption']
        elif cat in ('figure','table'): functions=['associated_content']
        elif cat=='equation': functions=['main_body']; subtypes=['display_equation']
        elif cat=='margin': functions=['navigation']; subtypes=[nt]
        elif nt=='doc_title': functions=['metadata']; subtypes=['paper_title']
        elif nt=='paragraph_title': subtypes=['section_heading_candidate']
        elif cat=='text': functions=['main_body']; subtypes=['paragraph_candidate']
        if not iscontainer and b and e['eligible']:
            peers=[x for x in bypage[e['number']] if x is not e and x['eligible'] and x['record'].get('role')!='container' and x['b']]
            following=[x for x in peers if x['category']=='text' and 0<=x['b'][1]-b[3]<=CONFIG['max_vertical_gap'] and horizontal(b,x['b'])>=CONFIG['min_horizontal_overlap']]
            if cat in ('text','title') and len(tokens)<=CONFIG['short_title_tokens'] and len(text)<=CONFIG['title_max_chars'] and b[3]-b[1]<=CONFIG['title_max_height'] and SECTION.match(text.strip()) and following:
                categories.append('title'); functions.append('main_body'); subtypes.append('section_heading_candidate')
                rules.append('section_geometry_lexical-v1'); evidence.update(x['record']['id'] for x in following)
            if CAPTION.match(text.strip()) and len(tokens)<=CONFIG['caption_max_tokens']:
                expected='table' if text.strip().lower().startswith(('table','tabla')) else 'figure'
                nearby=[x for x in peers if x['category']==expected and horizontal(b,x['b'])>=CONFIG['min_horizontal_overlap'] and min(abs(b[1]-x['b'][3]),abs(x['b'][1]-b[3]))<=CONFIG['max_vertical_gap']]
                if nearby:
                    categories.append('caption'); functions.append('associated_content'); subtypes.append('caption_candidate')
                    rules.append('caption_geometry_lexical-v1'); evidence.update(x['record']['id'] for x in nearby)
                    # Generic paragraph is a fallback, not a contradiction to a well-formed caption.
                    if cat=='text': functions=[f for f in functions if f!='main_body']; subtypes=[s for s in subtypes if s!='paragraph_candidate']
            if cat=='text' and nt not in ('ref_text','page_footnote','table_footnote','image_footnote') and e['number']==1 and (b[1]+b[3])/2<=CONFIG['metadata_max_y'] and len(tokens)<=80 and METADATA.search(text):
                functions=[f for f in functions if f!='main_body']+['metadata']; subtypes=[s for s in subtypes if s!='paragraph_candidate']+['metadata_candidate']
                rules.append('metadata_context_lexical-v1')
            if cat=='figure' and e['number']==1 and b[3]<=.20 and b[2]-b[0]<=.25 and b[3]-b[1]<=.12:
                siblings=[x for x in bypage[e['number']] if x['category']=='caption' and r.get('parent') and x['record'].get('parent')==r['parent']]
                if not siblings:
                    functions.append('editorial'); subtypes.append('publisher_asset_candidate'); rules.append('small_editorial_asset-v1'); warn('editorial_asset_unconfirmed')
        if not iscontainer and r['id'] in repeated:
            functions=[f for f in functions if f!='main_body']+['navigation']; subtypes.append('recurring_margin_candidate')
            rules.append('document_recurrence-v1'); evidence.update(repeated[r['id']])
            if cat not in ('text','margin'): warn('recurrence_function_conflict')
        if not iscontainer and cat=='text':
            if sum(bool(LIST.match(line)) for line in text.splitlines())>=2:
                subtypes=[s for s in subtypes if s!='paragraph_candidate']+['list_candidate']; rules.append('multiline_list-v1')
            elif nt in ('list','index'):
                subtypes=[s for s in subtypes if s!='paragraph_candidate']+['native_list_structure_unverified']; warn('list_structure_unverified')
        features['math_signal']=bool(re.search(r'[=∑∫√]|\\(?:frac|sum|int)\b',text))
        for other in conflicts[r['id']]:
            categories.append(other['category']); evidence.add(other['record']['id'])
            warn('comparable_parser_category_conflict')
        if conflicts[r['id']]: rules.append('mutual_category_conflict-v1')
        c=dimension(categories,'reconciled_preserved' if len(set(categories))==1 else 'abstained')
        f=dimension(functions)
        # Subtypes refine rather than compete: retain all explanations as candidates.
        s=dimension(subtypes)
        if c['status']=='abstained': warn('category_ambiguous')
        if f['status']=='abstained': warn('function_ambiguous' if functions else 'function_insufficient_evidence')
        if s['status']=='abstained': warn('subtype_unresolved')
        if not b:
            warn('geometry_deferred' if r['parser']=='mineru' and r.get('parent') else 'geometry_invalid')
            f.update(value=None,status='abstained')
        page=e['page']
        if page.get('status')=='blocked' or page.get('parsers',{}).get(r['parser'])!='completed':
            f.update(value=None,status='abstained'); warn('source_not_eligible')
        if 'invalid_geometry' in page.get('incidents',[]):
            f.update(value=None,status='abstained'); warn('inherited_page_geometry_abstention')
        if page.get('incidents'):
            warn('inherited_page_incident')
        classification=dict(category=c,function=f,subtype=s,rule_version=VERSION,rule_refs=sorted(set(rules)),
                            evidence_refs=sorted(evidence),features=features,warnings=warnings,
                            requires_human_validation=bool(warnings),semantic_validation='pending_after_full_mvp')
        regions.append(dict(id=r['id'],page=e['number'],bbox_xyxy=copy.deepcopy(r.get('bbox')),
                            structural_kind='container' if iscontainer else 'region',original_record=copy.deepcopy(r),classification=classification))
        for warning in warnings:
            queue.append(dict(region_ref=r['id'],page=e['number'],**warning))
    metadata=defaultdict(list)
    for r in regions:
        c=r['classification']
        if 'metadata' in c['function']['candidates']:
            metadata[c['subtype']['value'] or 'unresolved'].append(r['id'])
    return dict(schema_version=VERSION,paper_id=document['document_sha256'],document=document['document'],
                rule_config=copy.deepcopy(CONFIG),source_schema=document.get('schema_version'),
                pages=[dict(identity=copy.deepcopy(p['identity']),original_status=p.get('status'),
                            original_incidents=copy.deepcopy(p.get('incidents',[])),
                            region_refs=sorted(r['id'] for r in p['records']),
                            original_objects=copy.deepcopy(p.get('objects',[])),original_containers=copy.deepcopy(p.get('containers',[])),
                            original_relations=copy.deepcopy(p.get('relations',[])),original_groups=copy.deepcopy(p.get('groups',[])))
                       for p in sorted(document['pages'],key=lambda p:p['identity']['physical_page'])],
                regions=regions,metadata=dict(metadata),review_queue=queue,
                reading_order=dict(scope='whole_paper',status='unresolved',resolved_sequence=None),
                validation=dict(technical_contract='pending_export_checks',semantic='pending_after_full_mvp',
                                human_review_required_now=False,original_decisions_unchanged=True))
