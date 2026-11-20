"""Structural acceptance for the approved local layout."""
from pathlib import Path
import json
import subprocess
import sys
import zipfile

ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'bounding_boxes')


def test_approved_functional_layout():
    for rel in ('code/bbx', 'analytics/automatic',
                'analytics/geometry', 'analytics/targets', 'tests/code', 'tests/analytics',
                'raw_results/analytics', 'raw_results/feedback', 'raw_results/provenance', 'reports', 'reports/context/reports/execution',
                'reports/context/reports/analytics', 'reports/context/reports/tests', 'code/config/requirements'):
        assert (ROOT / rel).is_dir(), rel
    for rel in ('bbx', 'analysis_tools', 'deep_analysis', 'targets_analysis', 'results', 'analysis'):
        assert not (ROOT / rel).exists(), rel


def test_local_entrypoint_plan_never_allocates():
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'run.py'), 'colab', 'plan',
                             '--attempt', 'unused'], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['session_will_start'] is False


def test_flat_remote_bundle_contract_survives_layout(tmp_path):
    sys.path.insert(0, str(ROOT / 'code'))
    from bbx.transport import pack_code
    archive = tmp_path / 'bundle.zip'
    pack_code(ROOT, archive)
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        assert {'run.py', 'experiment.json', 'bbx/contracts.py', 'bbx/layout.py',
                'requirements/a.lock'} <= names
        assert not any(n.startswith(('code/', 'config/', 'raw_results/', 'runtime/')) for n in names)
        assert z.read('experiment.json') == (ROOT / 'code/config/experiment.json').read_bytes()
        unpack=tmp_path/'flat-bundle'
        z.extractall(unpack)
    result=subprocess.run([sys.executable,'-B',str(unpack/'run.py'),'colab','plan',
                           '--attempt','unused'],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['session_will_start'] is False


def test_historical_local_references_resolve_without_old_copies(tmp_path):
    sys.path.insert(0, str(ROOT / 'code'))
    from bbx.layout import resolve_path
    p = ROOT / 'results/mineru-nativefix-20261101T034122Z/viewer_source/viewer.json'
    assert resolve_path(p) == ROOT / 'raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/viewer.json'
    assert not p.exists()
    # An original storage ZIP must restore into current paths, not stale trees.
    import hashlib
    from bbx.artifact_store import restore_backup
    (tmp_path/'.layout.json').write_text(json.dumps({'prefixes':{'results/':'raw_results/code/'},'files':{}}))
    data=b'original';digest=hashlib.sha256(data).hexdigest()
    manifest={'schema':'bounding-box-artifact-storage/1','groups':[
        {'sha256':digest,'bytes':len(data),'paths':['results/fixture/pages/0.png']}]}
    backup=tmp_path/'legacy.zip'
    with zipfile.ZipFile(backup,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest))
        z.writestr('objects/'+digest,data)
    restore_backup(tmp_path,backup)
    assert (tmp_path/'raw_results/code/fixture/pages/0.png').read_bytes()==data
    assert not (tmp_path/'results').exists()


def test_storage_cli_is_available_without_pythonpath_setup(tmp_path):
    result = subprocess.run([sys.executable, '-B', str(ROOT/'run.py'), 'storage',
                             'inspect', '--root', str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['groups'] == []


def test_wheel_cache_is_at_workspace_root_for_local_and_flat_locks(tmp_path):
    from bbx.layout import wheel_directory
    assert wheel_directory(ROOT/'code/config/requirements/a.lock') == ROOT/'runtime/reused-wheels'
    assert wheel_directory(tmp_path/'requirements/a.lock') == tmp_path/'runtime/reused-wheels'
