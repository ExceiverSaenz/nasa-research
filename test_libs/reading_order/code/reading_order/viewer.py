import hashlib
import json
from pathlib import Path
from .ingest import Ingestor,LocalReferences


class ViewerData:
    def __init__(self, run_path):
        self.run_path = Path(run_path)
        self.run = json.loads((self.run_path/'manifest.json').read_text())

    def page(self, paper, index):
        ref = self.run['input_reference']
        docs = Ingestor(LocalReferences(ref['source_root'])).resolve(ref)
        doc = next((d for d in docs if d.paper_id==paper),None)
        if doc is None or index not in range(len(doc.pages)):
            raise ValueError('Page is not registered in this run')
        from dataclasses import asdict
        return dict(page=doc.pages[index],blocks=[asdict(b) for b in doc.blocks if b.page_idx==index],
                    background=f'/asset/{paper}/{index}')

    def asset(self, paper, index):
        doc = next((d for d in self.run['documents'] if d['paper_id']==paper),None)
        if doc is None or index not in range(len(doc['pages'])):
            raise ValueError('Unregistered background')
        root = LocalReferences(self.run['input_reference']['source_root']).root.parents[1]/'viewer_source/pages'
        path = (root/doc['paper_sha256']/(str(index)+'.png')).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('No existing background available')
        return path


def build_viewer(run_path):
    run_path = Path(run_path)
    run = json.loads((run_path/'manifest.json').read_text())
    index = dict(schema='reading-order-viewer/1',run_id=run['run_id'],input_profile_id=run['input_profile_id'],
                 documents=run['documents'],native_cross_page_support=False,assets='existing_references_only')
    target = run_path/'viewer-index.json'
    if target.exists():
        if json.loads(target.read_text())!=index:
            raise ValueError('Viewer index already exists with different identity')
    else:
        target.write_text(json.dumps(index,indent=2))
    from .offline_viewer import OfflineViewerExporter
    OfflineViewerExporter(run_path).export()
    return index
