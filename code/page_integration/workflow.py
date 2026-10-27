"""Offline preparation, verified transfer and evaluation. Never imports OCR."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

from .localized_labels import (associate, checked_box, geometry_acceptance,
                               normalized_text, original_box, select_rois)

ROOT=Path(__file__).resolve().parents[2]
BASE=Path('code/results/mineru-page/20261023T202636Z/result.zip')
RENDER=Path('code/results/layoutlmv3-page/20261023T153938Z/review/render.png')
PREPARED=Path('analytics/data/prepared/sic12_page3/p01-p02-20261024-v3/prepared.json')
REFERENCE=Path('analytics/data/references/sic12_page3/table-labels-v1.json')
IMAGE_SHA='6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'


def digest(data):return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def read(path):return json.loads(Path(path).read_bytes())


def resolve_pointer(document,pointer):
    value=document
    for key in pointer.lstrip('/').split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def text_fragments(value,pointer):
    """Only semantic text/equation content; never base64, paths or HTML tables."""
    result=[]
    if isinstance(value,dict):
        if value.get('type') in ('text','equation_inline') and isinstance(value.get('content'),str):
            return [dict(text=value['content'],source_pointer=pointer+'/content')]
        if isinstance(value.get('content'),list):
            for i,child in enumerate(value['content']):result.extend(text_fragments(child,pointer+'/content/'+str(i)))
    return result


def collect_texts(document,roi,roi_id,member,sha):
    if document.get('schema')!='docvortex.middle' or document.get('schema_version')!='2.0':
        raise ValueError('Unknown native coordinate/schema contract')
    pages=document.get('pages',[])
    if len(pages)!=1 or pages[0]['page_idx']!=0:raise ValueError('Expected one crop page')
    result=[]
    def visit(block,pointer):
        children=block.get('content')
        is_container=isinstance(children,list) and any(isinstance(c,dict) and 'bbox' in c for c in children)
        if is_container:
            for i,child in enumerate(children):visit(child,pointer+'/content/'+str(i))
            return
        fragments=text_fragments(block,pointer)
        if not fragments:return
        if block.get('bbox') is None:raise ValueError('Text without geometry at '+pointer)
        native=checked_box(block['bbox'],1,1);box=original_box(native,roi)
        recovered=[(box[0]-roi[0])/(roi[2]-roi[0]),(box[1]-roi[1])/(roi[3]-roi[1]),
                   (box[2]-roi[0])/(roi[2]-roi[0]),(box[3]-roi[1])/(roi[3]-roi[1])]
        error=max(abs(a-b)*scale for a,b,scale in zip(native,recovered,(roi[2]-roi[0],roi[3]-roi[1])*2))
        if error>1:raise ValueError('Coordinate round trip >1 px')
        result.append(dict(text=''.join(f['text'] for f in fragments),bbox=box,bbox_native=native,
            source_pointer=pointer,fragments=fragments,source_member=member,source_sha256=sha,
            roi_id=roi_id,roundtrip_error_px=error,native_type=block['type']))
    for i,block in enumerate(pages[0]['blocks']):visit(block,'/pages/0/blocks/'+str(i))
    return result


def prepare(destination):
    """Create allowlisted user-run package and preview, never load a model."""
    from PIL import Image,ImageDraw
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    prepared=read(ROOT/PREPARED);page=prepared['rendered_pages'][0]
    if page['render_sha256']!=IMAGE_SHA or file_hash(ROOT/RENDER)!=IMAGE_SHA:raise ValueError('Original render changed')
    mineru=next(r for r in prepared['runs'] if r['model']=='mineru')
    if file_hash(ROOT/BASE)!=mineru['source_archive_sha256']:raise ValueError('Baseline archive changed')
    blobs={}
    with zipfile.ZipFile(ROOT/BASE) as z:
        document=json.loads(z.read('page/middle-native.json'))
        regions=json.loads(z.read('page/regions.json'))['regions']
        run=json.loads(z.read('page/run-manifest.json'))
        config=z.read('config.yaml');lock=z.read('requirements.lock');freeze=z.read('requirements-freeze.txt')
        models=z.read('model-manifest.json');receipt=z.read('model-download-receipt.json')
        native_sha=digest(z.read('page/middle-native.json'))
    for filename in ('__init__.py','run_image.py','outputs.py'):
        data=(ROOT/'code/mineru_probe'/filename).read_bytes()
        if digest(data)!=run['code_sha256'][filename]:raise ValueError('Original adapter changed: '+filename)
        blobs['mineru_probe/'+filename]=data
    original_helper=(ROOT/'code/mineru_probe/remote_job.py').read_bytes()
    with zipfile.ZipFile(ROOT/BASE) as z:setup_hash=json.loads(z.read('job-status.json'))['setup_sha256']
    if digest(original_helper)!=setup_hash:raise ValueError('Original installer changed')
    blobs['mineru_probe/remote_job.py']=original_helper
    targets=select_rois(regions,page['width_px'],page['height_px'])
    if {t['object_id'] for t in targets}!={'p0-b2','p0-b4'}:raise ValueError('Scope is exactly the two tables')
    for t in targets:
        caption=resolve_pointer(document,t['caption_source_pointer'])
        t['description']=''.join(f['text'] for f in text_fragments(caption,t['caption_source_pointer']))
        if not t['description']:raise ValueError('Missing native caption text')
        t['native_source']=dict(archive=str(BASE).replace('\\','/'),archive_sha256=mineru['source_archive_sha256'],
            member='page/middle-native.json',member_sha256=native_sha)
    plan=dict(schema_version='1.0',experiment='localized-labels-v1',page=page,targets=targets,
        baseline_archive_sha256=mineru['source_archive_sha256'],original_run=run,
        execution_policy='USER_ONLY_COLAB_CLI_T4',ocr_executed=False,
        parameters=dict(overlap_min=.5,padding_px=0,resize=False,retries=0,iou_min=.5,
                        expanded_reference_coverage_min=.9,reference_expansion_px=2,roundtrip_max_px=1))
    reference=read(ROOT/REFERENCE)
    if reference['render_sha256']!=IMAGE_SHA or reference['document_id']!=page['document_id']:raise ValueError('Reference identity mismatch')
    checks=[]
    for label in reference['labels']:
        t=next(t for t in targets if t['object_id']==label['object_id']);b=label['bbox'];r=t['bbox']
        contained=r[0]<=b[0]<b[2]<=r[2] and r[1]<=b[1]<b[3]<=r[3]
        checks.append(dict(object_id=t['object_id'],label_contained=contained,roi_status=t['status']))
    if not all(c['label_contained'] and c['roi_status']=='ready' for c in checks):
        raise ValueError('ROI precheck failed; do not execute or expand automatically: '+repr(checks))
    destination.mkdir(parents=True,exist_ok=False)
    im=Image.open(ROOT/RENDER).convert('RGB');preview=im.copy();draw=ImageDraw.Draw(preview)
    for t in targets:
        out=io.BytesIO();im.crop(tuple(t['bbox'])).save(out,format='PNG',dpi=(200,200))
        name='inputs/'+t['roi_id']+'.png';blobs[name]=out.getvalue();t['input_member']=name;t['input_sha256']=digest(blobs[name])
        (destination/(t['roi_id']+'.png')).write_bytes(blobs[name])
        draw.rectangle(t['bbox'],outline='red',width=2)
    preview.save(destination/'roi-preview.png')
    for name in ('__init__.py','localized_labels.py','workflow.py','remote_labels.py','label_recovery.schema.json'):
        blobs['page_integration/'+name]=(Path(__file__).parent/name).read_bytes()
    blobs.update({'config.yaml':config,'requirements.lock':lock,'requirements-freeze.txt':freeze,
                  'model-manifest.json':models,'model-download-receipt.json':receipt})
    blobs['plan.json']=json.dumps(plan,ensure_ascii=False,indent=2).encode('utf-8')
    manifest={'schema_version':'1.0','files':{n:dict(bytes=len(b),sha256=digest(b)) for n,b in blobs.items()}}
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for n,b in blobs.items():z.writestr(n,b)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    (destination/'upload.sha256').write_text(file_hash(destination/'upload.zip')+'\n',encoding='ascii')
    save(destination/'plan.json',plan)
    save(destination/'roi-precheck.json',dict(reference_sha256=file_hash(ROOT/REFERENCE),checks=checks,ocr_executed=False))
    # Baseline hashes include historical result trees, code and reference, never inferred from counts.
    protected=[ROOT/BASE,ROOT/RENDER,ROOT/PREPARED,ROOT/REFERENCE]
    for run_info in prepared['runs']:
        source=ROOT/run_info['source_archive']
        if file_hash(source)!=run_info['source_archive_sha256']:raise ValueError('Source archive changed: '+str(source))
        protected.append(source)
    for directory in ('code/mineru_probe','analytics/results/sic12_page3/a03-20261024',
                      'analytics/results/sic12_page3/a04-20261024','analytics/results/sic12_page3/a05-20261024',
                      'analytics/results/sic12_page3/a06-20261024',
                      'analytics/data/prepared/sic12_page3/p03-20261024',
                      'code/results/mineru-page/20261023T202636Z/review',
                      'code/results/layoutlmv3-page/20261023T153938Z/review',
                      'code/results/table-transformer-page/20261023T165937Z/recovered-exports'):
        protected.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    save(destination/'integrity.json',{p.relative_to(ROOT).as_posix():file_hash(p) for p in protected})
    return plan


def unpack(bundle,sidecar,destination):
    """Verify all bytes and allowlist before extraction; no path guessing."""
    bundle=Path(bundle);destination=Path(destination)
    if file_hash(bundle)!=Path(sidecar).read_text().strip():raise ValueError('Upload hash mismatch')
    fixed={'config.yaml','requirements.lock','requirements-freeze.txt','model-manifest.json',
           'model-download-receipt.json','plan.json','bundle-manifest.json',
           'mineru_probe/__init__.py','mineru_probe/run_image.py','mineru_probe/outputs.py','mineru_probe/remote_job.py'}
    fixed|={'page_integration/'+n for n in ('__init__.py','localized_labels.py','workflow.py','remote_labels.py','label_recovery.schema.json')}
    fixed|={'inputs/p0-b2.png','inputs/p0-b4.png'}
    with zipfile.ZipFile(bundle) as z:
        if set(z.namelist())!=fixed or len(z.namelist())!=len(fixed):raise ValueError('Unknown/duplicate ZIP entries')
        manifest=json.loads(z.read('bundle-manifest.json'))
        if set(manifest['files'])!=fixed-{'bundle-manifest.json'}:raise ValueError('Invalid upload manifest')
        data={n:z.read(n) for n in fixed}
        for n,spec in manifest['files'].items():
            if digest(data[n])!=spec['sha256'] or len(data[n])!=spec['bytes']:raise ValueError('Upload member mismatch: '+n)
    destination.mkdir(parents=True,exist_ok=False)
    for n,b in data.items():
        target=destination/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
    return manifest


def evaluate(preparation,result_zip,destination):
    """Evaluate returned JSON against held-out manual reference; never run OCR."""
    preparation=Path(preparation);result_zip=Path(result_zip);destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    integrity=read(preparation/'integrity.json')
    for n,h in integrity.items():
        if file_hash(ROOT/n)!=h:raise ValueError('Protected original changed: '+n)
    if file_hash(result_zip)!=result_zip.with_suffix('.sha256').read_text().strip():raise ValueError('Returned archive hash mismatch')
    plan=read(preparation/'plan.json');texts=[];failures=[]
    from .remote_labels import canonical,check_environment
    with zipfile.ZipFile(preparation/'upload.zip') as source:
        expected_packages={canonical(line.split('==',1)[0]):line.split('==',1)[1]
                           for line in source.read('requirements-freeze.txt').decode().splitlines() if line.strip()}
    with zipfile.ZipFile(result_zip) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate result members')
        if z.read('plan.json')!=json.dumps(plan,ensure_ascii=False,indent=2).encode('utf-8'):
            raise ValueError('Returned plan mismatch')
        status=json.loads(z.read('execution-status.json'))
        if status['status']!='completed':failures.append('remote_execution_not_completed')
        runtime=json.loads(z.read('runtime.json')) if 'runtime.json' in z.namelist() else None
        if not runtime or not runtime.get('verified'):failures.append('runtime_not_verified')
        else:check_environment(runtime['observed'],dict(python=plan['original_run']['python'],packages=expected_packages))
        for t in plan['targets']:
            member='rois/'+t['roi_id']+'/middle-native.json'
            if member not in z.namelist():failures.append('missing_native:'+t['roi_id']);continue
            raw=z.read(member)
            texts.extend(collect_texts(json.loads(raw),t['bbox'],t['roi_id'],member,digest(raw)))
    linked=associate(plan['targets'],texts);reference=read(ROOT/REFERENCE);checks=[]
    for label in reference['labels']:
        result=next(r for r in linked if r['object_id']==label['object_id']);c=result['selected_label']
        geometry=geometry_acceptance(c['bbox'],label['bbox']) if c else None
        correct=bool(c and re.sub(r'\s+','',c['label_text']).casefold()==re.sub(r'\s+','',label['text']).casefold() and
            result['caption_id']==label['caption_id'] and result['body_id']==label['body_id'] and
            geometry['passed'] and not failures and c['roundtrip_error_px']<=1)
        result['links_verified']=correct
        checks.append(dict(object_id=label['object_id'],passed=correct,geometry=geometry,
                           combined_block=bool(c and c['label_bbox_precision']=='combined_block')))
    destination.mkdir(parents=True,exist_ok=False)
    payload=dict(schema_version='1.0',page=plan['page'],objects=linked,text_evidence=texts,
        reference_sha256=file_hash(ROOT/REFERENCE),result_archive_sha256=file_hash(result_zip),
        input_plan_sha256=file_hash(preparation/'plan.json'),runtime=runtime,checks=checks,failures=failures,
        integrity_verified=True,registry_implemented=True,labels_recovered=all(r['label_recovered'] for r in linked),
        links_verified=all(c['passed'] for c in checks),human_review='pending')
    save(destination/'unified-page.json',payload)
    return payload


def evaluate_table2_lines(preparation,result_zip,destination,review=None):
    """Separate offline increment; v1 results/candidates remain unmodified below baseline/."""
    from .localized_labels import propose_caption_lines,verify_line_review,LABEL
    from PIL import Image,ImageDraw
    preparation=Path(preparation);result_zip=Path(result_zip);destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    # Original evaluator validates all 85 protected sources, checksum and runtime.
    baseline=evaluate(preparation,result_zip,destination/'baseline')
    plan=read(preparation/'plan.json')
    target=next(t for t in plan['targets'] if t['object_id']=='p0-b4')
    reference=read(ROOT/REFERENCE)
    if reference['physical_page']!=plan['page']['physical_page']:
        raise ValueError('Reference page identity mismatch')
    if reference['render_sha256']!=plan['page']['render_sha256'] or reference['document_id']!=plan['page']['document_id']:
        raise ValueError('Reference document/render mismatch')
    expected_tolerance=dict(iou_min=.5,expanded_reference_coverage_min=.9,reference_expansion_px=2,roundtrip_max_px=1)
    if reference['tolerance']!=expected_tolerance:raise ValueError('Approved tolerances changed')
    evidence=[]
    member='rois/p0-b4/model-native.json'
    with zipfile.ZipFile(result_zip) as z,zipfile.ZipFile(preparation/'upload.zip') as original:
        for n in ('config.yaml','requirements.lock','model-manifest.json','model-download-receipt.json'):
            if z.read(n)!=original.read(n):raise ValueError('Original runtime artifact differs: '+n)
        if json.loads(z.read('rois/p0-b4/input-and-transform.json'))!=target:raise ValueError('Transform/ROI provenance changed')
        raw=z.read(member);model=json.loads(raw)
        if model.get('schema')!='docvortex.model' or model.get('schema_version')!='2.0' or len(model.get('pages',[]))!=1:
            raise ValueError('Unknown native model schema')
        for i,block in enumerate(model['pages'][0]):
            pointer='/pages/0/'+str(i);fragments=text_fragments(block,pointer)
            if not fragments:continue
            evidence.append(dict(text=''.join(f['text'] for f in fragments),fragments=fragments,
                bbox=original_box(block['bbox'],target['bbox']),bbox_native=block['bbox'],
                lines=block.get('lines',[]),source_member=member,source_sha256=digest(raw),
                source_pointer=pointer,roi_id='p0-b4',native_type=block['type']))
    proposal=propose_caption_lines(target,evidence,target['bbox'])
    c=proposal['selected_candidate'];label=next(l for l in reference['labels'] if l['object_id']=='p0-b4')
    geometry=geometry_acceptance(c['label_line']['bbox'],label['bbox']) if c else None
    # Cross-check the model caption against MiddleJson; do not silently mix blocks.
    middle=next((t for t in baseline['text_evidence'] if t['roi_id']=='p0-b4' and c and
                 t['text']==c['text'] and t['bbox']==c['original_block_bbox']),None)
    native=target['native_source']
    with zipfile.ZipFile(ROOT/native['archive']) as z:
        native_raw=z.read(native['member'])
        if digest(native_raw)!=native['member_sha256']:raise ValueError('Original native source changed')
        native_doc=json.loads(native_raw)
        caption=resolve_pointer(native_doc,target['caption_source_pointer'])
        body=resolve_pointer(native_doc,target['body_source_pointer'])
        parent=resolve_pointer(native_doc,target['caption_source_pointer'].rsplit('/content/',1)[0])
        parentage=(parent['type']=='table' and caption['type']=='table_caption' and body['type']=='table_body' and
                   caption in parent['content'] and body in parent['content'])
    literal_label_ok=bool(c and re.sub(r'\s+','',c['label_text']).casefold()==re.sub(r'\s+','',label['text']).casefold())
    automatic=bool(c and geometry['passed'] and literal_label_ok and middle and parentage and
                   not baseline['failures'] and c['label_line']['roundtrip_error_px']<=1 and
                   c['description_line']['roundtrip_error_px']<=1 and
                   target['caption_id']==label['caption_id'] and target['body_id']==label['body_id'])
    review_ok=bool(c and verify_line_review(c,review,file_hash(result_zip)))
    verified=automatic and review_ok
    proposal['links_verified']=verified
    proposal['status']='verified_by_visual_review' if verified else proposal['status']
    payload=dict(schema_version='1.0',schema_ref='code/page_integration/label_recovery.schema.json#/$defs/table2_lines',
        scope=['p0-b4'],page=plan['page'],registry_implemented=True,
        labels_recovered=literal_label_ok,links_verified=verified,
        automatic_acceptance_passed=automatic,visual_review=review,
        visual_review_valid=review_ok,proposal=proposal,label_geometry=geometry,tolerances=expected_tolerance,
        original_native_evidence=dict(source=native,caption_pointer=target['caption_source_pointer'],body_pointer=target['body_source_pointer']),
        middle_caption_evidence=middle,parentage_verified=parentage,
        unchanged_table1=next(r for r in baseline['objects'] if r['object_id']=='p0-b2'),
        baseline_result='baseline/unified-page.json',result_archive_sha256=file_hash(result_zip),
        reference_sha256=file_hash(ROOT/REFERENCE),input_plan_sha256=file_hash(preparation/'plan.json'),
        implementation_sha256={n:file_hash(Path(__file__).parent/n) for n in ('localized_labels.py','workflow.py')},
        integrity_verified=baseline['integrity_verified'],ocr_executed=False,
        limitations=['Native lines provide geometry, not individual transcriptions. Visual review required.',
                     'Table 1 and figures unchanged; no broader extraction or OCR validation.'])
    if c:
        image=Image.open(ROOT/RENDER).convert('RGB').crop(target['bbox']);draw=ImageDraw.Draw(image)
        for role,color in (('label_line','red'),('description_line','blue')):
            b=c[role]['bbox'];local=[b[0]-target['bbox'][0],b[1]-target['bbox'][1],b[2]-target['bbox'][0],b[3]-target['bbox'][1]]
            draw.rectangle(local,outline=color,width=1)
        image.save(destination/'line-review.png')
        payload['review_image_sha256']=file_hash(destination/'line-review.png')
    save(destination/'table2-lines.json',payload)
    return payload


def main():
    p=argparse.ArgumentParser(description='Offline only: prepare or evaluate; never executes OCR')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--output',required=True)
    a=sub.add_parser('evaluate');a.add_argument('--preparation',required=True);a.add_argument('--result',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('evaluate-table2-lines');a.add_argument('--preparation',required=True);a.add_argument('--result',required=True);a.add_argument('--output',required=True);a.add_argument('--review')
    args=p.parse_args()
    if args.command=='prepare':
        plan=prepare(args.output);print('Prepared without OCR:',args.output)
        for t in plan['targets']:print(t['roi_id'],t['bbox'],t['status'])
    elif args.command=='evaluate':
        data=evaluate(args.preparation,args.result,args.output)
        print(json.dumps({k:data[k] for k in ('labels_recovered','links_verified','failures','human_review')},indent=2))
    else:
        data=evaluate_table2_lines(args.preparation,args.result,args.output,read(args.review) if args.review else None)
        print(json.dumps({k:data[k] for k in ('labels_recovered','automatic_acceptance_passed','links_verified','visual_review_valid')},indent=2))


if __name__=='__main__':main()
