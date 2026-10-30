#!/usr/bin/env python3
"""Sign R2 PDF requests on Ubuntu; download/verify them on the execution host.

Requests contain temporary bearer URLs: keep them private and do not log them.
Permanent credentials are read only by the sign command, never copied to requests.
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import quote, urlsplit
from setup_models import fetch_file

ROOT=Path(__file__).resolve().parent


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):value.update(block)
    return value.hexdigest()


def read_settings(path):
    path=path.expanduser()
    if os.name=='posix' and path.stat().st_mode & 0o077:
        raise ValueError('Credential file requires private permissions (chmod 600)')
    values={}
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:]
        name,sep,value=line.partition('=')
        if not sep:raise ValueError('Invalid credential file syntax')
        values[name.strip()]=' '.join(shlex.split(value,comments=True))
    for name in ('R2_ENDPOINT_URL','R2_BUCKET','R2_PREFIX','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY'):
        if not values.get(name):raise ValueError('Missing setting: '+name)
    endpoint=urlsplit(values['R2_ENDPOINT_URL'])
    if (endpoint.scheme!='https' or not endpoint.hostname
            or not endpoint.hostname.endswith('.r2.cloudflarestorage.com')
            or endpoint.path not in ('','/') or endpoint.query or endpoint.fragment or endpoint.username):
        raise ValueError('Expected R2 HTTPS S3 endpoint without bucket path')
    return values


def presign(config,key,expires,now=None):
    now=now or datetime.datetime.now(datetime.timezone.utc)
    stamp=now.strftime('%Y%m%dT%H%M%SZ');day=stamp[:8];scope=day+'/auto/s3/aws4_request'
    base=config['R2_ENDPOINT_URL'].rstrip('/');host=urlsplit(base).netloc
    path='/'+quote(config['R2_BUCKET'],safe='')+'/'+quote(key,safe='/')
    values={'X-Amz-Algorithm':'AWS4-HMAC-SHA256','X-Amz-Credential':config['AWS_ACCESS_KEY_ID']+'/'+scope,
            'X-Amz-Date':stamp,'X-Amz-Expires':str(expires),'X-Amz-SignedHeaders':'host'}
    query='&'.join(quote(k,safe='')+'='+quote(v,safe='') for k,v in sorted(values.items()))
    canonical='GET\n'+path+'\n'+query+'\nhost:'+host+'\n\nhost\nUNSIGNED-PAYLOAD'
    message='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
    signing=('AWS4'+config['AWS_SECRET_ACCESS_KEY']).encode()
    for value in (day,'auto','s3','aws4_request'):signing=hmac.new(signing,value.encode(),hashlib.sha256).digest()
    signature=hmac.new(signing,message.encode(),hashlib.sha256).hexdigest()
    return base+path+'?'+query+'&X-Amz-Signature='+signature


def validate_name(name):
    if (not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.pdf',name)
            or '..' in name):raise ValueError('Expected a simple PDF filename')


def write_private(path,value):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:json.dump(value,stream,indent=2)


def sign_request(source_dir,names,config,output,expires=3600):
    if not 60<=expires<=604800:raise ValueError('Expiry must be 60..604800 seconds')
    source_dir=source_dir.resolve(strict=True)
    if not names:names=[p.name for p in source_dir.glob('*.pdf')]
    if not names or len(names)!=len(set(names)):raise ValueError('Expected nonempty unique PDF selection')
    files=[]
    for name in names:
        validate_name(name);path=source_dir/name
        if not path.resolve().is_relative_to(source_dir):raise ValueError('PDF escapes source directory')
        before=path.stat()
        with path.open('rb') as stream:
            if b'%PDF-' not in stream.read(1024):raise ValueError('Invalid source PDF header: '+name)
        sha=digest(path)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Source PDF changed')
        key=config['R2_PREFIX'].strip('/')+'/'+name
        files.append({'name':name,'key':key,'bytes':after.st_size,'sha256':sha,'url':presign(config,key,expires)})
    files.sort(key=lambda item:(item['bytes'],item['name']))
    value={'schema':'r2-paper-request/1','expires_at':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=expires)).isoformat(),
           'bucket':config['R2_BUCKET'],'files':files}
    write_private(output,value)
    print(f'Private request created: {output}; PDFs: {len(files)}; expires in {expires}s',flush=True)


def download_request(request,output):
    value=json.loads(request.read_text(encoding='utf-8'))
    if value.get('schema')!='r2-paper-request/1':raise ValueError('Unsupported request schema')
    files=value.get('files',[])
    if not files or len({item['name'] for item in files})!=len(files):raise ValueError('Invalid PDF selection')
    # Validate all entries before starting any download.
    for item in files:
        validate_name(item['name'])
        if type(item.get('bytes')) is not int or item['bytes']<1 or not re.fullmatch('[a-f0-9]{64}',item.get('sha256','')):
            raise ValueError('Invalid expected PDF size/hash')
        url=urlsplit(item['url'])
        if (url.scheme!='https' or not url.hostname or not url.hostname.endswith('.r2.cloudflarestorage.com')
                or url.username or not url.query):raise ValueError('Expected a signed R2 HTTPS URL')
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    receipt=[]
    for item in files:
        path=output/item['name']
        if not path.resolve().is_relative_to(output):raise ValueError('PDF target escapes input directory')
        try:
            fetch_file(item['url'],path,item)
        except Exception:
            # Never propagate exceptions containing a bearer URL.
            raise RuntimeError('PDF download/verification failed: '+item['name']+
                               '; preserve partial files; check access/expiry and regenerate request if needed') from None
        with path.open('rb') as stream:
            if b'%PDF-' not in stream.read(1024):raise ValueError('Invalid PDF header: '+item['name'])
        receipt.append({key:item[key] for key in ('name','key','bytes','sha256')})
        print('Ready for parser: '+str(path),flush=True)
    report=output/'r2-download-receipt.json'
    # Receipt contains provenance and hashes, never signed URLs or credentials.
    temporary=report.with_name(report.name+'.tmp')
    write_private(temporary,{'schema':'r2-paper-download/1','bucket':value['bucket'],'files':receipt})
    temporary.replace(report)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest='action',required=True)
    sign=actions.add_parser('sign',help='Ubuntu/local: create a private temporary download request')
    sign.add_argument('--env-file',type=Path,default=Path.home()/'.config/nasa-research/r2.env')
    sign.add_argument('--source-dir',type=Path,required=True)
    sign.add_argument('--paper',action='append',default=[])
    sign.add_argument('--output',type=Path,required=True)
    sign.add_argument('--expires',type=int,default=3600)
    download=actions.add_parser('download',help='Colab: download and verify PDFs, no model calls')
    download.add_argument('--request',type=Path,required=True)
    download.add_argument('--input-dir',type=Path,default=ROOT/'inputs/r2')
    args=parser.parse_args()
    if args.action=='sign':sign_request(args.source_dir,args.paper,read_settings(args.env_file),args.output,args.expires)
    else:download_request(args.request,args.input_dir)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('PAPER PREPARATION FAILED: '+str(exc),file=sys.stderr,flush=True)
        raise SystemExit(1)
