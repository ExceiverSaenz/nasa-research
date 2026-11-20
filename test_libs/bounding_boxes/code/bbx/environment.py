import json
import subprocess
import tempfile
from pathlib import Path
from .contracts import check, sha256, exit_code
from .layout import resolve_path, wheel_directory


def classify_artifact(path, manifest):
    p=Path(path)
    if not p.is_file(): return 'missing'
    return 'valid' if p.stat().st_size==manifest['bytes'] and sha256(p)==manifest['sha256'] else 'corrupt'


def inspect_environment(python, lock):
    python=Path(python); lock=resolve_path(lock)
    if not python.is_file(): return [check('interpreter','NOT_RUN','Interpreter absent')]
    if not lock.is_file(): return [check('lock','NOT_RUN','Hashed lock absent')]
    probe="import sys,json,importlib.metadata as m;print(json.dumps({'version':list(sys.version_info[:2]),'prefix':sys.prefix,'base':sys.base_prefix,'packages':{d.metadata['Name'].lower():d.version for d in m.distributions()}}))"
    try:
        result=subprocess.run([str(python),'-I','-c',probe],capture_output=True,text=True,timeout=30,check=True)
        data=json.loads(result.stdout)
        isolated=data['prefix']!=data['base']
        cfg=python.parent.parent/'pyvenv.cfg'
        isolated=isolated and cfg.exists() and 'include-system-site-packages = false' in cfg.read_text().lower()
        checks=[check('isolation','PASS' if isolated and data['version']==[3,11] else 'FAIL',packages=data['packages'])]
        # Let pip parse hashes/markers/direct references, without dependency downloads or installation.
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp)/'pip.json'
            command=[str(python),'-m','pip','install','--dry-run','--no-index','--find-links',str(wheel_directory(lock)),'--require-hashes','--report',str(report),'-r',str(lock)]
            p=subprocess.run(command,capture_output=True,text=True,timeout=60)
            satisfied=p.returncode==0 and report.exists() and verify_pip_report(json.loads(report.read_text()))
        checks.append(check('lock_satisfied','PASS' if satisfied else 'FAIL',exit_code=p.returncode))
        p=subprocess.run([str(python),'-m','pip','check'],capture_output=True,text=True,timeout=30)
        checks.append(check('pip_check','PASS' if p.returncode==0 else 'FAIL',exit_code=p.returncode))
        p=subprocess.run([str(python),'-I',str(Path(__file__).with_name('native_contract.py'))],
                         capture_output=True,text=True,timeout=60)
        try:
            native=json.loads(p.stdout)
            compatible=p.returncode==0 and native.get('schema')=='mineru-native-contract/1' and native.get('status')=='PASS'
        except (ValueError,AttributeError):native={};compatible=False
        checks.append(check('native_span_contract','PASS' if compatible else 'FAIL',
                            'CPU native ABI gate; no model inference',exit_code=p.returncode,receipt=native))
        if not compatible:return checks
        for module in ('torch','torchvision','transformers','mineru','pypdfium2'):
            p=subprocess.run([str(python),'-I','-c',f'import {module}'],capture_output=True,text=True,timeout=60)
            checks.append(check('import:'+module,'PASS' if p.returncode==0 else 'FAIL'))
        return checks
    except (subprocess.SubprocessError,ValueError,OSError) as e:
        return [check('environment','FAIL',type(e).__name__)]


def verify_pip_report(report):
    return report.get('install') == []


def prepare_environment(spec, *, checks=None, apply=False, installer=None):
    checks=checks if checks is not None else inspect_environment(spec['python'],spec['lock'])
    if exit_code(checks)==0: return {'action':'reuse','checks':checks}
    if any(c['status']=='FAIL' for c in checks): raise ValueError('Incompatible environment; create a separate destination')
    if not apply: return {'action':'prepare_required','checks':checks}
    if installer is None: raise ValueError('Explicit verified installer required')
    installer(spec)
    return {'action':'prepared_requires_reinspection','checks':checks}
