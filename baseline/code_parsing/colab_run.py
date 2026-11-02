"""Plan locally by default; --execute explicitly authorizes a future A100 run."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

from .common import ROOT, digest, IntegrityService, write_json
from .r2 import PREFIX, PdfSelector, R2Client, R2Credentials


from .contracts import Integrity, CommandRunner, Session


class BaselinePlanner:
    def __init__(self, *, integrity: Integrity | None = None, selector=None):
        self.integrity = integrity if integrity is not None else IntegrityService()
        self.selector = selector if selector is not None else PdfSelector()

    def plan(self, directory, names, all_papers):
        receipt=self.integrity.verify_lock()
        return dict(schema='baseline-plan/1', gpu='A100', python='3.11.16', r2_prefix=PREFIX,
            papers=self.selector.select(directory,names,all_papers), lock_sha256=receipt['lock_sha256'],
            input_sha256=receipt['input_sha256'],
            install_command_flags=['--require-hashes','--only-binary=:all:'],
            a100_validation='pending', automatic_retries=False)

class ColabSession:
    """CLI IO for a single explicitly owned session."""

    def __init__(self, session, local, *, runner: CommandRunner | None = None):
        self.session = session
        self.local = Path(local)
        self.runner = runner if runner is not None else subprocess.run

    @staticmethod
    def require_marker(output, run_id, phase):
        if 'BASELINE_COMPLETED:'+run_id+':'+phase not in output.splitlines():
            raise RuntimeError('Remote phase has no explicit completion marker: '+phase)

    def command(self, args):
        args = [str(a) for a in args]
        if args.count('-s') != 1 or args.index('-s')+1 >= len(args) or args[args.index('-s')+1] != self.session:
            raise ValueError('Command must address only the owned session')
        result=self.runner([str(a) for a in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        with (self.local/'cli.log').open('a',encoding='utf-8') as log:
            log.write('\nCOMMAND: '+' '.join(map(str,args))+'\n'+result.stdout); log.flush()
        if result.returncode: raise RuntimeError('Colab command failed; inspect '+str(self.local/'cli.log'))
        return result.stdout

    def run_phase(self, phase, python, run_id):
        script=self.local/(phase+'.py')
        script.write_text('import subprocess\nfrom pathlib import Path\np=Path("/content/baseline/'+phase+'.log")\n'
            'with p.open("w") as log:\n r=subprocess.run('+repr([python,'-B','-m','baseline.code_parsing.worker',phase,'--run-id',run_id])+',cwd="/content",stdout=log,stderr=subprocess.STDOUT,text=True)\n'
            'print(p.read_text(),flush=True)\nr.check_returncode()\n')
        self.require_marker(self.command(['colab','exec','-s',self.session,'-f',script,'--timeout','14400']),run_id,phase)

class BaselineController:
    """Coordinate collaborators; it does not implement signing or process IO."""

    SOURCE_FILES = ('__init__.py','code_parsing/__init__.py','code_parsing/common.py',
                    'code_parsing/contracts.py','code_parsing/r2.py','code_parsing/parsing.py',
                    'code_parsing/worker.py','requirements.in','requirements.lock',
                    'bootstrap.lock','lock-verification.json')

    def __init__(self, root=ROOT, *, integrity: Integrity | None = None, session_factory=None,
                 credentials=None, r2_factory=None, temporary_directory=None):
        self.root = Path(root)
        self.integrity = integrity if integrity is not None else IntegrityService(self.root)
        self.session_factory = session_factory if session_factory is not None else ColabSession
        self.credentials = credentials if credentials is not None else R2Credentials
        self.r2_factory = r2_factory if r2_factory is not None else R2Client
        self.temporary_directory = temporary_directory if temporary_directory is not None else tempfile.TemporaryDirectory

    def execute(self, value, env_file, remote_python, keep_session=False):
        if keep_session: raise ValueError('This validation requires closing every owned session')
        if sys.platform!='linux' or not shutil.which('colab'): raise RuntimeError('Use Ubuntu/WSL with configured Colab CLI')
        for previous in (self.root/'runtime/colab-attempts').glob('*/status.json'):
            old=json.loads(previous.read_text())
            if old.get('session_creation_attempted') and not old.get('session_closed'):
                raise RuntimeError('Previous owned session closure unconfirmed: '+str(previous))
        client = self.r2_factory(self.credentials.load(env_file))
        run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        session='baseline-'+run_id.lower(); local=self.root/'runtime/colab-attempts'/run_id
        local.mkdir(parents=True)
        transport: Session = self.session_factory(session, local)
        status=dict(value,id=run_id,session=session,status='prepared',session_closed=False)
        def save(): write_json(local/'status.json',status)
        save()
        try:
            source=local/'source.tar.gz'
            names=self.SOURCE_FILES
            hashes={name:digest(self.root/name) for name in names}
            with tarfile.open(source,'w:gz') as tar:
                for name in names: tar.add(self.root/name,arcname='baseline/'+name,recursive=False)
            if hashes!={name:digest(self.root/name) for name in names}: raise ValueError('Source changed while packaging')
            write_json(local/'source-manifest.json',hashes)
            write_json(local/'selection.json',value)
            status['session_creation_attempted']=True; save()
            transport.command(['colab','new','-s',session,'--gpu','A100'])
            status.update(status='session_created',session_created=True); save()
            transport.command(['colab','upload','-s',session,source,'/content/baseline-source.tar.gz'])
            bootstrap=local/'bootstrap.py'
            bootstrap.write_text('import hashlib,tarfile\nfrom pathlib import Path\np=Path("/content/baseline-source.tar.gz")\nassert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(digest(source))+'\nassert not Path("/content/baseline").exists()\nwith tarfile.open(p) as t:t.extractall("/content",filter="data")\n')
            transport.command(['colab','exec','-s',session,'-f',bootstrap])
            status['status']='preparing'; save(); transport.run_phase('prepare',remote_python,run_id)
            # Sign only after model/environment preparation, to avoid expiration.
            private=local/'private'; private.mkdir()
            with self.temporary_directory(prefix='request-',dir=private) as tmp:
                request=Path(tmp)/'request.json'; client.write_request(request,value['papers'])
                transport.command(['colab','upload','-s',session,request,'/content/baseline-request.json'])
            status['status']='parsing'; save(); transport.run_phase('parse','/content/baseline/runtime/environment/bin/python',run_id)
            archive=local/'results.tar.gz'; checksum=local/'results.sha256'
            transport.command(['colab','download','-s',session,'/content/baseline-results.tar.gz',archive])
            transport.command(['colab','download','-s',session,'/content/baseline-results.sha256',checksum])
            if digest(archive)!=checksum.read_text().strip(): raise ValueError('Transport SHA256 mismatch')
            destination=self.root/'results'/run_id; self.integrity.extract(archive,destination); self.integrity.verify_files(destination)
            for folder in (destination/'papers').glob('*'):
                if folder.is_dir(): self.integrity.verify_files(folder)
            result=json.loads((destination/'status.json').read_text())
            status.update(status='backup_verified',result_directory=str(destination),batch_status=result['status']); save()
            if result['status']!='completed': raise RuntimeError('Partial/failed results preserved; inspect before retrying')
            expected={p['sha256'] for p in value['papers']}
            if {p['sha256'] for p in result['papers']}!=expected: raise ValueError('Result selection mismatch')
            status['status']='completed'; save()
            return status
        except BaseException as exc:
            status.update(status='manual_review',error=type(exc).__name__+': '+str(exc)); save()
            raise
        finally:
            if status.get('session_creation_attempted'):
                # Only this freshly named session is ever addressed, including recovery.
                try:
                    if status.get('status')!='completed':
                        try:
                            recovery=local/'recover.py'
                            recovery.write_text('from pathlib import Path\nimport tarfile\nr=Path("/content/baseline")\n'
                                'with tarfile.open("/content/baseline-recovery.tar.gz","w:gz") as t:\n'
                                ' for p in list((r/"runtime").glob("*.json"))+list(r.glob("*.log"))+list((r/"results").rglob("*")):\n'
                                '  if p.is_file():t.add(p,arcname=p.relative_to(r).as_posix(),recursive=False)\n')
                            transport.command(['colab','exec','-s',session,'-f',recovery,'--timeout','120'])
                            transport.command(['colab','download','-s',session,'/content/baseline-recovery.tar.gz',local/'recovery.tar.gz'])
                            status['recovery_downloaded']=True
                        except Exception as recovery_error:
                            status['recovery_error']=str(recovery_error)
                finally:
                    # Recovery IO errors and interruptions must not skip stop.
                    try:
                        confirmation=transport.command(['colab','stop','-s',session])
                        status['closure_output']=confirmation
                        status['session_closed']='[colab] Session terminated.' in confirmation
                        if not status['session_closed']: raise RuntimeError('Owned session closure not confirmed')
                    except Exception as close_error:
                        status.update(status='closure_unconfirmed',closure_error=str(close_error))
                        save()
                        raise RuntimeError('Do not create another session: closure unconfirmed for '+session) from close_error
                    save()

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',required=True,type=Path,help='Local PDFs, identity references only')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--papers',nargs='+'); group.add_argument('--all',action='store_true')
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--plan',action='store_true'); action.add_argument('--execute',action='store_true')
    parser.add_argument('--env-file',type=Path,default=Path.home()/'.config/nasa-research/r2.env')
    parser.add_argument('--remote-python',default='python3',help='Remote bootstrap Python with HTTPS; provisions isolated 3.11.16')
    parser.add_argument('--keep-session',action='store_true')
    args=parser.parse_args(argv)
    value=BaselinePlanner().plan(args.source_dir,args.papers or [],args.all)
    if args.execute: value=BaselineController().execute(value,args.env_file,args.remote_python,args.keep_session)
    print(json.dumps(value,indent=2))

if __name__=='__main__': main()
