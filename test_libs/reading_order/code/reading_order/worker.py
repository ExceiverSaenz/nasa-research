"""Long-lived per-candidate worker. Requests use stdin; inputs never go to disk."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
from .adapters.engines import EngineAdapter
from .resources import ResourceSampler


def pdf_metadata(request):
    from pypdf import PdfReader
    with urllib.request.urlopen(request['url'],timeout=90) as response:
        raw = response.read(128*1024*1024+1)
    if len(raw)>128*1024*1024 or hashlib.sha256(raw).hexdigest()!=request['sha256'] or b'%PDF-' not in raw[:1024]:
        raise ValueError('PDF identity failed')
    document = PdfReader(io.BytesIO(raw))
    return dict(status='PASS',sha256=request['sha256'],pages=[dict(width=float(p.mediabox.width),
                height=float(p.mediabox.height),rotation=int(p.rotation or 0)) for p in document.pages],
                persistence='memory_only')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment',type=Path,required=True)
    args = parser.parse_args(argv)
    adapters = {}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get('persist_input') is not False:
                raise ValueError('Input persistence was requested')
            with contextlib.redirect_stdout(io.StringIO()):
                if request['action'] == 'pdf_metadata':
                    result = pdf_metadata(request)
                else:
                    candidate = request['candidate_id']
                    key=(candidate,bool(request.get('capture_diagnostics',False)))
                    if key not in adapters:
                        adapters[key] = EngineAdapter(candidate,args.environment,request.get('language','en'),key[1])
                    with ResourceSampler() as sampler:
                        result = adapters[key].predict(request['blocks'],request['page'])
                    result.setdefault('costs',{}).update(sampler.result())
            del request
        except Exception as error:
            result = dict(status='FAIL',ordered_ids=None,reason=type(error).__name__,native={})
        print('ORDER_RESULT:'+json.dumps(result,allow_nan=False),flush=True)


if __name__=='__main__':
    main()
