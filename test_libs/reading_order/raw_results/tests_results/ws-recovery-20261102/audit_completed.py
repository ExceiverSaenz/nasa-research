"""Audit the completed continuation; reads existing references/results only."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root/'code'),str(root/'analytics')]
from reading_order.stability import verify_unchanged,read_reference
from reading_order.contracts import require_permutation
from compare_orders import compare_pair
run=root/'raw_results/code_results/stability-12-recovery-20261102-comm'
summary=json.loads((run/'summary.json').read_text())
assert summary['status']=='PASS' and summary['session_closed'] is True
assert summary['pdf_reads']==0 and summary['confirmation_executed'] is False
primary,reference=read_reference(summary['primary_reference']['path'])
assert reference==summary['primary_reference']
def key(p):return (p['candidate_id'],p['scope']['paper_id'],p['scope']['page_idx'])
canonical={key(p):p for p in primary['predictions']}
assert len(canonical)==78 and all(p['status']=='PASS' for p in canonical.values())
references=[reference];rows=[];reused=0;new=0
for seed in [1729,1730]:
    current=json.loads((run/('permutation-'+str(seed))/'manifest.json').read_text())
    assert current['input_reference']==primary['input_reference']
    assert len(current['predictions'])==78
    assert {key(p) for p in current['predictions']}==set(canonical)
    old,old_ref=read_reference(current['continuation_of']['path'])
    assert old_ref==current['continuation_of'];references.append(old_ref)
    previous={key(p):p for p in old['predictions']}
    for p in current['predictions']:
        assert p['status']=='PASS' and p['scope']['permutation_seed']==seed
        control=canonical[key(p)]
        require_permutation(p['ordered_ids'],control['ordered_ids'])
        assert {k:v for k,v in p['scope'].items() if k!='permutation_seed'}=={k:v for k,v in control['scope'].items() if k!='permutation_seed'}
        if 'reused_from' in p:
            original=p['reused_from'];document,ref=read_reference(original['path'])
            assert original['sha256']==ref['sha256'];references.append(ref)
            prior=document['predictions'][int(original['json_pointer'].split('/')[-1])]
            assert {k:v for k,v in p.items() if k!='reused_from'}==prior
            assert prior['status']=='PASS';reused+=1
        else:
            assert previous[key(p)]['status']!='PASS';new+=1
        metric=compare_pair(dict(p,scope=control['scope']),control)
        assert metric['status']=='comparable'
        rows.append(dict(seed=seed,candidate_id=p['candidate_id'],page_idx=p['scope']['page_idx'],
                         identical_order=p['ordered_ids']==control['ordered_ids'],
                         precedence_disagreement=metric['precedence_disagreement'],successor_jaccard=metric['successor_jaccard']))
verify_unchanged(references)
assert reused==27 and new==129
engine='code/reading_order/adapters/engines.py'
assert summary['environment']['code_files'][engine]==primary['environment']['code_files'][engine]
source=Path(primary['input_reference']['source_root'])
for doc in primary['input_reference']['documents']:
    for filename,field in [('normalized.json','normalized_sha256'),('middle.json','middle_sha256')]:
        assert hashlib.sha256((source/doc['paper_id']/filename).read_bytes()).hexdigest()==doc[field]
output=root/'raw_results/analytics_results/stability-12-completed-20261102'
output.mkdir(exist_ok=False)
counts=[]
for candidate in sorted({row['candidate_id'] for row in rows}):
    values=[row for row in rows if row['candidate_id']==candidate]
    counts.append(dict(candidate_id=candidate,conditions=26,identical_orders=sum(row['identical_order'] for row in values),
                       changed_orders=sum(not row['identical_order'] for row in values)))
report=dict(audit_status='PASS',coverage=dict(expected=156,valid=156,new_inferences=new,reused=reused,failed=0),
            primary_unchanged=True,original_hashes_unchanged=True,ordering_adapter_code_unchanged=True,
            primary_reference=reference,continuation=str(run/'summary.json'),references=references,
            metric_kind='input_permutation_stability',scope_equivalence='Same frozen inputs, page, eligible IDs and route; only seed differs',
            per_candidate=counts,comparisons=rows,semantic_accuracy='not_measured',selection='selection_pending')
(output/'stability.json').write_text(json.dumps(report,indent=2))
print(json.dumps(dict(coverage=report['coverage'],per_candidate=counts)),flush=True)
