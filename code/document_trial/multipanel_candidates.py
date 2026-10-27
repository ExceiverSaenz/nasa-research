"""Frozen offline candidate rule v1. Never accepts relations or imports models."""
import copy
import math
import re
import hashlib
import json
from pathlib import Path

THRESHOLD=0.90


def valid(b,w,h):
    return (isinstance(b,list) and len(b)==4 and
            all(isinstance(v,(int,float)) and math.isfinite(v) for v in b) and
            0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h)


def coverage(body,anchor):
    area=max(0,min(body[2],anchor[2])-max(body[0],anchor[0]))*max(0,min(body[3],anchor[3])-max(body[1],anchor[1]))
    return area/((body[2]-body[0])*(body[3]-body[1]))


def native_text(value):
    if isinstance(value,str):return value
    if isinstance(value,list):return ' '.join(native_text(v) for v in value)
    if isinstance(value,dict):return native_text(value.get('content',''))
    return ''


def ref(s):
    return dict(id=s['id'],local_id=s['local_id'],source_pointer=s['source_pointer'])


def parent(s):
    return s['source_pointer'].rsplit('/content/',1)[0]


def generate(result,expected_identity):
    out=dict(schema_version='multipanel-candidates/1',identity=copy.deepcopy(result['identity']),
             rule=dict(version='v1',coverage=THRESHOLD),status='completed',candidates=[],diagnostics=[],
             external_evidence=copy.deepcopy(result['evidence']),accepted=False)
    def abort(reason):
        out.update(status='abstained',diagnostics=[reason]);return out
    if result['identity']!=expected_identity:return abort('identity_mismatch')
    i=result['identity'];w=i['width_px'];h=i['height_px']
    if i['geometry']['coordinate_system']!={'unit':'pixel','origin':'top-left','bbox_format':'xyxy'}:
        return abort('coordinate_frame_mismatch')
    segments=result['segments']
    if len({s['id'] for s in segments})!=len(segments):return abort('duplicate_ids')
    prefix=i['document_sha256']+':'+i['execution_id']+':p'+str(i['physical_page'])+':'
    if any(s['id']!=prefix+s['local_id'] or not s.get('source_pointer') for s in segments):return abort('invalid_reference_identity')
    if any(not valid(s.get('bbox'),w,h) for s in segments):return abort('invalid_native_geometry')
    lm=[e for e in result['evidence'] if e['model']=='layoutlmv3']
    if any(not valid(e['native_record'].get('bbox'),w,h) for e in lm):return abort('invalid_anchor_geometry')
    bodies=[s for s in segments if s['native_content']['type'] in ('chart_body','image_body')]
    caps=[s for s in segments if s['native_content']['type'] in ('chart_caption','image_caption')]
    texts=[e for e in lm if e['native_record']['type']=='text']
    for anchor in (e for e in lm if e['native_record']['type']=='figure'):
        box=anchor['native_record']['bbox'];members=[];border=[]
        for s in bodies:
            cov=coverage(s['bbox'],box)
            if cov>0:
                record=dict(**ref(s),coverage=cov)
                (members if cov>=THRESHOLD else border).append(record)
        member_ids={m['id'] for m in members}
        parents={parent(s) for s in bodies if s['id'] in member_ids}
        captions=[]
        for s in caps:
            text=native_text(s['native_content'])
            match=re.search(r'\b(?:Fig\.?|Figure)\s*\d+\b',text,re.I)
            if parent(s) in parents and match:
                captions.append(dict(**ref(s),literal=match.group(),native_text=text,
                    lm_text_support=[e['id'] for e in texts if coverage(s['bbox'],e['native_record']['bbox'])>=THRESHOLD]))
        caption_ids={c['id'] for c in captions}
        interference=[]
        for s in segments:
            if s['id'] not in member_ids|caption_ids and s not in bodies and coverage(s['bbox'],box)>0:
                interference.append(dict(**ref(s),coverage=coverage(s['bbox'],box)))
        reasons=[]
        if border:reasons.append('borderline_members')
        if interference:reasons.append('context_overlap')
        if len(captions)>1:reasons.append('multiple_captions')
        if len(members)<2 or len(parents)<2:
            status='review_required' if border else 'single_body_no_group'
        elif not captions:status='abstained';reasons.append('no_supported_caption')
        else:status='review_required' if reasons else 'candidate'
        candidate=dict(anchors=[anchor['id']],members=members,borderline_members=border,
            captions=captions,context_overlap=interference,status=status,reasons=reasons,
            accepted=False,review_status='pending_human_validation')
        key=lambda c:(tuple(sorted(m['id'] for m in c['members'])),tuple(sorted(ca['id'] for ca in c['captions'])))
        same=next((c for c in out['candidates'] if key(c)==key(candidate) and c['borderline_members']==border and c['context_overlap']==interference),None)
        if same:same['anchors'].append(anchor['id'])
        else:out['candidates'].append(candidate)
    for c in out['candidates']:
        ids={m['id'] for m in c['members']}
        if any(other is not c and ids&{m['id'] for m in other['members']} for other in out['candidates']):
            c['reasons'].append('shared_members_between_anchors')
            if c['status']!='abstained':c['status']='review_required'
    return out


def export(source,manifest_path,destination):
    """Export one new immutable sidecar; source manifest provides expected identity."""
    source=Path(source);manifest_path=Path(manifest_path);destination=Path(destination)
    raw=source.read_bytes();meta=manifest_path.read_bytes()
    result=generate(json.loads(raw),json.loads(meta)['identity'])
    result['provenance']=dict(baseline_sha256=hashlib.sha256(raw).hexdigest(),
                             source_manifest_sha256=hashlib.sha256(meta).hexdigest())
    payload=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if destination.exists():
        if destination.read_bytes()!=payload:raise ValueError('Incompatible output; never overwrite')
    else:
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(payload)
    return result
