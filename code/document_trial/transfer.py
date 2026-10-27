"""Offline fragmentation and byte-exact remote assembly; no models or retries."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import uuid

CHUNK_BYTES=1024*1024


def assemble(manifest):
    import hashlib
    import os
    from pathlib import Path
    target=Path(manifest['target'])
    if target.exists():raise FileExistsError('Destination exists; inspect manually, no overwrite')
    staging=Path(str(target)+'.assembling-'+manifest['attempt'])
    digest=hashlib.sha256();total=0
    with staging.open('xb') as output:
        for part in manifest['parts']:
            path=Path(part['remote']);data=path.read_bytes()
            if len(data)!=part['bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:
                raise ValueError('Transfer fragment differs: '+path.name)
            output.write(data);digest.update(data);total+=len(data)
    if total!=manifest['bytes'] or digest.hexdigest()!=manifest['sha256']:
        raise ValueError('Reconstructed archive differs; parsing forbidden')
    # Publish without replacing any existing destination. Retain parts as evidence.
    os.link(staging,target)
    staging.unlink()
    print('TRANSFER_VERIFIED '+manifest['sha256'],flush=True)


def prepare(source,destination,attempt,target='/content/nasa-sic12-document-v1-upload.zip',chunk_bytes=CHUNK_BYTES):
    if uuid.UUID(attempt).hex!=attempt:raise ValueError('Invalid attempt')
    if type(chunk_bytes) is not int or chunk_bytes<1 or chunk_bytes>CHUNK_BYTES:raise ValueError('Invalid fragment size')
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    parts=[];digest=hashlib.sha256();total=0
    with source.open('rb') as f:
        for index,data in enumerate(iter(lambda:f.read(chunk_bytes),b'')):
            name='part-%04d'%index;local=destination/name;local.write_bytes(data)
            parts.append(dict(local=str(local),remote='/content/sic-transfer-'+attempt+'-'+name,
                bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            digest.update(data);total+=len(data)
    manifest=dict(attempt=attempt,target=target,parts=parts,bytes=total,sha256=digest.hexdigest())
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (destination/'assembly.py').write_text(inspect.getsource(assemble)+'\nassemble('+repr(manifest)+')\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');p.add_argument('attempt_file')
    a=p.parse_args();m=prepare(a.source,a.destination,json.loads(Path(a.attempt_file).read_bytes())['attempt_id'])
    print('Transferencia fragmentada:',len(m['parts']),'bloques; SHA256',m['sha256'])
