"""Colab CLI transport. No command is executed on import."""
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from .contracts import sha256
from .layout import resolve_path


def pack_code(root,destination):
    root=Path(root);destination=Path(destination)
    allowed=[(resolve_path(root/'run.py',root=root),'run.py'),(resolve_path(root/'experiment.json',root=root),'experiment.json')]
    for directory,extensions in [('bbx',{'.py'}),('requirements',{'.in','.lock'}),('model_manifests',{'.json'}),('tool_manifests',{'.json'})]:
        physical=resolve_path(root/directory,root=root)
        allowed.extend((p,str(Path(directory)/p.relative_to(physical))) for p in physical.rglob('*') if p.is_file() and p.suffix in extensions)
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
        for p,relative in allowed:z.write(p,relative)
    return {'path':str(destination),'sha256':sha256(destination)}


class ColabTransport:
    def __init__(self,workdir,runner=subprocess.run,executable='colab'):
        if executable=='colab':
            found=shutil.which('colab')
            fallback=Path.home()/'.local/bin/colab'
            executable=found or (fallback if fallback.is_file() else 'colab')
        self.workdir=Path(workdir);self.runner=runner;self.executable=str(executable)
    def command(self,args,timeout=60):
        try:result=self.runner([self.executable,*args],capture_output=True,text=True,check=True,timeout=timeout)
        except subprocess.CalledProcessError as e:
            self.workdir.mkdir(parents=True,exist_ok=True)
            (self.workdir/(uuid.uuid4().hex+'-failure.log')).write_text((e.stdout or '')+'\n'+(e.stderr or ''),encoding='utf-8')
            raise
        self.workdir.mkdir(parents=True,exist_ok=True)
        (self.workdir/(uuid.uuid4().hex+'-'+args[0]+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        return result.stdout
    def create(self,session,*,authorized=False):
        if not authorized:raise ValueError('Explicit session authorization required')
        if not re.fullmatch(r'bbx-[a-zA-Z0-9-]+',session):raise ValueError('Invalid session identity')
        self.command(['new','--session',session,'--gpu','A100'],timeout=180)
        return session
    def upload(self,session,local,remote):
        return self.command(['upload',str(local),remote,'--session',session],timeout=300)
    def download(self,session,remote,local):
        if Path(local).exists():raise ValueError('Never overwrite downloaded artifacts')
        return self.command(['download',remote,str(local),'--session',session],timeout=300)
    def stop(self,session):
        return self.command(['stop','--session',session],timeout=180)
    def exec_code(self,session,code,marker,timeout=600):
        # Never include credentials/URLs in this code. Sensitive requests use a private temporary transfer.
        self.workdir.mkdir(parents=True,exist_ok=True)
        path=self.workdir/(uuid.uuid4().hex+'.py');path.write_text(code,encoding='utf-8')
        stdout=self.command(['exec','--session',session,'--file',str(path),'--timeout',str(timeout)],timeout=timeout+30)
        if marker not in stdout.splitlines():raise ValueError('Missing explicit remote completion marker')
        return stdout
