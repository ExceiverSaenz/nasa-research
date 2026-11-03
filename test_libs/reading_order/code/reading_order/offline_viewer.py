"""Export a direct-file visualization, referencing original page backgrounds."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote
from .ingest import Ingestor,LocalReferences
from .reviews import ReviewStore


def script_json(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False)
            .replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029'))


class OfflineViewerExporter:
    """Read verified references once and write only a derived visual projection."""
    def __init__(self,run_path):
        self.run_path=Path(run_path).resolve()
        raw=(self.run_path/'manifest.json').read_bytes()
        self.run=json.loads(raw)
        self.run_sha256=hashlib.sha256(raw).hexdigest()

    def payload(self,target):
        reference=self.run['input_reference']
        references=LocalReferences(reference['source_root'])
        documents=Ingestor(references).resolve(reference)
        images=references.root.parents[1]/'viewer_source/pages'
        pages={}
        fields=('id','bbox','raw_label','parent_id','route','group_ids','exclusion','source_ref')
        for doc in documents:
            for page in doc.pages:
                index=page['page_idx'];image=images/doc.paper_sha256/(str(index)+'.png')
                background=quote(Path(os.path.relpath(image,target.parent)).as_posix(),safe='/') if image.is_file() else None
                blocks=[asdict(b) for b in doc.blocks if b.page_idx==index and b.exclusion is None]
                source=references.root/doc.paper_id/'middle.json'
                source_url=quote(Path(os.path.relpath(source,target.parent)).as_posix(),safe='/')
                projected=[dict({k:b[k] for k in fields},source_url=source_url+'#'+quote(b['source_ref'].partition('#')[2],safe='/~')) for b in blocks]
                pages[f'{doc.paper_id}:{index}']=dict(page=page,
                    blocks=projected,excluded_ids=[b.id for b in doc.blocks if b.page_idx==index and b.exclusion],background=background)
        run={key:self.run[key] for key in ('run_id','input_profile_id','candidate_display_names','native_cross_page_support') if key in self.run}
        run['documents']=[{key:doc[key] for key in ('paper_id','paper_sha256','pages')} for doc in self.run['documents']]
        run['predictions']=[dict(p,native={key:value for key,value in p.get('native',{}).items() if key!='pair_logits'}) for p in self.run['predictions']]
        return dict(schema='reading-order-offline-viewer/1',
            state=dict(run=run,run_sha256=self.run_sha256,reviews=ReviewStore(self.run_path).load()),
            manifest_href=quote(Path(os.path.relpath(self.run_path/'manifest.json',target.parent)).as_posix(),safe='/'),
            pages=pages,source_policy='visual_projection_only; images_and_source_text_by_reference')

    def export(self,target=None):
        target=Path(target) if target is not None else self.run_path/'viewer.html'
        if target.is_symlink():raise ValueError('Viewer destination may not be a symlink')
        payload=self.payload(target)
        assets=Path(__file__).parent/'viewer'
        html=(assets/'index.html').read_text(encoding='utf-8')
        policy="default-src 'none'; img-src file:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
        html=html.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+policy+'">',1)
        html=html.replace('<link rel="stylesheet" href="/style.css">',
            '<style>'+(assets/'style.css').read_text(encoding='utf-8')+'</style>')
        scripts='<script id="reading-order-data" type="application/json">'+script_json(payload)+'</script>'
        scripts+='<script>'+(assets/'offline.js').read_text(encoding='utf-8')+'</script>'
        scripts+='<script>window.READING_ORDER_STATIC=JSON.parse(document.getElementById("reading-order-data").textContent);</script>'
        scripts+='<script>'+(assets/'app.js').read_text(encoding='utf-8')+'</script>'
        html=html.replace('<script src="/app.js"></script>',scripts)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,
                    prefix='viewer-',suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);stream.write(html)
            temporary.replace(target)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        return target
