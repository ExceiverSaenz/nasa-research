"""Private SigV4 GET requests. Permanent keys never leave the controller."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shlex
from urllib.parse import quote, urlsplit
import urllib.request
import xml.etree.ElementTree as ET

from .common import digest

PREFIX = 'tensile_papers/'


def valid_name(name):
    if (not isinstance(name, str) or not name.lower().endswith('.pdf') or name in ('.', '..')
            or any(c in name for c in '/\\:\n\r\0') or not name.strip()):
        raise ValueError('Expected a PDF filename, without directories')

class PdfSelector:
    """Select local identity references without network or credentials."""

    def select(self, directory, names, all_papers):
        directory = Path(directory).resolve()
        names = sorted(p.name for p in directory.iterdir() if p.suffix.lower() == '.pdf') if all_papers else names
        if not names or len(set(names)) != len(names): raise ValueError('Choose unique PDFs')
        rows = []
        for name in names:
            valid_name(name)
            p = directory / name
            if not p.is_file() or p.is_symlink() or p.resolve().parent != directory:
                raise ValueError('Missing or unsafe PDF: ' + name)
            before = p.stat()
            with p.open('rb') as stream:
                if b'%PDF-' not in stream.read(1024): raise ValueError('Invalid PDF: ' + name)
            sha = digest(p)
            if (p.stat().st_size, p.stat().st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                raise ValueError('Reference changed during selection')
            rows.append({'name': name, 'key': PREFIX + name, 'bytes': before.st_size, 'sha256': sha})
        if len({r['sha256'] for r in rows}) != len(rows): raise ValueError('Duplicate PDF content')
        return rows

class R2Credentials:
    """Read and validate the existing private credential file."""

    @staticmethod
    def load(path):
        path = Path(path).expanduser()
        if os.name == 'posix' and path.stat().st_mode & 0o077: raise ValueError('R2 settings must be private (600)')
        values = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('export '): line = line[7:]
            key, sep, value = line.partition('=')
            if not sep: raise ValueError('Invalid R2 setting')
            values[key.strip()] = ' '.join(shlex.split(value, comments=True))
        for key in ('R2_ENDPOINT_URL', 'R2_BUCKET', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'):
            if not values.get(key): raise ValueError('Missing setting: ' + key)
        u = urlsplit(values['R2_ENDPOINT_URL'])
        if (u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.r2.cloudflarestorage.com')
                or u.path not in ('', '/') or u.query or u.fragment or u.username or u.port):
            raise ValueError('Expected R2 HTTPS endpoint')
        return values

class R2Client:
    """Signed object access scoped to the baseline prefix."""

    def __init__(self, config=None, *, opener=None, clock=None):
        self.config = dict(config or {})
        self.opener = opener if opener is not None else urllib.request.urlopen
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def presign(self, key, expires=3600, parameters=None):
        config = self.config
        now = self.clock(); stamp = now.strftime('%Y%m%dT%H%M%SZ'); day = stamp[:8]
        scope = day + '/auto/s3/aws4_request'; base = config['R2_ENDPOINT_URL'].rstrip('/')
        path = '/' + quote(config['R2_BUCKET'], safe='') + '/' + quote(key, safe='/')
        values = {'X-Amz-Algorithm':'AWS4-HMAC-SHA256', 'X-Amz-Credential':config['AWS_ACCESS_KEY_ID']+'/'+scope,
                  'X-Amz-Date':stamp, 'X-Amz-Expires':str(expires), 'X-Amz-SignedHeaders':'host'}
        values.update(parameters or {})
        query = '&'.join(quote(k, safe='')+'='+quote(v, safe='') for k,v in sorted(values.items()))
        canonical = 'GET\n'+path+'\n'+query+'\nhost:'+urlsplit(base).netloc+'\n\nhost\nUNSIGNED-PAYLOAD'
        message = 'AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
        signing = ('AWS4'+config['AWS_SECRET_ACCESS_KEY']).encode()
        for value in (day, 'auto', 's3', 'aws4_request'): signing = hmac.new(signing, value.encode(), hashlib.sha256).digest()
        return base+path+'?'+query+'&X-Amz-Signature='+hmac.new(signing, message.encode(), hashlib.sha256).hexdigest()

    def write_request(self, path, papers):
        value = {'expires_at':(self.clock()+timedelta(hours=1)).isoformat(),
                 'files':[dict(p, url=self.presign(p['key'])) for p in papers]}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream: json.dump(value, stream)

    def download(self, request, destination):
        destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
        files = request.get('files', [])
        if not files or len({p['name'] for p in files}) != len(files): raise ValueError('Invalid request selection')
        for item in files:
            valid_name(item['name']); u = urlsplit(item['url'])
            if (item['key'] != PREFIX+item['name'] or not re.fullmatch('[a-f0-9]{64}', item['sha256'])
                    or type(item['bytes']) is not int or item['bytes'] < 1
                    or u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.r2.cloudflarestorage.com')
                    or u.username or not u.query or not u.path.endswith('/'+quote(item['key'], safe='/'))):
                raise ValueError('Invalid signed PDF request')
        for item in files:
            p = destination/item['name']; partial = p.with_name(p.name+'.partial')
            if p.exists() or partial.exists(): raise FileExistsError('Input already exists')
            try:
                with self.opener(item['url'], timeout=120) as source, partial.open('xb') as target:
                    total = 0
                    while block := source.read(1024*1024):
                        total += len(block)
                        if total > item['bytes']: raise ValueError('PDF size exceeded')
                        target.write(block)
                if partial.stat().st_size != item['bytes'] or digest(partial) != item['sha256']:
                    raise ValueError('PDF identity mismatch')
                with partial.open('rb') as stream:
                    if b'%PDF-' not in stream.read(1024): raise ValueError('Invalid PDF header')
                partial.rename(p)
            except Exception:
                raise RuntimeError('R2 download failed for '+item['name']+'; preserve partial input for review') from None
        return [{k:p[k] for k in ('name','key','bytes','sha256')} for p in files]

    def inventory(self, evidence=None):
        files=[]; token=None
        while True:
            query={'list-type':'2','prefix':PREFIX}
            if token: query['continuation-token']=token
            url=self.presign('',parameters=query)
            try:
                with self.opener(url,timeout=120) as response: raw=response.read()
                if evidence: (evidence/('inventory-page-'+str(len(files))+'.xml')).write_bytes(raw)
                doc=ET.fromstring(raw)
            except Exception: raise RuntimeError('R2 prefix inventory failed; inspect account access') from None
            ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
            for entry in doc.findall('s:Contents',ns):
                key=entry.findtext('s:Key',namespaces=ns)
                if not key.startswith(PREFIX): raise ValueError('R2 escaped authorised prefix')
                name=key[len(PREFIX):]
                if not name.lower().endswith('.pdf'): continue
                valid_name(name)
                files.append(dict(name=name,key=key,bytes=int(entry.findtext('s:Size',namespaces=ns)),
                                  etag=entry.findtext('s:ETag',namespaces=ns)))
            if doc.findtext('s:IsTruncated',namespaces=ns)!='true': break
            token=doc.findtext('s:NextContinuationToken',namespaces=ns)
            if not token: raise ValueError('Missing R2 pagination token')
        if not files or len({p['name'] for p in files})!=len(files): raise ValueError('Invalid remote PDF inventory')
        return sorted(files,key=lambda p:p['name'])

    def fetch_reference(self, item, directory):
        valid_name(item['name'])
        if item['key']!=PREFIX+item['name']: raise ValueError('Outside authorised prefix')
        directory.mkdir(parents=True,exist_ok=True); path=directory/item['name']
        if path.exists(): raise FileExistsError('Reference already exists; inspect its receipt')
        try:
            with self.opener(self.presign(item['key']),timeout=120) as source, path.open('xb') as target:
                count=0
                while block:=source.read(1024*1024):
                    count+=len(block)
                    if count>item['bytes']: raise ValueError('Remote object size changed')
                    target.write(block)
            if path.stat().st_size!=item['bytes']: raise ValueError('Incomplete R2 reference')
            with path.open('rb') as stream:
                if b'%PDF-' not in stream.read(1024): raise ValueError('Invalid R2 PDF')
        except Exception: raise RuntimeError('R2 reference acquisition failed: '+item['name']) from None
        return dict(item,sha256=digest(path))

