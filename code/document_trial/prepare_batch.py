"""Build one immutable batch from verified single-PDF packages; offline only."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from .common import ROOT, read, save, sha, validate_bundle
from .batch import batch_digest


def prepare_batch(destination,index=None):
    index=Path(index or ROOT/'code/packages/sic-parsing-v1/index.json')
    records=read(index)['packages'];blobs={};documents=[];models=None
    current={p.resolve() for p in (ROOT/'SiC_papers').glob('*.pdf')}
    if current!={(ROOT/r['document']).resolve() for r in records}:
        raise ValueError('Package index does not match all current SiC PDFs; prepare missing/changed PDFs first')
    for r in records:
        package=ROOT/r['package'];archive=package/'upload.zip'
        if sha(archive)!=r['package_sha256']:raise ValueError('Original package changed')
        plan=validate_bundle(archive,package/'upload.sha256')
        if (plan['document']!=r['document'] or plan['document_sha256']!=r['document_sha256'] or
            plan['page_count']!=r['pages'] or sha(ROOT/r['document'])!=r['document_sha256']):
            raise ValueError('Document/index identity mismatch')
        if models is None:models=plan['models']
        if models!=plan['models']:raise ValueError('Cannot share different model configurations')
        prefix='documents/'+r['document_sha256']
        with zipfile.ZipFile(archive) as z:
            if z.read('plan.json')!=(package/'plan.json').read_bytes():raise ValueError('Original external plan differs')
            for name in z.namelist():
                if name=='bundle-manifest.json' or name.startswith('document_trial/'):continue
                data=z.read(name)
                if name in ('plan.json','document.pdf') or name.startswith('regression/'):
                    blobs[prefix+'/'+name]=data
                elif name in blobs and blobs[name]!=data:raise ValueError('Shared input differs: '+name)
                else:blobs[name]=data
        documents.append(dict(key=r['document_sha256'],input_path=prefix,plan=plan,
            original_package=r['package'],original_package_sha256=r['package_sha256']))
    for path in (ROOT/'code/document_trial').glob('*.py'):
        if not path.name.startswith('test_'):blobs['document_trial/'+path.name]=path.read_bytes()
    plan=dict(schema_version='document-parsing-batch/1',documents=documents,
        batch_sha256=batch_digest(documents),models=models,dpi=200,
        execution_policy='USER_ONLY_COLAB_CLI_T4',automatic_retries=False,automatic_recovery=False,
        postprocessing='native_outputs_only_no_reconciliation',page_count=sum(r['pages'] for r in records))
    blobs['plan.json']=(json.dumps(plan,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    manifest=dict(files={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in blobs.items()})
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    (destination/'plan.json').write_bytes(blobs['plan.json'])
    save(destination/'source-integrity.json',dict(index=str(index.relative_to(ROOT)),
        source_packages=records,source_code={n:manifest['files'][n]['sha256'] for n in blobs if n.startswith('document_trial/')}))
    blobs['bundle-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(blobs.items()):z.writestr(name,data)
    (destination/'upload.sha256').write_text(sha(destination/'upload.zip')+'\n',encoding='ascii')
    validate_bundle(destination/'upload.zip',destination/'upload.sha256')
    print('Prepared:',destination,'documents:',len(documents),'pages:',plan['page_count'])
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    prepare_batch(parser.parse_args().output)
