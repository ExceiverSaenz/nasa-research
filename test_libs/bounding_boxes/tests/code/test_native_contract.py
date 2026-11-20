import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from contextlib import nullcontext
from unittest.mock import patch

import pytest

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0,str(ROOT))
CACHE=ROOT/'runtime/private-ranges-investigation'
RUNNER=Path(__file__).with_name('native_contract_runner.py')


def cached_wheel(version):
    rows=json.loads((CACHE/'artifacts.json').read_text())
    row=next(r for r in rows if r['name']=='docvortex' and r['version']==version)
    p=CACHE/row['filename']
    assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    return p


@pytest.mark.parametrize('environment',['a','b'])
def test_locked_docvortex_accepts_mineru_single_private_range(environment,request,tmp_path):
    if not request.config.getoption('--native-contract'):
        pytest.skip('Explicit --native-contract required; uses verified cached binaries on CPU')
    assert sys.platform=='win32','This characterization uses cached Windows wheels'
    version=re.search(r'^docvortex==([^\s]+)',(ROOT/'config/requirements'/f'{environment}.lock').read_text(),re.M).group(1)
    p=subprocess.run([sys.executable,'-B',str(RUNNER),str(cached_wheel(version)),str(tmp_path),'papers/SiC_papers/10.pdf'],capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stderr
    assert json.loads(p.stdout)['status']=='PASS'


@pytest.mark.parametrize('version,compatible',[('0.6.7',True),('0.6.8',False),('0.6.9',False)])
def test_preparation_gate_exercises_real_native_binding(version,compatible,request,tmp_path):
    if not request.config.getoption('--native-contract'):
        pytest.skip('Explicit cached native CPU characterization only')
    p=subprocess.run([sys.executable,'-B',str(RUNNER),str(cached_wheel(version)),str(tmp_path),'papers/SiC_papers/10.pdf','--gate'],capture_output=True,text=True,timeout=60)
    if compatible:
        assert p.returncode==0,p.stderr
    else:
        assert p.returncode!=0 and 'private_ranges' in p.stderr,p.stderr


@pytest.mark.parametrize('returncode,stdout',[(1,''),(0,'not a JSON success receipt')])
def test_environment_does_not_accept_failed_native_contract(tmp_path,returncode,stdout):
    from bbx.environment import inspect_environment
    python=tmp_path/'env/bin/python';python.parent.mkdir(parents=True);python.touch()
    (python.parent.parent/'pyvenv.cfg').write_text('include-system-site-packages = false')
    lock=tmp_path/'requirements/a.lock';lock.parent.mkdir();lock.write_text('candidate --hash=sha256:example')
    def run(command,**kwargs):
        if '-c' in command and 'm.distributions()' in command[-1]:
            data={'version':[3,11],'prefix':str(python.parent.parent),'base':'/base','packages':{'mineru':'4.0.12','docvortex':'0.6.7'}}
            return subprocess.CompletedProcess(command,0,json.dumps(data),'')
        if '--report' in command:
            Path(command[command.index('--report')+1]).write_text('{"install": []}')
        if any(Path(x).name=='native_contract.py' for x in command):
            return subprocess.CompletedProcess(command,returncode,stdout,'TypeError: private_ranges')
        return subprocess.CompletedProcess(command,0,'','')
    with patch('bbx.environment.subprocess.run',side_effect=run), patch('bbx.environment.tempfile.TemporaryDirectory',return_value=nullcontext(str(tmp_path))):
        checks=inspect_environment(python,lock)
    assert any(c['id']=='native_span_contract' and c['status']=='FAIL' for c in checks),checks


def test_full_cpu_probe_runs_without_ml_stack(request):
    if not request.config.getoption('--native-contract'):
        pytest.skip('Explicit CPU diagnostic environment only')
    python=CACHE/'cpu-env/Scripts/python.exe'
    assert python.exists(),'Prepare the documented CPU diagnostic environment first'
    code=("import importlib.util,runpy; "
          "assert importlib.util.find_spec('torch') is None; "
          "assert importlib.util.find_spec('vllm') is None; "
          f"runpy.run_path({str(ROOT/'code/bbx/native_contract.py')!r},run_name='__main__')")
    p=subprocess.run([str(python),'-I','-B','-c',code],capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stderr
    receipt=json.loads(p.stdout)
    assert receipt['status']=='PASS' and receipt['versions']['docvortex']=='0.6.7'


