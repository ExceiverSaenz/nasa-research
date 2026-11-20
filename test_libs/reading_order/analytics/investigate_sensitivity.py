"""Forensics over saved predictions. No predictor, GPU, PDF or source writes."""
import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from reading_order.context import permute
from reading_order.contracts import ranks_to_ids,require_permutation
from reading_order.ingest import Ingestor,LocalReferences,portable_reference,resolve_reference


def digest(path):return hashlib.sha256(resolve_reference(path).read_bytes()).hexdigest()


def decode_native(candidate,native,ids):
    if candidate in ('hantian','pp_doclayout_v2'):return ranks_to_ids(native['ranks'],ids)
    require_permutation(native['indices'],list(range(len(ids))))
    return [ids[i] for i in native['indices']]


def sigmoid(value):return 1/(1+math.exp(-max(-700,min(700,value))))


def pp_votes(matrix):
    n=len(matrix)
    if any(len(row)!=n for row in matrix):raise ValueError('Expected square matrix')
    return [math.fsum(sigmoid(matrix[i][j]) if i<j else 1-sigmoid(matrix[j][i])
                      for i in range(n) if i!=j) for j in range(n)]


def pp_order(matrix,ids):
    votes=pp_votes(matrix)
    return sorted(ids,key=lambda i:(votes[ids.index(i)],ids.index(i)))


def pair_logit(matrix,ids,a,b):
    i,j=ids.index(a),ids.index(b)
    return matrix[i][j] if i<j else -matrix[j][i]


def reindex_pairs(matrix,ids,new_ids):
    return [[pair_logit(matrix,ids,a,b) if i<j else -10000 for j,b in enumerate(new_ids)] for i,a in enumerate(new_ids)]


def docling_prior_edges(ids,boxes,labels=None,width=100,height=100):
    labels=labels or {}
    def bucket(i):return 'header' if labels.get(i)=='header' else 'footer' if labels.get(i) in ('footer','page_number') else 'body'
    def graphic(i):return labels.get(i) in ('image','chart','table')
    horizontal=[];near_vertical=[]
    for left,right in zip(ids,ids[1:]):
        if bucket(left)!=bucket(right):continue
        a,b=boxes[left],boxes[right]
        overlap=min(a[3],b[3])-max(a[1],b[1]);union=max(a[3],b[3])-min(a[1],b[1])
        between=any(i not in (left,right) and bucket(i)==bucket(left) and a[2]<box[2] and box[0]<b[0]
                    and max(a[1],b[1])<box[3] and box[1]<min(a[3],b[3]) for i,box in boxes.items())
        if a[2]+.001<b[0] and overlap>0 and overlap/union>.8 and not between:horizontal.append([left,right])
        if (not graphic(left) and not graphic(right) and abs(a[0]-b[0])<width*.01
                and a[3]-height*.0025<=b[1]<a[3] and a[1]<b[1] and a[3]<b[3]):near_vertical.append([left,right])
    return dict(horizontal=horizontal,near_vertical=near_vertical)


def inverted_pairs(a,b):
    positions={v:i for i,v in enumerate(b)}
    return [(left,right) for i,left in enumerate(a) for right in a[i+1:] if positions[left]>positions[right]]


def source_audit(root):
    """Official source bytes only in memory; pin wheels to the validated lock."""
    lock=(root/'raw_results/tests_results/20261102T052716Z-config-7e26b3/requirements.lock').read_text()
    prepared=json.loads((root/'raw_results/tests_results/20261102T052716Z-config-7e26b3/prepared-identity.json').read_text())
    snapshots=[];texts={}
    targets=[('docling-slim','2.145.0',{'docling':'docling/models/postprocessing/reading_order_rb.py'}),
             ('docling-core','2.105.0',{'bounding_box':'docling_core/types/doc/base.py'}),
             ('transformers','5.22.1',{'pp_model':'transformers/models/pp_doclayout_v2/modeling_pp_doclayout_v2.py',
              'pp_decoder':'transformers/models/pp_doclayout_v2/image_processing_pp_doclayout_v2.py',
              'hantian_model':'transformers/models/layoutlmv3/modeling_layoutlmv3.py'})]
    for project,version,members in targets:
        metadata=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{project}/{version}/json',timeout=60))
        wheel=next(v for v in metadata['urls'] if v['filename'].endswith('.whl'))
        raw=urllib.request.urlopen(wheel['url'],timeout=90).read();sha=hashlib.sha256(raw).hexdigest()
        if sha!=wheel['digests']['sha256'] or sha not in lock:raise ValueError('Source artifact differs from validated lock')
        archive=zipfile.ZipFile(io.BytesIO(raw))
        for key,member in members.items():
            code=archive.read(member);texts[key]=code.decode()
            snapshots.append(dict(key=key,version=version,wheel_url=wheel['url'],wheel_sha256=sha,
                                  member=member,module_sha256=hashlib.sha256(code).hexdigest(),lock_hash_verified=True))
    helper_url='https://raw.githubusercontent.com/FreeOCR-AI/layoutreader/3b46ee82cd02dcea94ee4064152e5f4de91e205e/v3/helpers.py'
    helper=urllib.request.urlopen(helper_url,timeout=60).read()
    sha=hashlib.sha256(helper).hexdigest()
    if sha!=prepared['artifacts']['hantian_helpers.py']:raise ValueError('Hantian helper differs from prepared environment')
    texts['hantian_helper']=helper.decode();snapshots.append(dict(key='hantian_helper',url=helper_url,module_sha256=sha,prepared_hash_verified=True))
    interesting={'parse_logits','boxes2inputs','follows_maintext_order','_init_l2r_map','_init_ud_maps',
                 '_get_order_seqs','PPDocLayoutV2GlobalPointer','PPDocLayoutV2TextEmbeddings','LayoutLMv3TextEmbeddings'}
    for snapshot in snapshots:
        snapshot['relevant_symbols']=[dict(name=n.name,line=n.lineno,end_line=n.end_lineno) for n in ast.walk(ast.parse(texts[snapshot['key']]))
            if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in interesting]
    return snapshots


def analyze(root,output,verify_sources=False,update=False):
    root=Path(root);paths=[root/'raw_results/code_results/pilot-12-20261102/manifest.json',
        *[root/'raw_results/code_results/stability-12-recovery-20261102-comm'/('permutation-'+str(seed))/'manifest.json' for seed in (1729,1730)]]
    references=[dict(path=portable_reference(p.resolve()),sha256=digest(p)) for p in paths]
    runs=[json.loads(p.read_text()) for p in paths]
    frozen=runs[0]['input_reference']
    source=root.parent/'bounding_boxes/raw_results/code/mineru-nativefix-20261101T034122Z/assembled/basic'
    document=Ingestor(LocalReferences(source)).read('12',expected=frozen['documents'][0])
    blocks={b.id:b for b in document.blocks if b.exclusion is None}
    pages={p['page_idx']:p for p in document.pages}
    base={(p['candidate_id'],p['scope']['page_idx']):p for p in runs[0]['predictions']}
    counts={c:dict(native_checks=0,changed_conditions=0,comparisons=0) for c in ('hantian','docling','pp_doclayout_v2')}
    rows=[];pp_native_replays=0;pp_fixed_preferences=0;docling_input_map_checks=0
    for run in runs:
        if run['input_reference']!=frozen:raise ValueError('Frozen reference differs')
        for prediction in run['predictions']:
            c=prediction['candidate_id']
            if c not in counts:continue
            if prediction['status']!='PASS':raise ValueError('Requires complete existing outputs')
            page=prediction['scope']['page_idx'];seed=prediction['scope']['permutation_seed']
            ids=permute([i for i,b in blocks.items() if b.page_idx==page],seed)
            if decode_native(c,prediction['native'],ids)!=prediction['ordered_ids']:raise ValueError('Native-to-ID adapter mismatch')
            counts[c]['native_checks']+=1
            if c=='docling':
                mapping=prediction['native']['temporary_ref_to_id']
                if [mapping['#/texts/'+str(i)] for i in range(len(ids))]!=ids:raise ValueError('Reconstructed input differs from saved mapping')
                docling_input_map_checks+=1
            if c=='pp_doclayout_v2':
                if pp_order(prediction['native']['pair_logits'],ids)!=prediction['ordered_ids']:raise ValueError('Float64 decoder replay differs')
                pp_native_replays+=1
            if seed is None:continue
            canonical=base[c,page];original_ids=permute(canonical['ordered_ids'],None)
            pairs=inverted_pairs(canonical['ordered_ids'],prediction['ordered_ids'])
            row=dict(candidate_id=c,page_idx=page,page_number=page+1,seed=seed,entities=len(ids),
                     changed=bool(pairs),inverted_pairs=len(pairs),evaluated_pairs=len(ids)*(len(ids)-1)//2,
                     input_index_changed=sum(ids.index(i)!=original_ids.index(i) for i in ids))
            counts[c]['comparisons']+=1;counts[c]['changed_conditions']+=bool(pairs)
            if c=='docling':
                dim=pages[page];labels={i:blocks[i].raw_label for i in ids}
                boxes={i:[blocks[i].bbox[0]*dim['width'],blocks[i].bbox[1]*dim['height'],blocks[i].bbox[2]*dim['width'],blocks[i].bbox[3]*dim['height']] for i in ids}
                prior0=docling_prior_edges(original_ids,boxes,labels,dim['width'],dim['height'])
                prior1=docling_prior_edges(ids,boxes,labels,dim['width'],dim['height'])
                row.update(inverted_id_pairs=[dict(ids=list(pair),labels=[labels[i] for i in pair]) for pair in pairs],
                           canonical_cid_prior=prior0,permuted_cid_prior=prior1,
                           cid_prior_changed=prior0!=prior1)
            if c=='pp_doclayout_v2':
                g0=canonical['native']['pair_logits'];g1=prediction['native']['pair_logits']
                labels0=dict(zip(original_ids,canonical['transformations']['mapped_class_ids']))
                labels1=dict(zip(ids,prediction['transformations']['mapped_class_ids']))
                if labels0!=labels1:raise ValueError('Category mapping changed by ID')
                deltas=[abs(sigmoid(pair_logit(g0,original_ids,a,b))-sigmoid(pair_logit(g1,ids,a,b)))
                        for index,a in enumerate(original_ids) for b in original_ids[index+1:]]
                v0=dict(zip(original_ids,pp_votes(g0)));v1=dict(zip(ids,pp_votes(g1)))
                fixed=pp_order(reindex_pairs(g0,original_ids,ids),ids)
                if fixed!=canonical['ordered_ids']:raise ValueError('Fixed pair preferences are not invariant')
                pp_fixed_preferences+=1
                row.update(max_pair_probability_delta=max(deltas),mean_pair_probability_delta=sum(deltas)/len(deltas),
                           fixed_pair_preferences_preserve_order=True,category_mapping_unchanged=True,
                           changed_pair_details=[dict(ids=[a,b],labels=[blocks[a].raw_label,blocks[b].raw_label],
                           canonical_pair_probability=sigmoid(pair_logit(g0,original_ids,a,b)),
                           permuted_pair_probability=sigmoid(pair_logit(g1,ids,a,b)),
                           canonical_votes=[v0[a],v0[b]],permuted_votes=[v1[a],v1[b]],
                           canonical_input_positions=[original_ids.index(a),original_ids.index(b)],
                           permuted_input_positions=[ids.index(a),ids.index(b)]) for a,b in pairs])
                if pairs:
                    moved={i for pair in pairs for i in pair}
                    row['largest_vote_changes']=[dict(id=i,label=blocks[i].raw_label,
                        canonical_vote=v0[i],permuted_vote=v1[i],
                        largest_incoming_score_changes=sorted([
                            dict(other_id=j,other_label=blocks[j].raw_label,
                                 canonical_score=sigmoid(pair_logit(g0,original_ids,j,i)),
                                 permuted_score=sigmoid(pair_logit(g1,ids,j,i)),
                                 delta=sigmoid(pair_logit(g1,ids,j,i))-sigmoid(pair_logit(g0,original_ids,j,i)))
                            for j in ids if j!=i],key=lambda value:abs(value['delta']),reverse=True)[:3]) for i in sorted(moved)]
            rows.append(row)
    snapshots=source_audit(root) if verify_sources else []
    for reference in references:
        if digest(reference['path'])!=reference['sha256']:raise ValueError('Preserved output changed')
    Ingestor(LocalReferences(source)).read('12',expected=frozen['documents'][0])
    report=dict(schema='reading-order-sensitivity-attribution/1',status='PASS',new_inferences=0,pdf_reads=0,
        inputs_copied=False,production_adapters_modified=False,references=references,sources=snapshots,counts=counts,
        docling_saved_input_maps_verified=docling_input_map_checks,
        docling_prior_changed_conditions=sum(row.get('cid_prior_changed',False) for row in rows if row['candidate_id']=='docling'),
        pp_native_decoder_replays=pp_native_replays,
        pp_fixed_pair_preference_replays=pp_fixed_preferences,conditions=rows,
        limitations=['Hantian token logits were not saved: cannot split neural effects from upstream greedy-decoder tie handling.',
          'Docling records final indices only: CID graph predicates can be inspected but original traversal/R-tree trace cannot be reconstructed completely without rerunning the predictor.',
          'PP decoder replay uses CPU float64, not original CUDA float32 reduction order; all saved native ranks nevertheless match.',
          'No repeated identical-input inference exists to isolate residual GPU numerical nondeterminism.'])
    output=Path(output)
    if update:
        existing=json.loads((output/'attribution.json').read_text())
        if existing['schema']!=report['schema'] or existing['references']!=references:
            raise ValueError('Update is restricted to this derived report and the same preserved inputs')
    else:output.mkdir(parents=True,exist_ok=False)
    (output/'attribution.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(dict(counts=counts,pp_native_decoder_replays=pp_native_replays,
                        pp_fixed_pair_preference_replays=pp_fixed_preferences)))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify-sources',action='store_true')
    parser.add_argument('--update',action='store_true',help='Update this derived report only, with unchanged references')
    args=parser.parse_args()
    analyze(ROOT,args.output,args.verify_sources,args.update)
