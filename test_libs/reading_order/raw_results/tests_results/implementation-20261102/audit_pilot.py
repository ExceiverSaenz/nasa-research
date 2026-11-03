"""Audit existing results only; never execute an engine or read a PDF."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'analytics'))
from compare_orders import compare_pair
base=root/'raw_results/code_results/pilot-12-20261102'
canonical=json.loads((base/'manifest.json').read_text())
assert 'requested_runs_complete' in canonical
def key(p):return (p['candidate_id'],p['scope']['paper_id'],p['scope']['page_idx'])
primary={key(p):p for p in canonical['predictions']}
assert len(primary)==78 and all(p['status']=='PASS' for p in primary.values())
rows=[]
sources=[]
for directory in [base,*[base.with_name(s['run_id']) for s in canonical['stability_runs']]]:
 raw=(directory/'manifest.json').read_bytes()
 report=json.loads(raw)
 sources.append(dict(run_id=report['run_id'],manifest_sha256=hashlib.sha256(raw).hexdigest(),predictions=len(report['predictions'])))
 assert report['input_profile_id']==canonical['input_profile_id']
 assert report['input_reference']==canonical['input_reference']
 assert len(report['predictions'])==78
 if directory==base:continue
 for prediction in report['predictions']:
  control=primary[key(prediction)]
  assert {k:v for k,v in prediction['scope'].items() if k!='permutation_seed'}=={k:v for k,v in control['scope'].items() if k!='permutation_seed'}
  metric=compare_pair(dict(prediction,scope=control['scope']),control)
  rows.append(dict(candidate_id=prediction['candidate_id'],page_idx=prediction['scope']['page_idx'],seed=prediction['scope']['permutation_seed'],
   status=prediction['status'],comparison_status=metric['status'],
   identical_order=prediction['ordered_ids']==control['ordered_ids'] if metric['status']=='comparable' else None,
   precedence_disagreement=metric['precedence_disagreement'],successor_jaccard=metric['successor_jaccard']))
source_root=root.parent/'bounding_boxes/raw_results/code/mineru-nativefix-20261101T034122Z/assembled/basic'
for document in canonical['input_reference']['documents']:
 for filename,field in [('normalized.json','normalized_sha256'),('middle.json','middle_sha256')]:
  assert hashlib.sha256((source_root/document['paper_id']/filename).read_bytes()).hexdigest()==document[field]
output=root/'raw_results/analytics_results/pilot-12-stability-audit'
output.mkdir(exist_ok=False)
summary=[]
for candidate in sorted({p['candidate_id'] for p in canonical['predictions']}):
 selected=[r for r in rows if r['candidate_id']==candidate]
 summary.append(dict(candidate_id=candidate,expected_conditions=len(selected),compared_conditions=sum(r['comparison_status']=='comparable' for r in selected),
  failed_conditions=sum(r['status']=='FAIL' for r in selected),identical_orders=sum(r['identical_order'] is True for r in selected),changed_orders=sum(r['identical_order'] is False for r in selected)))
(output/'stability.json').write_text(json.dumps(dict(audit_status='PASS',requested_runs_complete=canonical['requested_runs_complete'],sources=sources,original_hashes_unchanged=True,metric_kind='input_permutation_stability',
 scope_equivalence='Identical frozen references, page, eligible IDs and route; only permutation_seed differs',summary=summary,comparisons=rows,
 selection='selection_pending',semantic_accuracy='not_measured'),indent=2))
print(json.dumps(summary))
