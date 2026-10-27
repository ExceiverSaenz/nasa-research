"""Resumable wheel transport with an official SHA256; no model execution."""
import argparse
import hashlib
from pathlib import Path
import time
from urllib.request import Request, urlopen


def download(url, expected, target, opener=urlopen, attempts=8):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    def digest(path):
        result = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(4*1024*1024), b''):
                result.update(chunk)
        return result.hexdigest()
    if target.exists():
        if digest(target) != expected:
            raise ValueError('Existing wheel hash mismatch')
        return
    partial = target.with_suffix(target.suffix+'.part')
    for attempt in range(attempts):
        offset = partial.stat().st_size if partial.exists() else 0
        print('DOWNLOAD', target.name, 'offset', offset, 'connection', attempt+1, flush=True)
        try:
            request = Request(url, headers={'Range':'bytes='+str(offset)+'-', 'Accept-Encoding':'identity'})
            with opener(request, timeout=600) as response:
                content_range = response.headers.get('Content-Range', '')
                if offset and (response.status != 206 or not content_range.startswith('bytes '+str(offset)+'-')):
                    raise ValueError('Server did not honor resume range')
                total = int(content_range.rsplit('/', 1)[1]) if content_range else offset+int(response.headers['Content-Length'])
                with partial.open('ab') as stream:
                    while True:
                        chunk = response.read(1024*1024)
                        if not chunk:
                            break
                        stream.write(chunk)
            if partial.stat().st_size != total:
                raise OSError('Incomplete HTTP body')
            if digest(partial) != expected:
                raise ValueError('Official wheel hash mismatch')
            partial.rename(target)
            print('VERIFIED', target.name, flush=True)
            return
        except ValueError:
            raise
        except Exception as error:
            print('Transport interrupted:', type(error).__name__, '; partial bytes retained', flush=True)
            if attempt+1 == attempts:
                raise RuntimeError('Download incomplete; partial retained') from None
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    download(args.url, args.sha256, args.output)
