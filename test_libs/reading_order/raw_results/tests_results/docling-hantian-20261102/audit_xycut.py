"""Pinned-source fidelity audit, no original datasets or model execution."""
import hashlib,io,json,tarfile,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[3]
commit='81d93f825108d314f6588e5828e09b89bf45b67c'
url='https://codeload.github.com/home-still/xycut-plus-plus/tar.gz/'+commit
raw=urllib.request.urlopen(url,timeout=60).read();archive=tarfile.open(fileobj=io.BytesIO(raw))
prefix='xycut-plus-plus-'+commit+'/'
files={name:archive.extractfile(prefix+name).read() for name in ('src/core.rs','src/matching.rs','src/utils.rs','src/traits.rs','Cargo.toml')}
code={name:value.decode() for name,value in files.items()}
worker=root/'code/reading_order/adapters/xycut_worker.rs';worker_text=worker.read_text()
def ref(name,needle):
    text=code[name];assert needle in text
    return dict(member=name,line=text[:text.index(needle)].count('\n')+1)
assert 'SemanticLabel::CrossLayout' not in worker_text
assert 'masked_elements.push(element.clone())' in code['src/matching.rs']
assert 'let aspect_ratio = width / height;' in code['src/core.rs']
assert 'element.should_mask() || is_cross_layout || is_geometric_mask' in code['src/matching.rs']
findings=[
 dict(id='density',status='divergent',paper='Eq. 4: area ratio',implementation='sum of width/height ratios',
      reference=ref('src/core.rs','let aspect_ratio = width / height;'),
      synthetic_counterexample=dict(cross_box=[80,5],single_boxes=[[20,50]]*3,paper_ratio=400/3000,implementation_ratio=16/1.2)),
 dict(id='cross_layout_propagation',status='divergent',paper='Cross/single layout classification participates in refinement and matching',
      implementation='partition clones retain original semantic labels; wrapper emits only Regular/HorizontalTitle/Vision',
      reference=ref('src/matching.rs','masked_elements.push(element.clone())'),
      implication='For nonempty regular partitions under this adapter, cross-layout density numerator is zero; the adaptive >0.9 branch is unreachable.'),
 dict(id='geometric_presegmentation',status='redundant',paper='Eq. 3: central isolated visual element test',
      implementation='geometric mask requires should_mask and is ORed with should_mask, so it cannot change partition membership',
      reference=ref('src/matching.rs','if element.should_mask() || is_cross_layout || is_geometric_mask')),
 dict(id='matching_intersection',status='divergent',paper='Eq. 8 intersection/orientation/partial-overlap constraints',
      implementation='any full 2D overlap gives 0; otherwise 100; no orientation/partial IoU threshold',
      reference=ref('src/utils.rs','let phi1 = if boxes_overlap { 0.0 } else { 100.0 };')),
 dict(id='weight_scale',status='divergent',paper='Eq. 9 uses page dimensions',implementation='weights use masked element maximum dimension',
      reference=ref('src/utils.rs','let max_dim = mw.max(mh);')),
 dict(id='reinsertion',status='different_policy',paper='Algorithm 1 final ordering keys include index, label priority, Y1 and X1',
      implementation='row-quantized semantic groups inserted before a selected anchor',
      reference=ref('src/core.rs','result.insert(position, masked.id());'))]
paper_url='https://arxiv.org/html/2504.10258v1'
report=dict(status='AUDIT_COMPLETE',paper_fidelity='DIVERGES_FROM_PAPER',candidate_id='xycut_plus_plus',
            implementation='home-still/xycut-plus-plus third-party variant',commit=commit,paper=paper_url,
            archive_url=url,archive_sha256=hashlib.sha256(raw).hexdigest(),
            members=[dict(path=name,sha256=hashlib.sha256(value).hexdigest()) for name,value in files.items()],
            adapter_worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
            license_line=next(line for line in code['Cargo.toml'].splitlines() if line.strip().startswith('license')),
            findings=findings,new_inferences=0,source_data_copies=False,
            scope='Core ordering audit; using fixed MinerU detections is an intentional experimental condition, not itself a fidelity defect.',
            conclusion='Preserve existing results as this named variant. Do not attribute paper benchmark claims or official implementation status to it. No automatic replacement or tuning.')
out=root/'raw_results/analytics_results/xycut-fidelity-20261102';out.mkdir(exist_ok=False)
(out/'audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(dict(status=report['status'],paper_fidelity=report['paper_fidelity'],findings=len(findings))))
