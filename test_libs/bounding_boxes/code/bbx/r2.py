import datetime
import hashlib
import hmac
import shlex
import urllib.parse
import urllib.request
from pathlib import Path
from .contracts import check, sha256
from .environment import classify_artifact


def safe_error(e):
    return type(e).__name__ + (f': HTTP {e.code}' if hasattr(e,'code') else '')


def read_config(path):
    config={}
    for line in Path(path).read_text().splitlines():
        fields=shlex.split(line,comments=True)
        if fields and fields[0]=='export': fields=fields[1:]
        if fields and '=' in fields[0]:
            key,value=fields[0].split('=',1);config[key]=value
    for k in ('R2_ENDPOINT_URL','R2_BUCKET','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY'):
        if not config.get(k): raise ValueError('Missing required R2 configuration')
    return config


def signed_request(config, method, key):
    endpoint=urllib.parse.urlsplit(config['R2_ENDPOINT_URL'])
    if endpoint.scheme!='https' or endpoint.username or endpoint.password or endpoint.query or endpoint.path not in ('','/'):
        raise ValueError('Invalid R2 endpoint')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
    path='/'+urllib.parse.quote(config['R2_BUCKET']+'/'+key,safe='/~')
    payload=hashlib.sha256(b'').hexdigest()
    headers={'host':endpoint.netloc,'x-amz-content-sha256':payload,'x-amz-date':stamp}
    signed=';'.join(sorted(headers));canon=''.join(k+':'+headers[k]+'\n' for k in sorted(headers))
    request='\n'.join([method,path,'',canon,signed,payload]);scope=day+'/auto/s3/aws4_request'
    message='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(request.encode()).hexdigest()
    secret=('AWS4'+config['AWS_SECRET_ACCESS_KEY']).encode()
    for x in (day,'auto','s3','aws4_request'):secret=hmac.new(secret,x.encode(),hashlib.sha256).digest()
    signature=hmac.new(secret,message.encode(),hashlib.sha256).hexdigest()
    headers['Authorization']='AWS4-HMAC-SHA256 Credential='+config['AWS_ACCESS_KEY_ID']+'/'+scope+', SignedHeaders='+signed+', Signature='+signature
    return urllib.request.Request('https://'+endpoint.netloc+path,headers=headers,method=method)


def presign_get(config,key,expires=3600):
    if not 60<=expires<=3600:raise ValueError('Expiration must be 60..3600 seconds')
    endpoint=urllib.parse.urlsplit(config['R2_ENDPOINT_URL'])
    if endpoint.scheme!='https' or endpoint.username or endpoint.query or endpoint.path not in ('','/'):
        raise ValueError('Invalid endpoint')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
    scope=day+'/auto/s3/aws4_request';path='/'+urllib.parse.quote(config['R2_BUCKET']+'/'+key,safe='/~')
    fields={'X-Amz-Algorithm':'AWS4-HMAC-SHA256','X-Amz-Credential':config['AWS_ACCESS_KEY_ID']+'/'+scope,
            'X-Amz-Date':stamp,'X-Amz-Expires':str(expires),'X-Amz-SignedHeaders':'host'}
    query=urllib.parse.urlencode(sorted(fields.items()),quote_via=urllib.parse.quote,safe='~')
    canonical='\n'.join(['GET',path,query,'host:'+endpoint.netloc+'\n','host','UNSIGNED-PAYLOAD'])
    message='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
    secret=('AWS4'+config['AWS_SECRET_ACCESS_KEY']).encode()
    for x in (day,'auto','s3','aws4_request'):secret=hmac.new(secret,x.encode(),hashlib.sha256).digest()
    signature=hmac.new(secret,message.encode(),hashlib.sha256).hexdigest()
    return 'https://'+endpoint.netloc+path+'?'+query+'&X-Amz-Signature='+signature


def probe_r2(config_path, papers):
    config=read_config(config_path);checks=[]
    for p in papers:
        key=config.get('R2_PREFIX','').strip('/')+'/'+p['name']
        try:
            with urllib.request.urlopen(signed_request(config,'HEAD',key.lstrip('/')),timeout=20) as r:
                ok=r.status==200 and int(r.headers['Content-Length'])==p['bytes']
                checks.append(check('r2_head:'+p['name'],'PASS' if ok else 'FAIL',scope='local',http_status=r.status))
        except Exception as e:checks.append(check('r2_head:'+p['name'],'FAIL',safe_error(e),scope='local'))
    if papers:
        p=next((p for p in papers if p['name']=='12.pdf'),papers[0])
        try:
            key=(config.get('R2_PREFIX','').strip('/')+'/'+p['name']).lstrip('/')
            with urllib.request.urlopen(signed_request(config,'GET',key),timeout=30) as r:data=r.read()
            ok=len(data)==p['bytes'] and data.startswith(b'%PDF-') and hashlib.sha256(data).hexdigest()==p['sha256']
            checks.append(check('r2_get:'+p['name'],'PASS' if ok else 'FAIL',scope='local'))
        except Exception as e:checks.append(check('r2_get:'+p['name'],'FAIL',safe_error(e),scope='local'))
    return checks


def download_verified(fetch, destination, identity):
    destination=Path(destination)
    if classify_artifact(destination,identity)=='valid':return {'status':'PASS','reused':True}
    data=fetch()
    if len(data)!=identity['bytes'] or hashlib.sha256(data).hexdigest()!=identity['sha256'] or not data.startswith(b'%PDF-'):
        raise ValueError('Downloaded PDF identity mismatch')
    if destination.exists():raise ValueError('Existing corrupt file preserved; use a new destination')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as f:f.write(data)
    return {'status':'PASS','reused':False}
