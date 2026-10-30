"""Pure, document-independent conservative integration.reconciliation. No models or network."""
import copy
import itertools
import math
import re

VERSION = 'rules-v1'
THRESHOLD = .90
PARSERS = ('mineru', 'layoutlmv3', 'table_transformer')
MAPPING = {
    'mineru': {'text':'Texto','ref_text':'Texto','page_footnote':'Texto','list':'Texto','index':'Texto',
        'doc_title':'Títulos','paragraph_title':'Títulos','chart_body':'Figuras','image_body':'Figuras',
        'chart':'Figuras','image':'Figuras','table_body':'Tablas','table':'Tablas',
        'table_caption':'Captions','chart_caption':'Captions','image_caption':'Captions',
        'equation':'Ecuaciones','header':'Márgenes','footer':'Márgenes','page_number':'Márgenes'},
    'layoutlmv3': {'text':'Texto','list':'Texto','title':'Títulos','figure':'Figuras','table':'Tablas'},
    'table_transformer': {'table':'Tablas','table rotated':'Tablas','rotated table':'Tablas'}}


def valid_box(b, w, h):
    return (isinstance(b,list) and len(b)==4 and
            all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in b)
            and 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h)


def coverage(a,b):
    area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return area/((a[2]-a[0])*(a[3]-a[1]))


def mutual(a,b):
    return min(coverage(a,b),coverage(b,a))>=THRESHOLD


def normalize(page):
    out=copy.deepcopy(page)
    out.update(schema_version='autonomous-reconciliation/1',rule_version=VERSION,
               threshold=THRESHOLD,objects=[],containers=[],correspondences=[],relations=[],groups=[],decisions=[])
    out['incidents']=list(out.get('incidents',[]))
    out['records']=sorted(out.get('records',[]),key=lambda r:r['id'])
    identity=out.get('identity',{})
    if out.get('adapter')!='canonical-v1':out['incidents'].append('unsupported_adapter')
    if (not isinstance(identity.get('physical_page'),int) or identity['physical_page']<1 or
        any(not re.fullmatch('[0-9a-f]{64}',str(identity.get(k,''))) for k in ('document_sha256','render_sha256')) or
        any(not isinstance(identity.get(k),(int,float)) or not math.isfinite(identity[k]) or identity[k]<=0 for k in ('width_px','height_px'))):
        out['incidents'].append('identity_invalid')
    if len({r['id'] for r in out['records']})!=len(out['records']):out['incidents'].append('duplicate_ids')
    for r in out['records']:
        source=r.get('source',{})
        if not source.get('path') or not source.get('pointer') or not re.fullmatch('[0-9a-f]{64}',source.get('sha256','')):
            out['incidents'].append('source_integrity')
        transform=r.get('transform')
        if not isinstance(transform,list) or len(transform)!=6 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in transform):
            out['incidents'].append('unknown_transform')
        r['category']=MAPPING.get(r['parser'],{}).get(r['native_type'],'Otros')
        r['subtype']=r['native_type']
        r['classification_status']='native_preserved'
        r['classification_reason']='native_mapping' if r['native_type'] in MAPPING.get(r['parser'],{}) else 'unknown_native_class'
        r['geometry_status']='native_unchanged'
        if not valid_box(r.get('bbox'),identity.get('width_px',0),identity.get('height_px',0)):
            r['geometry_status']='invalid';out['incidents'].append('invalid_geometry')
        if r['parser']=='mineru' and out.get('parsers',{}).get('mineru')=='completed':
            out['containers' if r.get('role')=='container' else 'objects'].append(r['id'])
        if r.get('parent'):
            out['relations'].append(dict(type='native_parent_child',parent=r['parent'],child=r['id'],status='native_preserved'))
    out['incidents']=sorted(set(out['incidents']))
    fatal={'identity_invalid','duplicate_ids','unsupported_adapter','source_integrity','identity_mismatch'}
    out['status']='blocked' if fatal.intersection(out['incidents']) else ('partial' if out['incidents'] or any(out.get('parsers',{}).get(p)!='completed' for p in PARSERS) else 'completed')
    out['capabilities']={p:dict(categories=sorted(set(MAPPING[p].values())),text=p=='mineru',status=out.get('parsers',{}).get(p,'missing')) for p in PARSERS}
    return out


def compatible(a,b):
    return a['category']==b['category'] and a['category']!='Otros'


def coarse(a,b):
    return any(x['parser']=='layoutlmv3' and x['native_type']=='text' and y['category'] in ('Captions','Ecuaciones','Márgenes') for x,y in ((a,b),(b,a)))


def reconcile(page):
    out=normalize(page)
    if out['status']=='blocked' or 'invalid_geometry' in out['incidents'] or 'unknown_transform' in out['incidents']:
        return out
    records=out['records'];segments=[r for r in records if r.get('role')!='container' and out.get('parsers',{}).get(r['parser'])=='completed']
    def decision(function, inputs, status, reason, **extra):
        out['decisions'].append(dict(function=function,inputs=sorted(inputs),status=status,reason=reason,rule=VERSION,**extra))
    for pair in itertools.combinations(PARSERS,2):
        matches=[]
        for a in (r for r in segments if r['parser']==pair[0]):
            for b in (r for r in segments if r['parser']==pair[1]):
                ca,cb=coverage(a['bbox'],b['bbox']),coverage(b['bbox'],a['bbox'])
                if not ca:continue
                if min(ca,cb)>=THRESHOLD:
                    if compatible(a,b):matches.append((a,b,ca,cb))
                    else:decision('classification',[a['id'],b['id']],'native_preserved' if coarse(a,b) else 'abstained',
                                  'coarse_class_support' if coarse(a,b) else 'class_conflict',categories=[a['category'],b['category']])
                else:decision('correspondence',[a['id'],b['id']],'abstained','partial_overlap',coverage=[ca,cb])
        for a,b,ca,cb in matches:
            unique=sum(x['id']==a['id'] for x,_,_,_ in matches)==1 and sum(y['id']==b['id'] for _,y,_,_ in matches)==1
            decision('correspondence',[a['id'],b['id']],'automatic_rule' if unique else 'abstained',
                     'unique_mutual_coverage' if unique else 'non_unique',coverage=[ca,cb])
            if unique:out['correspondences'].append(dict(type='geometric_correspondence',sources=[a['id'],b['id']],status='automatic_rule',rule=VERSION))
    bodies=[r for r in segments if r['parser']=='mineru' and r['native_type'] in ('chart_body','image_body')]
    captions=[r for r in segments if r['parser']=='mineru' and r['native_type'] in ('chart_caption','image_caption')]
    natives=[r for r in segments if r['parser']=='mineru']
    proposals=[]
    for anchor in (r for r in segments if r['parser']=='layoutlmv3' and r['native_type']=='figure'):
        members=[r for r in bodies if coverage(r['bbox'],anchor['bbox'])>=THRESHOLD]
        border=[r for r in bodies if 0<coverage(r['bbox'],anchor['bbox'])<THRESHOLD]
        parents={r['parent'] for r in members if r.get('parent')}
        caps=[r for r in captions if r.get('parent') in parents]
        allowed={r['id'] for r in members+caps}
        interference=[r for r in natives if r['id'] not in allowed and r not in bodies and coverage(r['bbox'],anchor['bbox'])>0]
        reasons=[]
        if len(members)<2 or len(parents)<2:reasons.append('single_body_no_group')
        if border:reasons.append('borderline_members')
        if interference:reasons.append('context_overlap')
        if len(caps)!=1:reasons.append('multiple_captions' if caps else 'no_caption')
        elif not re.search(r'\b(?:Fig\.?|Figure)\s*\d+\b',caps[0].get('text',''),re.I):reasons.append('no_recognized_label')
        conflicts=[r['id'] for r in segments if r['parser']!='mineru' and r['id']!=anchor['id'] and
                   r['category'] not in ('Figuras','Otros') and
                   any(mutual(r['bbox'],x['bbox']) and not coarse(r,x) for x in members+[anchor])]
        if conflicts:reasons.append('external_class_conflict')
        key=(tuple(r['id'] for r in members),tuple(r['id'] for r in caps),tuple(reasons),tuple(conflicts))
        previous=next((p for p in proposals if p['key']==key),None)
        if previous:previous['anchors'].append(anchor['id']);continue
        proposals.append(dict(key=key,anchors=[anchor['id']],members=[r['id'] for r in members],
                              caption=caps[0]['id'] if len(caps)==1 else None,reasons=reasons,conflicts=conflicts))
    for p in proposals:
        if any(q is not p and set(p['members'])&set(q['members']) for q in proposals):p['reasons'].append('shared_members_between_groups')
        decision('grouping',p['anchors']+p['members']+([p['caption']] if p['caption'] else []),
                 'abstained' if p['reasons'] else 'automatic_rule',','.join(p['reasons']) or 'supported_multipanel',conflicts=p['conflicts'])
        if p['reasons']:continue
        member_records=[r for r in bodies if r['id'] in p['members']]
        overlap=any(coverage(a['bbox'],b['bbox'])>0 for a,b in itertools.combinations(member_records,2))
        group=dict(id='group:'+':'.join(p['members']),members=p['members'],caption=p['caption'],anchors=p['anchors'],
                   status='automatic_rule',rule=VERSION,warnings=['member_overlap'] if overlap else [])
        out['groups'].append(group)
        out['relations'].append(dict(type='has_caption',parent=group['id'],child=p['caption'],status='automatic_rule',rule=VERSION))
    return out
