"""Analyze saved targeted outputs only. No inference or PDF access."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path[:0]=[str(root/'code'),str(root/'analytics')]
from reading_order.context import permute
from reading_order.contracts import ranks_to_ids
from reading_order.stability import verify_unchanged
from hantian_decoder_audit import replay
folder=root/'raw_results/code_results/docling-hantian-validation-20261102'
summary=json.loads((folder/'summary.json').read_text());assert summary['status']=='PASS' and summary['session_closed']
reports={name:json.loads((folder/name/'manifest.json').read_text()) for name in ('canonical','permutation-1729','permutation-1730','hantian-repeat')}
def select(name,candidate):return {p['scope']['page_idx']:p for p in reports[name]['predictions'] if p['candidate_id']==candidate}
docling=select('canonical','docling');hantian=select('canonical','hantian');repeat=select('hantian-repeat','hantian')
doc_rows=[];hantian_rows=[];control_rows=[];replays=0;ties=0
for name,run in reports.items():
    for pred in run['predictions']:
        assert pred['status']=='PASS'
        page=pred['scope']['page_idx'];ids=permute(pred['ordered_ids'],pred['scope']['permutation_seed'])
        if pred['candidate_id']=='docling':
            assert pred['transformations']['cid_contract']=='mineru_top_level_block_ordinal/v1'
            mapping=pred['native']['cid_to_id']
            assert [mapping[str(cid)] for cid in pred['native']['cids']]==pred['ordered_ids']
            assert [ids[i] for i in pred['native']['indices']]==pred['ordered_ids']
            assert mapping==docling[page]['native']['cid_to_id']
            if name!='canonical':doc_rows.append(dict(page_number=page+1,condition=name,changed=pred['ordered_ids']!=docling[page]['ordered_ids']))
        else:
            native=pred['native'];decoded=replay(native['rank_logits'],native['rank_candidates'])
            assert decoded['ranks']==native['ranks']
            assert ranks_to_ids(decoded['ranks'],ids)==pred['ordered_ids']
            replays+=1;ties+=decoded['exact_score_ties']
            if name not in ('canonical','hantian-repeat'):
                base=hantian[page];base_ids=permute(base['ordered_ids'],None);raw=base['native']
                matrix=native['rank_logits'];baseline=raw['rank_logits'];index={i:k for k,i in enumerate(base_ids)}
                differences=[abs(matrix[row][col]-baseline[index[entity]][col]) for row,entity in enumerate(ids) for col in range(len(ids))]
                counter=replay([baseline[index[i]] for i in ids],[raw['rank_candidates'][index[i]] for i in ids])
                hantian_rows.append(dict(page_number=page+1,condition=name,
                    observed_order_changed=pred['ordered_ids']!=base['ordered_ids'],
                    max_aligned_logit_delta=max(differences),mean_aligned_logit_delta=sum(differences)/len(differences),
                    fixed_logits_decoder_order_changed=ranks_to_ids(counter['ranks'],ids)!=base['ordered_ids'],
                    fixed_logits_exact_score_ties=counter['exact_score_ties']))
for page,base in hantian.items():
    other=repeat[page]
    assert permute(base['ordered_ids'],None)==permute(other['ordered_ids'],None)
    delta=max(abs(a-b) for row1,row2 in zip(base['native']['rank_logits'],other['native']['rank_logits']) for a,b in zip(row1,row2))
    control_rows.append(dict(page_number=page+1,max_identical_input_logit_delta=delta,order_identical=base['ordered_ids']==other['ordered_ids']))
verify_unchanged(summary['preserved_references'])
old=json.loads(Path(summary['preserved_references'][0]['path']).read_text())
original={p['scope']['page_idx']:p for p in old['predictions'] if p['candidate_id']=='docling'}
result=dict(status='PASS',docling=dict(predictions=39,stable_cid_maps=39,changed_permutations=sum(r['changed'] for r in doc_rows),
    comparisons=26,canonical_pages_changed_vs_old_contract=sum(docling[p]['ordered_ids']!=original[p]['ordered_ids'] for p in docling),conditions=doc_rows),
    hantian=dict(predictions=replays,decoder_replays_matching=replays,decoder_exact_ties=ties,
        changed_permutations=sum(r['observed_order_changed'] for r in hantian_rows),
        fixed_logits_decoder_changes=sum(r['fixed_logits_decoder_order_changed'] for r in hantian_rows),
        max_identical_input_logit_delta=max(r['max_identical_input_logit_delta'] for r in control_rows),
        identical_control_orders=sum(r['order_identical'] for r in control_rows),
        permutation_conditions=hantian_rows,identical_input_controls=control_rows),
    input_references_unchanged=True,confirmation_executed=False,collection_executed=False,pdf_reads=0,
    selection='selection_pending',semantic_accuracy='not_measured',session_closed=summary['session_closed'],
    result_references=[dict(path=str(folder/name/'manifest.json'),sha256=hashlib.sha256((folder/name/'manifest.json').read_bytes()).hexdigest()) for name in reports])
out=root/'raw_results/analytics_results/docling-hantian-validation-20261102';out.mkdir(exist_ok=False)
(out/'analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(docling={k:v for k,v in result['docling'].items() if k!='conditions'},hantian={k:v for k,v in result['hantian'].items() if k not in ('permutation_conditions','identical_input_controls')})),flush=True)
