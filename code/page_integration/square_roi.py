"""Offline square-canvas preparation and inverse mapping, without OCR imports."""
import argparse
import copy
import io
import json
from pathlib import Path
import zipfile

from .workflow import ROOT,RENDER,REFERENCE,read,save,digest,file_hash
from .header_roi import CODE_FILES,ADAPTER_FILES,ARTIFACTS
from .localized_labels import checked_box
from .trace_observer import POLICY

EXPERIMENT='table1-square-v1'
SQUARE_CODE=CODE_FILES+('square_roi.py','trace_observer.py','remote_square.py')


def square_image(image):
    from PIL import Image
    width,height=image.size;side=max(width,height)
    left=(side-width)//2;top=(side-height)//2
    canvas=Image.new('RGB',(side,side),'white');canvas.paste(image.convert('RGB'),(left,top))
    return canvas,[left,top,side-width-left,side-height-top]


def square_original_box(normalized,transform):
    b=checked_box(normalized,1,1);roi=checked_box(transform['roi_xyxy_px'])
    width,height=transform['canvas_size_px'];left,top,right,bottom=transform['padding_ltrb_px']
    if width-left-right!=roi[2]-roi[0] or height-top-bottom!=roi[3]-roi[1]:raise ValueError('Padding/frame mismatch')
    canvas=[b[0]*width,b[1]*height,b[2]*width,b[3]*height]
    result=[roi[0]+canvas[0]-left,roi[1]+canvas[1]-top,roi[0]+canvas[2]-left,roi[1]+canvas[3]-top]
    inside=canvas[0]>=left and canvas[1]>=top and canvas[2]<=width-right and canvas[3]<=height-bottom
    return dict(bbox=result,canvas_bbox=canvas,inside_content=inside,
                status='content_candidate' if inside else 'padding_or_crossing_candidate_do_not_link',clipped=False)


def allowed_members():
    return ({'page_integration/'+n for n in SQUARE_CODE}|{'mineru_probe/'+n for n in ADAPTER_FILES}|
            set(ARTIFACTS)|{'plan.json','bundle-manifest.json','trace-policy.json','inputs/p0-b2.png'})


def prepare_square(destination):
    from PIL import Image
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    header=ROOT/'code/packages/table1-header-v1'
    protected=read(header/'integrity.json')
    for n,h in protected.items():
        if file_hash(ROOT/n)!=h:raise ValueError('Protected evidence changed: '+n)
    if file_hash(header/'upload.zip')!=(header/'upload.sha256').read_text().strip():raise ValueError('Header source package changed')
    for tree in ('code/packages/table1-header-v1','code/results/table1-header-v1'):
        for p in (ROOT/tree).rglob('*'):
            if p.is_file():protected[p.relative_to(ROOT).as_posix()]=file_hash(p)
    with zipfile.ZipFile(header/'upload.zip') as z:
        blobs={n:z.read(n) for n in z.namelist() if n!='bundle-manifest.json'}
        plan=json.loads(blobs['plan.json'])
        if blobs['plan.json']!=(header/'plan.json').read_bytes():raise ValueError('Frozen header plan differs')
        target=plan['targets'][0]
        source=Image.open(io.BytesIO(blobs['inputs/p0-b2.png'])).convert('RGB')
    original=Image.open(ROOT/RENDER).convert('RGB').crop(target['bbox'])
    if source.size!=(831,76) or source.tobytes()!=original.tobytes():raise ValueError('Original header pixels changed')
    canvas,padding=square_image(source)
    if canvas.size!=(831,831) or padding!=[0,377,0,378]:raise ValueError('Unapproved canvas shape')
    plan=copy.deepcopy(plan);target=plan['targets'][0]
    previous_transform=target['transform']
    target.update(roi_mode='header_square_padding',transform=dict(operation='crop_then_white_square_padding',
        roi_xyxy_px=target['bbox'],origin_px=target['bbox'][:2],roi_size_px=[831,76],
        size_px=[831,831],canvas_size_px=[831,831],padding_ltrb_px=padding,
        inverse='original_x=112+xn*831; original_y=154+yn*831-377',
        chain=[dict(operation='crop',xyxy_px=target['bbox']),dict(operation='white_padding',ltrb_px=padding)],
        previous_transform=previous_transform))
    plan.update(experiment=EXPERIMENT,source_experiment='table1-header-v1',source_plan_sha256=file_hash(header/'plan.json'),
        input_variable='white square padding only; original header pixels/parser/config/weights preserved',trace_policy=POLICY)
    reference=read(ROOT/REFERENCE);local=read(header/'acceptance-local.json')
    if file_hash(ROOT/REFERENCE)!=local['reference_sha256'] or reference['tolerance']!=local['tolerances']:
        raise ValueError('Reference or tolerances changed')
    for name in SQUARE_CODE:blobs['page_integration/'+name]=(Path(__file__).parent/name).read_bytes()
    stream=io.BytesIO();canvas.save(stream,format='PNG',dpi=(200,200));blobs['inputs/p0-b2.png']=stream.getvalue()
    target['input_sha256']=digest(stream.getvalue())
    blobs['plan.json']=json.dumps(plan,ensure_ascii=False,indent=2).encode('utf-8')
    blobs['trace-policy.json']=json.dumps(POLICY,indent=2).encode('utf-8')
    if set(blobs)|{'bundle-manifest.json'}!=allowed_members():raise ValueError('Square allowlist mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    manifest=dict(schema_version='1.0',files={n:dict(bytes=len(raw),sha256=digest(raw)) for n,raw in blobs.items()})
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for n,raw in blobs.items():z.writestr(n,raw)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    (destination/'upload.sha256').write_text(file_hash(destination/'upload.zip')+'\n',encoding='ascii')
    (destination/'plan.json').write_bytes(blobs['plan.json'])
    (destination/'p0-b2-square.png').write_bytes(stream.getvalue())
    save(destination/'integrity.json',protected);save(destination/'acceptance-local.json',local)
    return plan


def unpack_square(bundle,sidecar,destination):
    if file_hash(bundle)!=Path(sidecar).read_text().strip():raise ValueError('Square upload hash mismatch')
    with zipfile.ZipFile(bundle) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=allowed_members():raise ValueError('Square members differ')
        data={n:z.read(n) for n in names};manifest=json.loads(data['bundle-manifest.json'])
        if set(manifest['files'])!=allowed_members()-{'bundle-manifest.json'}:raise ValueError('Square manifest differs')
        for n,spec in manifest['files'].items():
            if len(data[n])!=spec['bytes'] or digest(data[n])!=spec['sha256']:raise ValueError('Changed member '+n)
        plan=json.loads(data['plan.json'])
        if (plan['experiment']!=EXPERIMENT or plan['scope']!=['p0-b2'] or len(plan['targets'])!=1 or
            plan['targets'][0]['roi_id']!='p0-b2' or plan['targets'][0]['object_id']!='p0-b2' or
            plan['targets'][0]['transform']['padding_ltrb_px']!=[0,377,0,378] or
            plan['targets'][0]['transform']['size_px']!=[831,831] or plan.get('trace_policy')!=POLICY or
            json.loads(data['trace-policy.json'])!=POLICY):raise ValueError('Unapproved square scope/policy')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    for n,raw in data.items():
        target=destination/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description='OFFLINE square preparation; never invokes OCR')
    p.add_argument('--output',required=True);args=p.parse_args()
    prepare_square(args.output);print('Square package prepared without OCR:',args.output)
