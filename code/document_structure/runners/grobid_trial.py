"""Explicit single-request client. Importing never starts services or loads models."""
import argparse
import hashlib
import http.client
import json
import socket
import subprocess
import time
import uuid
from pathlib import Path
from reading_order.export import digest,write

PIN='grobid/grobid@sha256:cf3e24bba3a3e8492488bd07e0c3beb2cd681724a760815488c7e44cb7f47cf3'
COMPONENTS={'segmentation','header','fulltext','name-header','name-citation','reference-segmenter','citation','affiliation-address','figure','table','date'}


def verify_lock(lock,pdf,baseline):
    if lock.get('schema_version')!='grobid-runtime-lock/1' or lock.get('image')!=PIN or lock.get('platform')!='linux/amd64' or lock.get('version')!='0.9.1':raise ValueError('runtime identity mismatch')
    for key in ('prepared','image_layers_verified','config_verified','models_verified','network_egress_disabled','funders_parameter_verified'):
        if lock.get(key) is not True:raise ValueError('lock incomplete: '+key)
    if lock.get('resources')!=dict(cpus=4,memory_gib=8,java_heap_gib=4):raise ValueError('resource policy mismatch')
    files=lock.get('files',{});models=lock.get('model_paths',[])
    if not models or not lock.get('config_path') or not COMPONENTS.issubset(lock.get('components',{})):raise ValueError('missing cascade/config inventory')
    required=set(models+[lock['config_path']])
    for name in lock['components']:
        paths=lock['components'][name]
        if not paths:raise ValueError('missing component '+name)
        required.update(paths)
    if not required.issubset(files):raise ValueError('unhashed runtime files')
    for path,sha in files.items():
        if not Path(path).is_file() or digest(path)!=sha:raise ValueError('runtime file hash mismatch: '+path)
    if digest(pdf)!=lock.get('pdf_sha256') or digest(baseline)!=lock.get('baseline_sha256'):raise ValueError('input hash mismatch')
    if lock.get('funders_parameter') not in ('consolidatFunders','consolidateFunders'):raise ValueError('unverified wire parameter')
    return True


def parameters(funders):
    return [('consolidateHeader','0'),('consolidateCitations','0'),(funders,'0'),('includeRawAffiliations','1'),('includeRawCitations','1'),('includeRawCopyrights','1'),('generateIDs','1'),('segmentSentences','0'),('debugMode','0'),('start','-1'),('end','-1')]+[('teiCoordinates',x) for x in ('title','persName','affiliation','head','p','ref','figure','formula','note','biblStruct')]


def attest_service(lock):
    """Read-only attestation of an already authorized, running dedicated service."""
    container=lock.get('service_container_id','')
    if not container or not all(c in '0123456789abcdef' for c in container) or len(container)!=64:raise ValueError('missing service identity')
    def inspect(args):return json.loads(subprocess.run(['docker']+args,check=True,capture_output=True,text=True,timeout=20).stdout)[0]
    c=inspect(['inspect',container]);image=inspect(['image','inspect',c['Image']]);host=c['HostConfig']
    if not c['State']['Running'] or PIN not in image.get('RepoDigests',[]) or image.get('Os')!='linux' or image.get('Architecture')!='amd64':raise ValueError('live image mismatch')
    if host.get('Memory')!=8*1024**3 or host.get('NanoCpus')!=4*10**9 or host.get('DeviceRequests'):raise ValueError('live resources mismatch')
    if any(m['Destination'].startswith(('/opt/grobid','/opt/delft')) for m in c.get('Mounts',[])):raise ValueError('model/config runtime override')
    for key in ('Entrypoint','Cmd'):
        if c['Config'].get(key)!=image['Config'].get(key):raise ValueError('image entrypoint override')
    image_env={v.split('=',1)[0]:v.split('=',1)[1] for v in image['Config'].get('Env',[])}
    actual_env={v.split('=',1)[0]:v.split('=',1)[1] for v in c['Config'].get('Env',[])}
    if actual_env.get('JAVA_OPTS')!='-Xmx4g' or {k:v for k,v in actual_env.items() if k!='JAVA_OPTS'}!={k:v for k,v in image_env.items() if k!='JAVA_OPTS'}:raise ValueError('runtime environment override')
    bindings=c['NetworkSettings']['Ports'].get('8070/tcp',[])
    if bindings!=[{'HostIp':'127.0.0.1','HostPort':'8070'}]:raise ValueError('service is not bound exclusively to loopback')
    networks=c['NetworkSettings']['Networks']
    if not networks or any(not inspect(['network','inspect',n]).get('Internal') for n in networks):raise ValueError('egress network not isolated')
    conn=http.client.HTTPConnection('127.0.0.1',8070,timeout=20)
    try:
        conn.request('GET','/api/version');response=conn.getresponse();version=response.read().decode('utf-8').strip().strip('"')
        if response.status!=200 or not (version=='0.9.1' or version.startswith('0.9.1-')):raise ValueError('service version mismatch')
    finally:conn.close()


def transport(url,body,headers,timeout,raw_path=None,response_meta_path=None):
    # Fixed loopback endpoint; http.client never follows a redirect with PDF content.
    conn=http.client.HTTPConnection('127.0.0.1',8070,timeout=timeout)
    chunks=[];stream=None;result=dict(raw=b'',status='execution_state_unknown')
    try:
        conn.request('POST','/api/processFulltextDocument',body,headers);r=conn.getresponse();result.update(http_status=r.status,response_headers=dict(r.getheaders()))
        if response_meta_path:write(Path(response_meta_path),dict(http_status=r.status,response_headers=result['response_headers']))
        if raw_path:stream=Path(raw_path).open('xb')
        def save(chunk):
            if chunk:
                chunks.append(chunk)
                if stream:stream.write(chunk);stream.flush()
        try:
            while True:
                chunk=r.read1(65536)
                if not chunk:
                    if getattr(r,'length',0):raise http.client.IncompleteRead(b'',r.length)
                    break
                save(chunk)
            result['status']='response_received' if r.status==200 else 'failed_or_empty'
        except http.client.IncompleteRead as exc:save(exc.partial);result['error']=repr(exc)
        except (TimeoutError,OSError) as exc:result['error']=repr(exc)
    finally:
        if stream:stream.close()
        conn.close()
    result['raw']=b''.join(chunks)
    if result['status']=='response_received' and not result['raw']:result['status']='failed_or_empty'
    return result


def request_once(pdf,baseline,lock_path,destination,authorized=False,transport=None):
    if not authorized:raise PermissionError('Explicit execution authorization required')
    pdf=Path(pdf).resolve();baseline=Path(baseline).resolve();lp=Path(lock_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    lock=json.loads(lp.read_text(encoding='utf-8'));verify_lock(lock,pdf,baseline)
    dest.mkdir(parents=True,exist_ok=False);(dest/'raw').mkdir()
    params=parameters(lock['funders_parameter']);boundary='grobid-'+uuid.uuid4().hex;chunks=[]
    for k,v in params:chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="input"; filename="paper.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode(),pdf.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()])
    run=dict(run_id=str(uuid.uuid4()),pdf_path=str(pdf),pdf_sha256=digest(pdf),baseline_sha256=digest(baseline),lock_sha256=digest(lp),models_ref='runtime-lock.json#/components',config_ref='runtime-lock.json#/config_path',parameters=params,attempts=0,status='reserved',models_executed=False,wall_start=time.time(),timeout_s=900)
    write(dest/'runtime-lock.json',lock);write(dest/'reservation.json',run)
    started=time.monotonic()
    try:
        if transport is None:attest_service(lock)
        run['attempts']=1;run['model_execution_requested']=True;run['models_executed']=None
        # The durable reservation marks submission before the call, including interruption cases.
        write(dest/'submitted.json',dict(run_id=run['run_id'],attempts=1,pdf_sha256=run['pdf_sha256']))
        call=transport or globals()['transport'];args=('http://127.0.0.1:8070/api/processFulltextDocument',b''.join(chunks),{'Content-Type':'multipart/form-data; boundary='+boundary},900)
        response=call(*args) if transport else call(*args,raw_path=dest/'raw/response.tei.xml',response_meta_path=dest/'response-headers.json')
        if isinstance(response,dict):
            raw=response.pop('raw');run.update(response)
        else:
            status,raw,headers=response;run.update(http_status=status,response_headers=headers,status='response_received' if status==200 and raw else 'failed_or_empty')
        if not (dest/'raw/response.tei.xml').exists():(dest/'raw/response.tei.xml').write_bytes(raw)
        run['response_sha256']=hashlib.sha256(raw).hexdigest()
        if run.get('status')=='response_received' and run.get('http_status')==200:run['models_executed']=True
    except (socket.timeout,TimeoutError) as exc:run.update(status='execution_state_unknown',error=str(exc))
    except Exception as exc:run.update(status='execution_state_unknown' if run['attempts'] else 'preflight_failed',error=type(exc).__name__+': '+str(exc))
    run['elapsed_seconds']=time.monotonic()-started;run['wall_end']=time.time();write(dest/'run.json',run)
    return run


if __name__=='__main__':
    p=argparse.ArgumentParser(description='Does not start Docker; requires independently prepared/attested service and explicit execution authorization')
    p.add_argument('pdf');p.add_argument('baseline');p.add_argument('lock');p.add_argument('destination');p.add_argument('--authorized-execution',action='store_true');a=p.parse_args()
    print(json.dumps(request_once(a.pdf,a.baseline,a.lock,a.destination,authorized=a.authorized_execution),indent=2))
