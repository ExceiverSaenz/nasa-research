"""Batch coordination only. No model imports, inference at import, or retries."""
import hashlib
import json
from pathlib import PurePosixPath
import shutil
import traceback
from .common import MODELS, read, save
from .worker import validate_document_plan


def batch_digest(documents):
    return hashlib.sha256(json.dumps(documents,sort_keys=True,separators=(',',':'),
        ensure_ascii=False).encode('utf-8')).hexdigest()


def validate_batch(inputs,plan):
    entries=plan.get('documents')
    if not isinstance(entries,list) or not entries or plan.get('batch_sha256')!=batch_digest(entries):
        raise ValueError('Invalid batch identity')
    seen=set()
    for entry in entries:
        child=entry['plan'];key=entry['key'];relative=PurePosixPath(entry['input_path'])
        if (relative.is_absolute() or '..' in relative.parts or '\\' in str(relative)
            or ':' in str(relative) or relative.parts[:1]!=('documents',)):
            raise ValueError('Unsafe document input path')
        if key!=child['document_sha256'] or key in seen:raise ValueError('Duplicate/invalid document key')
        seen.add(key)
        if child['models']!=plan['models']:raise ValueError('Model configuration drift')
        if (child.get('execution_policy')!='USER_ONLY_COLAB_CLI_T4' or
            child.get('automatic_retries') is not False or child.get('automatic_recovery') is not False or
            child.get('postprocessing')!='native_outputs_only_no_reconciliation'):
            raise ValueError('Unapproved document execution policy')
        source=inputs/str(relative)
        if read(source/'plan.json')!=child:raise ValueError('Child plan differs')
        validate_document_plan(child,source/'document.pdf')


def account_missing(plan,state):
    entries=plan.get('documents')
    jobs=[(e['plan'],state/'documents'/e['key']) for e in entries] if entries else [(plan,state)]
    for child,dest in jobs:
        if entries and not (dest/'execution-status.json').exists():
            save(dest/'plan.json',child)
            save(dest/'execution-status.json',dict(status='failed',error='Earlier failure; inspect batch execution-status'))
        for page in child['physical_pages']:
            for model in MODELS:
                path=dest/'pages'/('%04d'%page)/model/'status.json'
                if not path.exists():save(path,dict(status='not_run',page=page,model=model,inference_calls=0,
                    reason='No recorded terminal page result; inspect execution-status and branch-failures'))


def run_documents(inputs,state,work):
    plan=read(inputs/'plan.json');validate_batch(inputs,plan)
    results=[]
    for entry in plan['documents']:
        source=inputs/entry['input_path'];dest=state/'documents'/entry['key']
        dest.mkdir(parents=True,exist_ok=False)
        # Config/receipts are small immutable inputs; large weights remain shared.
        for model in MODELS:shutil.copytree(inputs/model,source/model)
        shutil.copy2(state/'config.yaml',dest/'config.yaml')
        (dest/'models').symlink_to((state/'models').resolve(),target_is_directory=True)
        (dest/'plan.json').write_bytes((source/'plan.json').read_bytes())
        execution=dict(read(state/'execution.json'),document_sha256=entry['key'])
        execution['parent_execution_id']=execution['execution_id']
        execution['execution_id']+='-'+entry['key']
        save(dest/'execution.json',execution)
        failures={};status=dict(status='failed',error=None,automatic_recovery=False)
        print('DOCUMENT_START '+entry['plan']['document'],flush=True)
        try:
            work('layoutlmv3','render',source,dest)
            for model in MODELS:
                try:work(model,'infer',source,dest)
                except Exception:failures[model]=traceback.format_exc()
            if failures:raise RuntimeError('One or more parser branches failed; no retry')
            status['status']='completed'
        except Exception:status['error']=traceback.format_exc()
        finally:
            save(dest/'branch-failures.json',failures)
            save(dest/'execution-status.json',status)
            account_missing(entry['plan'],dest)
            results.append(dict(document=entry['plan']['document'],key=entry['key'],status=status['status']))
            save(state/'document-progress.json',results)
            print('DOCUMENT_END '+entry['plan']['document']+' '+status['status'],flush=True)
    if any(r['status']!='completed' for r in results):raise RuntimeError('One or more documents failed; inspect individual outputs. No retry.')
