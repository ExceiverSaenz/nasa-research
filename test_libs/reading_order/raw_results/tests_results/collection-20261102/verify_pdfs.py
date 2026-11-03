"""Verify all explicitly selected R2 originals in WSL memory; persist metadata only."""
import sys,json,hashlib,platform,urllib.request
from pathlib import Path
base=Path(__file__).parent
wheel=base/'pypdf-6.1.1-py3-none-any.whl'
index=json.load(urllib.request.urlopen('https://pypi.org/pypi/pypdf/6.1.1/json',timeout=30))
artifact=next(v for v in index['urls'] if v['filename']==wheel.name)
if not wheel.exists():
    dependency=urllib.request.urlopen(artifact['url'],timeout=30).read()
    assert hashlib.sha256(dependency).hexdigest()==artifact['digests']['sha256']
    wheel.write_bytes(dependency)
assert hashlib.sha256(wheel.read_bytes()).hexdigest()==artifact['digests']['sha256']
root=Path(__file__).resolve().parents[3];sys.path[:0]=[str(wheel),str(root/'code'),str(root.parents[1]/'new_code')]
from reading_order.collection import load_selection
from reading_order.ingest import Ingestor,LocalReferences
from reading_order.worker import pdf_metadata
from prepare_papers import read_settings,presign
import pypdf
selection=load_selection(root/'code/config/collection.json')
reader=Ingestor(LocalReferences(selection.source_root));settings=read_settings(Path.home()/'.config/nasa-research/r2.env')
report=dict(status='RUNNING',location='WSL',python=platform.python_version(),pypdf=pypdf.__version__,
    persistence='metadata_only',source_copies=False,dependency_sha256=artifact['digests']['sha256'],documents={})
path=base/'pdf-verified.json'
try:
    for paper in selection.paper_ids:
        doc=reader.read(paper)
        value=pdf_metadata(dict(url=presign(settings,settings['R2_PREFIX'].strip('/')+'/'+paper+'.pdf',600),sha256=doc.paper_sha256))
        reader.read(paper,pdf_pages=value['pages'],expected=doc.references)
        report['documents'][paper]=dict(value,source=doc.references)
        path.write_text(json.dumps(report,indent=2))
        print(json.dumps(dict(paper=paper,status='PASS',pages=len(value['pages']))),flush=True)
    report['status']='PASS';path.write_text(json.dumps(report,indent=2))
except Exception as error:
    report.update(status='FAIL',error_type=type(error).__name__);path.write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status='FAIL',error_type=type(error).__name__)),flush=True);raise SystemExit(1)
