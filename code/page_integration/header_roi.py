"""Offline preparation for a header-only experiment; no OCR imports or execution."""
import argparse
import copy
import io
import json
import math
from pathlib import Path
import zipfile

from .localized_labels import checked_box
from .workflow import ROOT,BASE,RENDER,REFERENCE,IMAGE_SHA,read,save,digest,file_hash

EXPERIMENT='table1-header-v1'
CODE_FILES=('__init__.py','localized_labels.py','workflow.py','remote_labels.py',
            'header_roi.py','remote_header.py','label_recovery.schema.json')
ADAPTER_FILES=('__init__.py','run_image.py','outputs.py','remote_job.py')
ARTIFACTS=('config.yaml','requirements.lock','requirements-freeze.txt','model-manifest.json','model-download-receipt.json')


def header_roi(target,width,height):
    """Caption horizontal envelope + preceding barrier; never uses manual label boxes."""
    result=copy.deepcopy(target)
    context=checked_box(target['bbox'],width,height)
    caption=checked_box(target['caption_bbox'],width,height)
    body=checked_box(target['body_bbox'],width,height)
    if (target.get('status')!='ready' or context[1]>=caption[1] or
        context[0]>caption[0] or context[2]<caption[2] or context[3]<caption[3]):
        raise ValueError('Ambiguous/incompatible original context; do not expand automatically')
    crop=[math.floor(caption[0]),math.floor(context[1]),math.ceil(caption[2]),math.ceil(caption[3])]
    checked_box(crop,width,height)
    if crop[3]>body[1]:raise ValueError('Header ROI would overlap table body; review selection')
    result.update(bbox=crop,previous_context_bbox=context,roi_mode='header_only',
        selection_rule='caption_x_envelope_preceding_barrier_to_caption_bottom_v1',
        transform=dict(operation='crop_only',origin_px=crop[:2],size_px=[crop[2]-crop[0],crop[3]-crop[1]],
                       inverse='original=roi_origin+normalized*roi_size'))
    return result


def allowed_members():
    return ({'page_integration/'+n for n in CODE_FILES}|{'mineru_probe/'+n for n in ADAPTER_FILES}|
            set(ARTIFACTS)|{'plan.json','bundle-manifest.json','inputs/p0-b2.png'})


def prepare_header(destination):
    """Prepare one crop using verified frozen v1 sources, no full-page reparse."""
    from PIL import Image
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    prior=ROOT/'code/packages/localized-labels-v1'
    protected=read(prior/'integrity.json')
    for n,h in protected.items():
        if file_hash(ROOT/n)!=h:raise ValueError('Protected source changed: '+n)
    if file_hash(ROOT/RENDER)!=IMAGE_SHA:raise ValueError('Original render changed')
    # Include all prior accepted Table2 outputs and frozen uploaded/downloaded evidence.
    for tree in ('analytics/results/sic12_page3/table2-lines-v1','code/packages/localized-labels-v1',
                 'code/results/localized-labels-v1/20261024T221741Z'):
        for p in (ROOT/tree).rglob('*'):
            if p.is_file():protected[p.relative_to(ROOT).as_posix()]=file_hash(p)
    prior_plan=read(prior/'plan.json')
    target=next(t for t in prior_plan['targets'] if t['object_id']=='p0-b2')
    target=header_roi(target,prior_plan['page']['width_px'],prior_plan['page']['height_px'])
    plan=copy.deepcopy(prior_plan)
    plan.update(experiment=EXPERIMENT,targets=[target],scope=['p0-b2'],
        input_variable='header_only_ROI; parser/settings/weights/scale unchanged',
        source_plan_sha256=file_hash(prior/'plan.json'),source_experiment='localized-labels-v1',
        acceptance=dict(label='Table 1',object_id='p0-b2',caption_id='p0-b2-c0',body_id='p0-b2-c1',
            note='Not passed to OCR or association as recognition input; expectation only',
            stages=['recognition','original_render_geometry','association','visual_review_if_untranscribed_lines']))
    # Do not put expected label or acceptance reference into recognition input metadata.
    # The acceptance expectation is kept LOCAL, removed from the remote plan below.
    expected=plan.pop('acceptance')
    reference=read(ROOT/REFERENCE)
    expected_tolerances=dict(iou_min=.5,expanded_reference_coverage_min=.9,reference_expansion_px=2,roundtrip_max_px=1)
    if reference['tolerance']!=expected_tolerances:raise ValueError('Approved tolerances changed')
    if (reference['render_sha256']!=plan['page']['render_sha256'] or
        reference['document_id']!=plan['page']['document_id'] or reference['physical_page']!=plan['page']['physical_page']):
        raise ValueError('Reference identity mismatch')
    label=next(l for l in reference['labels'] if l['object_id']=='p0-b2');b=label['bbox'];r=target['bbox']
    if not (r[0]<=b[0]<b[2]<=r[2] and r[1]<=b[1]<b[3]<=r[3]):raise ValueError('Header excludes reference label; do not run')
    blobs={}
    with zipfile.ZipFile(ROOT/BASE) as original:
        for n in ARTIFACTS:blobs[n]=original.read(n)
        if digest(original.read('page/run-manifest.json'))!=digest(json.dumps(plan['original_run'],indent=2).encode()):
            if json.loads(original.read('page/run-manifest.json'))!=plan['original_run']:raise ValueError('Original run metadata changed')
        setup_sha=json.loads(original.read('job-status.json'))['setup_sha256']
    for name in ADAPTER_FILES:
        raw=(ROOT/'code/mineru_probe'/name).read_bytes()
        expected_sha=setup_sha if name=='remote_job.py' else plan['original_run']['code_sha256'][name]
        if digest(raw)!=expected_sha:raise ValueError('Original adapter changed: '+name)
        blobs['mineru_probe/'+name]=raw
    for name in CODE_FILES:blobs['page_integration/'+name]=(Path(__file__).parent/name).read_bytes()
    crop=Image.open(ROOT/RENDER).convert('RGB').crop(target['bbox'])
    stream=io.BytesIO();crop.save(stream,format='PNG',dpi=(200,200))
    blobs['inputs/p0-b2.png']=stream.getvalue()
    target.update(input_member='inputs/p0-b2.png',input_sha256=digest(stream.getvalue()))
    blobs['plan.json']=json.dumps(plan,ensure_ascii=False,indent=2).encode('utf-8')
    manifest={'schema_version':'1.0','files':{n:dict(bytes=len(raw),sha256=digest(raw)) for n,raw in blobs.items()}}
    if set(blobs)|{'bundle-manifest.json'}!=allowed_members():raise ValueError('Header allowlist mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for n,raw in blobs.items():z.writestr(n,raw)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    (destination/'upload.sha256').write_text(file_hash(destination/'upload.zip')+'\n',encoding='ascii')
    (destination/'p0-b2-header.png').write_bytes(stream.getvalue())
    (destination/'plan.json').write_bytes(blobs['plan.json'])
    save(destination/'integrity.json',protected)
    save(destination/'acceptance-local.json',dict(expected=expected,tolerances=expected_tolerances,
        reference_sha256=file_hash(ROOT/REFERENCE),roi_contains_reference=True,ocr_executed=False))
    return plan


def unpack_header(bundle,sidecar,destination):
    if file_hash(bundle)!=Path(sidecar).read_text().strip():raise ValueError('Header upload hash mismatch')
    with zipfile.ZipFile(bundle) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=allowed_members():raise ValueError('Unknown/duplicate header members')
        data={n:z.read(n) for n in names};manifest=json.loads(data['bundle-manifest.json'])
        if set(manifest['files'])!=allowed_members()-{'bundle-manifest.json'}:raise ValueError('Header manifest mismatch')
        for n,spec in manifest['files'].items():
            if len(data[n])!=spec['bytes'] or digest(data[n])!=spec['sha256']:raise ValueError('Header member changed: '+n)
        plan=json.loads(data['plan.json'])
        if (plan['experiment']!=EXPERIMENT or plan.get('scope')!=['p0-b2'] or len(plan['targets'])!=1 or
            plan['targets'][0]['object_id']!='p0-b2' or plan['targets'][0]['roi_id']!='p0-b2' or
            plan['targets'][0]['input_member']!='inputs/p0-b2.png' or plan['targets'][0]['roi_mode']!='header_only'):
            raise ValueError('Header experiment scope mismatch')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    for n,raw in data.items():
        target=destination/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return manifest


def main():
    p=argparse.ArgumentParser(description='OFFLINE header preparation only; never invokes OCR')
    p.add_argument('--output',required=True);args=p.parse_args()
    plan=prepare_header(args.output)
    print('Prepared without OCR:',args.output,plan['targets'][0]['bbox'])


if __name__=='__main__':main()
