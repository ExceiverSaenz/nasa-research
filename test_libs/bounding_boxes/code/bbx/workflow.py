"""Explicit Colab phases, persisted identities and verified return transport."""
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from .contracts import load_experiment,write_json,sha256,validate_experiment,exit_code
from .transport import pack_code
from .remote import manifest_data
from .r2 import read_config,presign_get,safe_error,probe_r2
from .contracts import contained


def pack_wheels(root,destination,expected=None):
    root=Path(root)
    if expected is None:
        resolution=load_experiment(root/'runtime/dependency-resolution.json')
        expected={Path(k.replace('\\','/')).name:v['sha256'] for k,v in resolution['files'].items() if k.endswith('.whl')}
    files=[]
    for name,digest in expected.items():
        p=contained(root/'runtime/reused-wheels',name)
        if not p.is_file() or sha256(p)!=digest:raise ValueError('Wheel absent or identity mismatch')
        files.append(p)
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,'runtime/reused-wheels/'+p.name)


def extract_verified(archive,destination,digest):
    if sha256(archive)!=digest:raise ValueError('Return archive SHA256 mismatch')
    destination=Path(destination)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            contained(destination,member.filename)
            if (member.external_attr>>16)&0o170000==0o120000:raise ValueError('Symlink in archive')
        z.extractall(destination)
    manifest=load_experiment(destination/'manifest.json')
    for rel,identity in manifest.items():
        file=contained(destination,rel)
        if not file.is_file() or file.stat().st_size!=identity['bytes'] or sha256(file)!=identity['sha256']:
            raise ValueError('Extracted result manifest mismatch')


def verify_collection(root,papers,tools):
    root=Path(root)
    for tool in tools:
        receipt=load_experiment(root/tool/'receipt.json');records=receipt.get('results',[])
        if len(records)!=len(papers) or {r['paper'] for r in records}!={p['name'] for p in papers}:raise ValueError('Incomplete paper inventory')
        for paper in papers:
            row=next(r for r in records if r['paper']==paper['name'])
            if row['status']!='complete' or sorted(row.get('result',{}).get('page_indices',[]))!=list(range(paper['pages'])):
                raise ValueError('Native page coverage incomplete')
            files=row.get('files',{})
            if 'normalized.json' not in files or len(files)<2:raise ValueError('Missing native output')
            for rel,identity in files.items():
                file=contained(root/tool/Path(paper['name']).stem,rel)
                if not file.is_file() or file.stat().st_size!=identity['bytes'] or sha256(file)!=identity['sha256']:raise ValueError('Native file identity mismatch')


class Workflow:
    def __init__(self,root,attempt,transport,prober=probe_r2):
        self.root=Path(root).resolve();self.attempt=Path(attempt).resolve();self.transport=transport
        self.state_path=self.attempt/'workflow.json'
        self.prober=prober
    def state(self):
        if not self.state_path.exists():raise ValueError('No prepared session receipt')
        return load_experiment(self.state_path)
    def _persist(self,state):write_json(self.state_path,state)
    def _phase(self,state,phase):
        remote=state['remote_root'];marker='BBX_PHASE_COMPLETED:'+phase
        code=(f'import sys,json\nsys.path.insert(0,{remote!r})\n'
              'from bbx.remote import run_phase\nfrom bbx.r2 import safe_error\n'
              f'try:\n result=run_phase({remote!r},{phase!r})\n'
              'except Exception as e:\n print(safe_error(e));sys.exit(1)\n'
              f'print({marker!r})\nprint("BBX_RESULT:"+json.dumps(result))\n')
        stdout=self.transport.exec_code(state['session'],code,marker,timeout=18000)
        result=json.loads(next(line[len('BBX_RESULT:'):] for line in stdout.splitlines() if line.startswith('BBX_RESULT:')))
        if result.get('status') not in ('prepared','complete'):raise ValueError('Remote phase not complete')
        return result
    def prepare(self,papers,*,allow_remote=False,papers_dir=None,r2_config=None):
        if not allow_remote:raise ValueError('Explicit remote authorization required')
        if self.state_path.exists():raise ValueError('Attempt already exists; never allocate a second VM')
        config=load_experiment(self.root/'experiment.json')
        if exit_code(validate_experiment(config)) or not papers:raise ValueError('Invalid configuration or empty inventory')
        if any(p.get('pages') is None or not re.fullmatch('[0-9a-f]{64}',p.get('sha256','')) for p in papers):raise ValueError('Complete frozen PDF identities required')
        resolution=load_experiment(self.root/'runtime/dependency-resolution.json')
        resolution['files']={k.replace('\\','/'):v for k,v in resolution['files'].items()}
        for env,rel in config['locks'].items():
            if sha256(self.root/rel)!=resolution['files'][rel]['sha256']:raise ValueError('Lock receipt mismatch')
            candidate='requirements/'+env+'.in'
            if sha256(self.root/candidate)!=resolution['files'][candidate]['sha256']:raise ValueError('Candidate changed since resolution')
        for rel in config['model_manifests']:manifest_data(self.root/rel)
        for tool in config['tools'][:2]:
            manifest=manifest_data(self.root/'model_manifests'/(tool['id']+'.json'))
            if (manifest['repo'],manifest['revision'])!=(tool['model'],tool['revision']):raise ValueError('Heron model/config identity mismatch')
        if r2_config is None:raise ValueError('Fresh local R2 preflight required before allocation')
        r2checks=self.prober(r2_config,papers)
        selected=next((p['name'] for p in papers if p['name']=='12.pdf'),papers[0]['name'])
        required={'r2_head:'+p['name'] for p in papers}|{'r2_get:'+selected}
        if exit_code(r2checks) or not required.issubset({c.get('id') for c in r2checks}):raise ValueError('Local R2 gates failed')
        self.transport.command(['sessions'])  # Read-only authentication gate before any allocation.
        self.attempt.mkdir(parents=True,exist_ok=True)
        pack_code(self.root,self.attempt/'code.zip');pack_wheels(self.root,self.attempt/'wheels.zip')
        write_json(self.attempt/'inventory.json',papers)
        token='bbx-'+uuid.uuid4().hex;remote='/content/'+token
        state={'status':'allocating','session':token,'remote_root':remote,'inventory':papers,
               'papers_dir':str(Path(papers_dir).resolve()) if papers_dir else None,
               'config_sha256':sha256(self.root/'experiment.json'),'code_sha256':sha256(self.attempt/'code.zip')}
        state['local_r2_checks']=r2checks
        self._persist(state)  # Written before allocation; timeout is never treated as absence.
        try:
            self.transport.create(token,authorized=True)
            for filename in ('code.zip','wheels.zip','inventory.json'):
                self.transport.upload(token,self.attempt/filename,'/content/'+token+'-'+filename)
            code=('import pathlib,zipfile,hashlib\n'+f'root=pathlib.Path({remote!r})\nroot.mkdir(exist_ok=False)\n'
                  f'expected={{"code.zip":{sha256(self.attempt/"code.zip")!r},"wheels.zip":{sha256(self.attempt/"wheels.zip")!r}}}\n'
                  'for name,digest in expected.items():\n'
                  f' p=pathlib.Path("/content/{token}-"+name)\n'
                  ' if hashlib.sha256(p.read_bytes()).hexdigest()!=digest: raise ValueError("Transfer hash mismatch")\n'
                  ' with zipfile.ZipFile(p) as z:\n'
                  '  if not all((root/n).resolve().is_relative_to(root.resolve()) for n in z.namelist()): raise ValueError("Unsafe archive")\n  z.extractall(root)\n'
                  f'if hashlib.sha256(pathlib.Path("/content/{token}-inventory.json").read_bytes()).hexdigest()!={sha256(self.attempt/"inventory.json")!r}: raise ValueError("Inventory transfer mismatch")\n'
                  f'(root/"inventory.json").write_bytes(pathlib.Path("/content/{token}-inventory.json").read_bytes())\n'
                  'print("BBX_TRANSFER_COMPLETED")\n')
            self.transport.exec_code(token,code,'BBX_TRANSFER_COMPLETED')
            state['preparation']=self._phase(state,'prepare');state['status']='prepared';self._persist(state)
        except Exception as e:
            state.update(status='manual_review',error=safe_error(e));self._persist(state);raise
        return state
    def _inference(self,phase,config_path,allow_inference):
        if not allow_inference:raise ValueError('Explicit inference authorization required')
        state=self.state();required='prepared' if phase=='smoke' else 'smoke_passed'
        if state['status']!=required:raise ValueError('Phase order violated')
        if sha256(self.root/'experiment.json')!=state['config_sha256']:raise ValueError('Configuration changed')
        config=read_config(config_path);rows=[]
        papers=state['inventory'][:1] if phase=='smoke' else state['inventory']
        for paper in papers:
            key=(config.get('R2_PREFIX','').strip('/')+'/'+paper['name']).lstrip('/')
            rows.append({'identity':paper,'url':presign_get(config,key),'expires_at':time.time()+3600})
        state['status']=phase+'_running';self._persist(state)
        try:
            # Temporary URL-only file; permanent keys never leave the local signing process.
            with tempfile.TemporaryDirectory(dir=self.attempt,prefix='private-') as temp:
                request=Path(temp)/'requests.json';write_json(request,rows)
                if os.name!='nt':request.chmod(0o600)
                self.transport.upload(state['session'],request,state['remote_root']+'/private-requests.json')
            result=self._phase(state,phase)
            state[phase]=result
            if phase=='smoke':state['status']='smoke_passed'
            else:
                marker='BBX_ARCHIVE_COMPLETED';remote=state['remote_root']
                code=(f'import sys,json\nsys.path.insert(0,{remote!r})\nfrom bbx.remote import archive_results\n'
                      f'result=archive_results({remote!r})\nprint({marker!r})\nprint("BBX_ARCHIVE:"+json.dumps(result))')
                stdout=self.transport.exec_code(state['session'],code,marker)
                identity=json.loads(next(x[len('BBX_ARCHIVE:'):] for x in stdout.splitlines() if x.startswith('BBX_ARCHIVE:')))
                archive=self.attempt/'results.zip';self.transport.download(state['session'],remote+'/results.zip',archive)
                extract_verified(archive,self.attempt/'download',identity['sha256'])
                # Verify complete native receipts before interpreting absence as no detections.
                verify_collection(self.attempt/'download',state['inventory'],('heron','heron101','basic','standard'))
                if state.get('papers_dir'):
                    for p in state['inventory']:
                        if sha256(Path(state['papers_dir'])/p['name'])!=p['sha256']:raise ValueError('Local input PDF identity changed')
                    from .delivery import aggregate
                    aggregate(self.attempt/'download',state['inventory'],load_experiment(self.root/'experiment.json'),state['session'],
                              render=False)
                state['status']='downloaded_verified';self._persist(state)
                self.transport.stop(state['session']);state['status']='complete'
            self._persist(state);return state
        except Exception as e:
            state.update(status='manual_review',error=safe_error(e));self._persist(state);raise
    def smoke(self,config_path,*,allow_inference=False):return self._inference('smoke',config_path,allow_inference)
    def execute(self,config_path,*,allow_inference=False):return self._inference('execute',config_path,allow_inference)
