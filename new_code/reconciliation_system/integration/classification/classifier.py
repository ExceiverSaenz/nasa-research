"""Pure rule-based functional classification; never runs parsers or models."""
import copy
import math
import re
import unicodedata
from collections import defaultdict

VERSION = 'functional-classification/1'
CONFIG = dict(caption_max_tokens=80, short_title_tokens=20, title_max_chars=180,
              max_vertical_gap=.06, min_horizontal_overlap=.5, metadata_max_y=.45,
              title_max_height=.08, margin_band=.12, recurrence_pages=3,
              recurrence_position_tolerance=.03, mutual_coverage=.90)
MAP = {
    'mineru': {'text':'text','ref_text':'text','page_footnote':'text','table_footnote':'text',
              'image_footnote':'text','list':'text','index':'text','doc_title':'title',
              'paragraph_title':'title','chart':'figure','chart_body':'figure','image':'figure',
              'image_body':'figure','table':'table','table_body':'table','table_caption':'caption',
              'chart_caption':'caption','image_caption':'caption','equation':'equation',
              'header':'margin','footer':'margin','page_number':'margin'},
    'layoutlmv3': {'text':'text','list':'text','title':'title','figure':'figure','table':'table'},
    'table_transformer': {'table':'table','table rotated':'table','rotated table':'table'}}
CAPTION = re.compile(r'^(fig(?:ure)?\.?|figura|table|tabla)\s*\d+[A-Za-z]?\b',re.I)
SECTION = re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+\S|abstract\b|introduction\b|conclusions?\b|references\b|acknowledg(?:e)?ments?\b|resumen\b|referencias\b)',re.I)
METADATA = re.compile(r'(?:\bdoi\s*:|https?://(?:dx\.)?doi\.org/|\b10\.\d{4,9}/\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b(?:received|accepted|available online|corresponding author|authors?|affiliations?|university|universidad|institute|department of)\b)',re.I)
LIST = re.compile(r'^\s*(?:[-•*]|\(?\d+[.)]|[a-z][.)])\s+\S',re.I)


def norm(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def box(record, identity):
    b=record.get('bbox'); w=identity.get('width_px'); h=identity.get('height_px')
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in (w,h)):
        return None
    if not isinstance(b,list) or len(b)!=4 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in b):
        return None
    if not (0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h): return None
    return [b[0]/w,b[1]/h,b[2]/w,b[3]/h]


def horizontal(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))/min(a[2]-a[0],b[2]-b[0])


def coverage(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))/((a[2]-a[0])*(a[3]-a[1]))


def dimension(candidates,status='automatic_rule'):
    values=sorted(set(candidates))
    return dict(value=values[0] if len(values)==1 else None,
                candidates=values,status=status if len(values)==1 else 'abstained')


def classify_document(document):
    """Return an additive per-paper sidecar; original records are deep copied."""
    entries=[]; seen=set()
    for page in document['pages']:
        ident=page['identity']
        for r in page['records']:
            if r['id'] in seen: raise ValueError('duplicate record id')
            seen.add(r['id'])
            entries.append(dict(record=r,page=page,number=ident['physical_page'],
                                b=box(r,ident),category=MAP.get(r['parser'],{}).get(r['native_type'],'other')))
    entries.sort(key=lambda e:(e['number'],e['record']['id']))
    bypage=defaultdict(list); recurring=defaultdict(list)
    for e in entries:
        bypage[e['number']].append(e)
        r=e['record']; b=e['b']; text=norm(r.get('text',''))
        if b and text and r.get('role')!='container':
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
                if ar['parser']==br['parser'] or not a['b'] or not b['b'] or 'container' in (ar.get('role'),br.get('role')): continue
                if min(coverage(a['b'],b['b']),coverage(b['b'],a['b']))<CONFIG['mutual_coverage']: continue
                coarse=any(x['record']['parser']=='layoutlmv3' and x['category']=='text' and y['category'] in ('caption','equation','margin') for x,y in ((a,b),(b,a)))
                if a['category']!=b['category'] and 'other' not in (a['category'],b['category']) and not coarse:
                    conflicts[ar['id']].append(b); conflicts[br['id']].append(a)
    regions=[]; queue=[]
    for e in entries:
        r=e['record']; b=e['b']; cat=e['category']; nt=r['native_type']; text=r.get('text',''); tokens=text.split()
        categories=[cat]; functions=[]; subtypes=[]; rules=['native_mapping-v1']; evidence={r['id']}; warnings=[]
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
        if not iscontainer and b:
            peers=[x for x in bypage[e['number']] if x is not e and x['record'].get('role')!='container' and x['b']]
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
        c=dimension(categories,'native_preserved' if len(set(categories))==1 else 'abstained')
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
