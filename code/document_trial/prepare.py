"""Build one immutable user-run package. No rendering, models or network."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from .common import ROOT,DOCUMENT,PAGE3,MODELS,sha,read,save,freeze_versions

ARCHIVES={
 'layoutlmv3':('code/results/layoutlmv3-page/20261023T153938Z/result.zip','55202094b48c150f4aefd2adf4a32f83e4157033eded23ffe08b9c97fe15b132'),
 'table_transformer':('code/results/table-transformer-page/20261023T165937Z/result.zip','a29324b855ae95a9e2be227fa13e4b61253e098501abda84a151654d5d820611'),
 'mineru':('code/results/mineru-page/20261023T202636Z/result.zip','da82316f469322285f54a4bf6fcc6f8a23a53c22d9717e95dac535968149da76')}

def document_parameters(pdf):
    pdf=Path(pdf).resolve()
    if not pdf.is_relative_to((ROOT/'SiC_papers').resolve()) or pdf.suffix.lower()!='.pdf' or not pdf.is_file():
        raise ValueError('Existing PDF inside SiC_papers required')
    try:
        from pypdf import PdfReader
    except ImportError:
        import fitz
        with fitz.open(pdf) as document:pagecount=len(document)
    else:pagecount=len(PdfReader(pdf).pages)
    if pagecount<1:raise ValueError('Empty document')
    digest=sha(pdf)
    return dict(document=pdf.relative_to(ROOT).as_posix(),document_sha256=digest,
        page_count=pagecount,physical_pages=list(range(1,pagecount+1)),dpi=200,
        regression=dict(page=3,render_sha256=PAGE3,table1='pending_warning',
            table2='historically_accepted_source_specific',
            policy='Never transfer historical label geometry to a changed render or unverified new inference') if digest==DOCUMENT else None)


def prepare(destination, pdf=None):
    destination=Path(destination)
    if destination.exists():raise FileExistsError('New package directory required')
    pdf=Path(pdf) if pdf is not None else ROOT/'SiC_papers/12.pdf'
    parameters=document_parameters(pdf)
    pdf=ROOT/parameters['document']
    blobs={'document.pdf':pdf.read_bytes()};specs={}
    for model,(path,expected) in ARCHIVES.items():
        if sha(ROOT/path)!=expected:raise ValueError('Original archive changed')
        with zipfile.ZipFile(ROOT/path) as z:
            freeze='requirements-page-freeze.txt' if model=='layoutlmv3' else 'requirements-freeze.txt'
            blobs[model+'/freeze.txt']=z.read(freeze)
            if model!='mineru':
                run=json.loads(z.read('page/run-manifest.json'));env=run['environment']
                specs[model]=dict(python=env['python'],cuda='11.1' if model=='layoutlmv3' else '12.1',
                    bootstrap_uv='0.12.21' if model=='layoutlmv3' else '0.6.14',
                    packages=freeze_versions(z.read(freeze).decode(),env),original_run=run,archive=path,archive_sha256=expected)
                manifest=run['detector']['model_manifest'];blobs[model+'/models.json']=json.dumps(manifest,indent=2).encode()
                source_dir=ROOT/('code/layoutlmv3/inference' if model=='layoutlmv3' else 'code/table_transformer')
                for name in ('detector.py',):
                    if sha(source_dir/name)!=run['code_sha256'][name]:raise ValueError('Original detector implementation differs: '+model+'/'+name)
                if model=='layoutlmv3':
                    vendor=ROOT/'code/vendor/unilm/layoutlmv3'
                    for name,digest in run['detector']['vendor_source_sha256'].items():
                        if sha(vendor/name)!=digest:raise ValueError('Original LM vendor differs: '+name)
                    config=vendor/'examples/object_detection/cascade_layoutlmv3.yaml'
                    if sha(config)!=run['detector']['config_sha256']:raise ValueError('LM YAML differs')
                    for f in vendor.rglob('*'):
                        if f.is_file() and '__pycache__' not in f.parts and f.suffix in ('.py','.yaml','.yml','.json','.txt','.cfg','.toml'):
                            blobs['vendor/layoutlmv3/'+f.relative_to(vendor).as_posix()]=f.read_bytes()
            else:
                expected_detector='4a84dacbc056636425341ec589b5c03eab878b253fe8157fdbc1295d75f21a78'
                if sha(ROOT/'code/mineru_probe/run_image.py')!=expected_detector:raise ValueError('Original MinerU parse adapter changed')
                for name in ('config.yaml','requirements.lock','model-manifest.json','model-download-receipt.json'):
                    blobs[model+'/'+name]=z.read(name)
                specs[model]=dict(python='3.11.16',cuda='12.6',bootstrap_uv='0.12.21',packages=freeze_versions(z.read(freeze).decode(),{}),archive=path,archive_sha256=expected)
    for directory,prefix in [('code/document_trial','document_trial'),('code/layoutlmv3/inference','inference'),('code/table_transformer','table_transformer'),('code/mineru_probe','mineru_probe')]:
        for f in (ROOT/directory).glob('*.py'):
            if not f.name.startswith('test_'):blobs[prefix+'/'+f.name]=f.read_bytes()
    tolerances=dict(iou_min=.5,expanded_reference_coverage_min=.9,reference_expansion_px=2,roundtrip_max_px=1)
    if parameters['document_sha256']==DOCUMENT:
        # Freeze page3 evidence, not a generalizable recipe of its object IDs.
        regression={
         'original-middle.json':('archive','mineru','page/middle-native.json'),
         'reference-render.png':('archive','layoutlmv3','page/render.png')}
        for name,(_,model,member) in regression.items():
            with zipfile.ZipFile(ROOT/ARCHIVES[model][0]) as z:blobs['regression/'+name]=z.read(member)
        for name,path in {
            'accepted-table2.json':'analytics/results/sic12_page3/table2-lines-v1/accepted/table2-lines.json',
            'historical-reconciled.json':'analytics/results/sic12_page3/reconciliation-v1/verified-output/reconciled-page.json',
            'label-reference.json':'analytics/data/references/sic12_page3/table-labels-v1.json',
            'manual-reference.json':'analytics/results/sic12_page3/reconciliation-quality-v1/manual-reference.json'}.items():
            blobs['regression/'+name]=(ROOT/path).read_bytes()
        if hashlib.sha256(blobs['regression/reference-render.png']).hexdigest()!=PAGE3:raise ValueError('Regression render differs')
        accepted=json.loads(blobs['regression/accepted-table2.json'])
        historical=json.loads(blobs['regression/historical-reconciled.json'])
        if (not accepted['links_verified'] or accepted['scope']!=['p0-b4'] or accepted['tolerances']!=tolerances
            or accepted['page']['document_id']!=DOCUMENT or accepted['page']['render_sha256']!=PAGE3
            or json.loads(blobs['regression/label-reference.json'])['tolerance']!=tolerances
            or historical['tables']['p0-b2']['status']!='pending_warning'
            or historical['tables']['p0-b4']['accepted_evidence']!=accepted):
            raise ValueError('Historical page3 acceptance, pending state or tolerances differ')
    plan=dict(schema_version='document-parsing/2',**parameters,models=specs,execution_policy='USER_ONLY_COLAB_CLI_T4',
        inference_passes_per_model_page=1,automatic_recovery=False,automatic_retries=False,
        label_tolerances=tolerances if parameters['document_sha256']==DOCUMENT else None,
        postprocessing='native_outputs_only_no_reconciliation')
    blobs['plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
    manifest=dict(files={n:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for n,data in sorted(blobs.items())})
    destination.mkdir(parents=True)
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(blobs.items()):z.writestr(name,data)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    (destination/'upload.sha256').write_text(sha(destination/'upload.zip')+'\n',encoding='ascii')
    (destination/'plan.json').write_bytes(blobs['plan.json'])
    save(destination/'source-integrity.json',{path:expected for path,expected in ARCHIVES.values()})
    return plan

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--pdf',default=str(ROOT/'SiC_papers/12.pdf'));args=p.parse_args()
    print(json.dumps(prepare(args.output,args.pdf),indent=2))
