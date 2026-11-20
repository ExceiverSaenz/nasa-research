"""Incremental verification via Contents API; no kernel execution or installation."""
import sys,json,hashlib,base64,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from email.parser import BytesParser
import requests
from colab_cli.state import StateStore
from colab_cli.contents import ContentsClient
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.preflight import require_test_receipt
base=Path(__file__).parent
class ArtifactReadError(RuntimeError):
    def __init__(self,path,status):self.path,self.status=path,status
try:
    fresh='--fresh' in sys.argv
    checked=require_test_receipt(root,base/'offline-receipts-linux/test-receipt.json')
    files={n:s for n,s in checked['code_files'].items() if n.startswith('code/reading_order/')}
    session=sys.argv[sys.argv.index('--session')+1] if '--session' in sys.argv else ('order-collection-20261102-r5' if fresh else 'order-collection-20261102-r4')
    environment_folder=base/('environment-'+session.rsplit('-',1)[-1])
    state=StateStore().get(session);assert state.accelerator=='A100'
    connection=ContentsClient(state)
    with (environment_folder/'api-upload.log').open('w') as log:
        for name in ('colab_backend.py','collection.py'):
            subprocess.run([str(Path.home()/'.local/bin/colab'),'upload','-s',session,str(root/'code/reading_order'/name),
                '/content/order-code/reading_order/'+name],stdout=log,stderr=subprocess.STDOUT,timeout=45,check=True)
    def get(path,directory=False):
        params={'authuser':'0','colab-runtime-proxy-token':connection.token}
        if not directory:params['format']='base64'
        for attempt in range(3):
            try:
                response=requests.get(connection.base_url+'/api/contents/'+quote(path.strip('/'),safe='/'),params=params,timeout=20)
                break
            except requests.RequestException:
                if attempt==2:raise ArtifactReadError(path,'connection_interrupted') from None
                time.sleep(.5)
        if not response.ok:raise ArtifactReadError(path,response.status_code)
        value=response.json()
        if directory:return value['content']
        return base64.b64decode(value['content']) if value['format']=='base64' else value['content'].encode()
    def code_hash(item):
        name,expected=item;actual=hashlib.sha256(get('content/order-code/'+name.removeprefix('code/'))).hexdigest()
        assert actual==expected;return name,actual
    with ThreadPoolExecutor(max_workers=4) as pool:actual_files=dict(pool.map(code_hash,files.items()))
    if fresh:
        previous_raw=get('content/order-prepared.json');previous=json.loads(previous_raw)
        assert previous['session']==session and previous['cuda_verified_by_bootstrap']
        assert previous['code_files']==files
        assert previous['code_archive_sha256']==hashlib.sha256((environment_folder/'code-only.tar.gz').read_bytes()).hexdigest()
        previous_path=environment_folder/'committed-preparation.json';previous_path.write_bytes(previous_raw)
    else:
        previous_path=environment_folder/'committed-preparation.json';previous=json.loads(previous_path.read_text())
        assert previous['session']==session and previous['cuda_verified_by_bootstrap']
    remote_root='content/order-config-20261102/'
    seal_raw=get(remote_root+'prepared-identity.json');seal=json.loads(seal_raw)
    assert hashlib.sha256(seal_raw).hexdigest()==previous['prepared_identity_sha256']
    assert hashlib.sha256(get(remote_root+'requirements.lock')).hexdigest()==previous['lock_sha256']
    assert hashlib.sha256(get(remote_root+'xy-worker/target/release/order-memory-worker')).hexdigest()==previous['worker_sha256']
    site=remote_root+'venv/lib/python3.11/site-packages/'
    metadata_paths=[site+v['name']+'/METADATA' for v in get(site,directory=True) if v['name'].endswith('.dist-info')]
    def version(path):
        metadata=BytesParser().parsebytes(get(path))
        return metadata['Name'].lower().replace('_','-'),metadata['Version']
    with ThreadPoolExecutor(max_workers=4) as pool:versions=dict(pool.map(version,metadata_paths))
    assert versions==seal['versions']
    result=dict(previous,code_files=actual_files,verification_method='Contents API: all code hashes, sealed identity, lock, worker and installed package metadata',
        installed_packages_verified=len(versions),cuda_verification_reference=dict(path=str(previous_path),sha256=hashlib.sha256(previous_path.read_bytes()).hexdigest()),
        code_update_files=['code/reading_order/colab_backend.py','code/reading_order/collection.py'])
    receipt_name='http-verified-environment.json' if fresh else 'receipts-environment.json'
    target=environment_folder/receipt_name
    if target.exists():raise FileExistsError('Environment receipt already exists')
    target.write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(status='PASS',code_files=len(files),installed_packages=len(versions),lock_sha256=result['lock_sha256'])),flush=True)
except Exception as error:
    print(json.dumps(dict(status='FAIL',error_type=type(error).__name__,artifact=getattr(error,'path',None),http_status=getattr(error,'status',None))),flush=True);raise SystemExit(1)
