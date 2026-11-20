"""Run actual offline tests on WSL; no package installation or GPU changes."""
import sys,os,json,hashlib,urllib.request,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];base=Path(__file__).parent
dependencies=[]
lock=(root/'raw_results/tests_results/20261102T052716Z-config-7e26b3/requirements.lock').read_text()
for name,version in [('pytest','8.4.2'),('pluggy','1.7.0'),('iniconfig','2.3.1')]:
    info=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=30))
    entry=next(v for v in info['urls'] if v['filename'].endswith('py3-none-any.whl'))
    path=base/entry['filename'];sha=entry['digests']['sha256'];assert sha in lock
    if not path.exists():
        raw=urllib.request.urlopen(entry['url'],timeout=30).read();assert hashlib.sha256(raw).hexdigest()==sha;path.write_bytes(raw)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    dependencies.append(str(path))
output=base/(sys.argv[1] if len(sys.argv)>1 else 'offline-bounded-client-linux');output.mkdir(exist_ok=False)
environment=dict(os.environ,PYTHONPATH=os.pathsep.join(dependencies),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
with tempfile.TemporaryDirectory(prefix='order-offline-tests-') as temp:
    command=[sys.executable,'-B','-m','pytest',str(root/'test'),'-q','-p','no:cacheprovider','--basetemp',str(Path(temp)/'cases'),'--junitxml',str(output/'tests.xml')]
    with (output/'pytest.log').open('w') as stream:result=subprocess.run(command,env=environment,stdout=stream,stderr=subprocess.STDOUT)
sys.path.insert(0,str(root/'code'))
from reading_order.preflight import code_fingerprint
(output/'test-receipt.json').write_text(json.dumps(dict(status='PASS' if result.returncode==0 else 'FAIL',command=command,
    platform='WSL Ubuntu22.04',temporary_filesystem='native Linux /tmp',isolated_dependencies=dependencies,
    code_files=code_fingerprint(root)),indent=2))
print((output/'pytest.log').read_text()[-2200:],flush=True)
raise SystemExit(result.returncode)
