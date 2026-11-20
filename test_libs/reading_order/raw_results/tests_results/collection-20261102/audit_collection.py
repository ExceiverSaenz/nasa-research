"""Verify recovered collection integrity against original references, without inference."""
import json,hashlib,sys
from dataclasses import asdict
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.collection import load_selection
from reading_order.ingest import Ingestor,LocalReferences
from reading_order.contracts import CANDIDATES,identity,require_permutation
from reading_order.context import permute
from reading_order.preflight import require_test_receipt,production_fingerprint
from reading_order.adapters.docling_contract import source_cids,CID_CONTRACT
base=Path(__file__).parent;folder=root/'raw_results/code_results/collection-20261102-delivery'
raw=(folder/'canonical/manifest.json').read_bytes();run=json.loads(raw)
selection=load_selection(root/'code/config/collection.json');reader=Ingestor(LocalReferences(selection.source_root))
frozen=run['input_reference'];assert identity({k:v for k,v in frozen.items() if k!='input_profile_id'})==frozen['input_profile_id']
assert [v['paper_id'] for v in frozen['documents']]==selection.paper_ids
expected={};empty=[];cid_maps={}
for row in frozen['documents']:
    doc=reader.read(row['paper_id'],expected=row,pdf_pages=[dict(width=p['pdf_width'],height=p['pdf_height'],rotation=p['rotation']) for p in row['pages']])
    assert doc.paper_sha256==row['paper_sha256']
    for page in doc.pages:
        ids=permute(doc.eligible(page['page_idx']),None)
        if not ids:empty.append([doc.paper_id,page['page_idx']])
        else:
            blocks={b.id:b for b in doc.blocks}
            cids=source_cids([asdict(blocks[i]) for i in ids],page['page_idx'])
            cid_maps[doc.paper_id,page['page_idx']]={str(cid):value for cid,value in zip(cids,ids)}
        for candidate in CANDIDATES:expected[candidate,doc.paper_id,page['page_idx']]=ids
seen=set();decoded=0;provenance_files={};provenance_links=0
def check_reuse(pred):
    global provenance_links
    visited=set()
    while 'reused_from' in pred:
        ref=pred['reused_from'];key=ref['path'],ref['sha256']
        marker=key+(ref['json_pointer'],)
        assert marker not in visited;visited.add(marker)
        if key not in provenance_files:
            content=Path(ref['path']).read_bytes();assert hashlib.sha256(content).hexdigest()==ref['sha256']
            provenance_files[key]=json.loads(content)
        original=provenance_files[key]
        for part in ref['json_pointer'].strip('/').split('/'):
            original=original[int(part)] if isinstance(original,list) else original[part]
        assert {k:v for k,v in original.items() if k!='reused_from'}=={k:v for k,v in pred.items() if k!='reused_from'}
        provenance_links+=1;pred=original
for pred in run['predictions']:
    scope=pred['scope'];key=pred['candidate_id'],scope['paper_id'],scope['page_idx']
    check_reuse(pred)
    assert key in expected and key not in seen;seen.add(key);ids=expected[key]
    assert scope['input_profile_id']==frozen['input_profile_id'] and scope['eligible_ids_hash']==identity(sorted(ids))
    assert scope['permutation_seed'] is None and pred['status']=='PASS'
    require_permutation(pred['ordered_ids'],ids)
    native=pred['native']
    if not ids:assert native['empty_scope'];reconstructed=[]
    elif key[0] in ('hantian','pp_doclayout_v2'):
        ranks=native['ranks'];require_permutation(ranks,list(range(len(ids))))
        reconstructed=[ids[i] for i in sorted(range(len(ids)),key=lambda i:ranks[i])]
    else:
        indices=native['indices'];require_permutation(indices,list(range(len(ids))))
        reconstructed=[ids[i] for i in indices]
    assert reconstructed==pred['ordered_ids'];decoded+=1
    if key[0]=='docling' and ids:
        assert pred['transformations']['cid_contract']==CID_CONTRACT
        assert native['cid_to_id']==cid_maps[key[1],key[2]]
        assert [native['cid_to_id'][str(cid)] for cid in native['cids']]==pred['ordered_ids']
assert set(expected)==seen and len(seen)==2382
context=json.loads((folder/'run-context.json').read_text())
assert context['code_files']==production_fingerprint(root)==run['environment']['code_files']
require_test_receipt(root,base/'offline-receipts-linux/test-receipt.json')
assert hashlib.sha256((base/'pdf-verified.json').read_bytes()).hexdigest()==context['pdf_metadata_reference']['sha256']
assert json.loads((folder/'session-status.json').read_text())['closed']
assert not list(folder.rglob('*.pdf')) and not list(folder.rglob('normalized.json')) and not list(folder.rglob('middle.json'))
result=dict(status='PASS',manifest_sha256=hashlib.sha256(raw).hexdigest(),papers=15,pages=397,predictions=len(seen),
    valid_native_to_id_decodings=decoded,empty_pages=empty,nonempty_pages=397-len(empty),
    nonempty_orders=decoded-len(empty)*len(CANDIDATES),empty_outputs=len(empty)*len(CANDIDATES),
    docling_source_cid_contract_verified=True,
    source_hashes_unchanged=True,pdf_metadata_identity_unchanged=True,code_matches_tested_deployment=True,
    source_copies=False,session_closed=True,semantic_accuracy_measured=False,
    reused_provenance_links_verified=provenance_links,reused_manifest_files_verified=len(provenance_files),
    per_paper=[dict(paper_id=p,per_candidate={c:sum(k[0]==c and k[1]==p for k in seen) for c in CANDIDATES}) for p in selection.paper_ids])
(base/'collection-integrity.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='per_paper'}))
