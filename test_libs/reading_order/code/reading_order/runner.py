from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from .contracts import CANDIDATES, Prediction, identity
from .context import permute


def all_runs_pass(reports):
    return bool(reports) and all(report.get('predictions') and
        all(p['status']=='PASS' for p in report['predictions']) for report in reports)


class Runner:
    """Orchestration depends on a prediction interface, not a concrete engine."""
    def __init__(self, backend, timeout_s=300, seed=1729, candidates=CANDIDATES):
        if not candidates or len(set(candidates))!=len(candidates) or not set(candidates).issubset(CANDIDATES):
            raise ValueError('Expected an explicit unique selection of known candidates')
        self.backend, self.timeout_s, self.seed = backend, timeout_s, seed
        self.candidates=tuple(candidates)

    def execute(self, documents, input_manifest, destination, reuse=None):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        report = dict(schema='reading-order-run/1', run_id=destination.name,
                      input_profile_id=input_manifest['input_profile_id'], input_reference=input_manifest,
                      created_utc=datetime.now(timezone.utc).isoformat(), predictions=[],candidate_ids=list(self.candidates),
                      documents=[dict(paper_id=d.paper_id, pages=d.pages, paper_sha256=d.paper_sha256,
                                      exclusions=[{'id':b.id,'reason':b.exclusion} for b in d.blocks if b.exclusion]) for d in documents],
                      native_cross_page_support=False, cross_page_links=[], selection='selection_pending')
        def save():
            temporary = destination/'manifest.tmp'
            temporary.write_text(json.dumps(report, indent=2, allow_nan=False))
            temporary.replace(destination/'manifest.json')
        save()
        transport_available=True
        for candidate in self.candidates:
            for doc in documents:
                for page in doc.pages:
                    blocks = {b.id: b for b in doc.blocks if b.page_idx == page['page_idx'] and b.exclusion is None}
                    ids = permute(list(blocks), self.seed)
                    scope = dict(paper_id=doc.paper_id, page_idx=page['page_idx'], input_profile_id=report['input_profile_id'],
                                 eligible_ids_hash=identity(sorted(ids)), permutation_seed=self.seed, route=None)
                    existing=(reuse or {}).get((candidate,doc.paper_id,page['page_idx']))
                    if existing is not None:
                        if existing['scope']!=scope or existing['status']!='PASS':
                            raise ValueError('Reused prediction scope or status differs')
                        from .contracts import require_permutation
                        require_permutation(existing['ordered_ids'],ids)
                        report['predictions'].append(existing)
                        save()
                        continue
                    start = time.monotonic()
                    pred = Prediction(candidate, scope, 'NOT_RUN', None)
                    if not transport_available:
                        pred.reason='transport_unavailable_not_submitted'
                        report['predictions'].append(asdict(pred));save();continue
                    try:
                        if page['rotation'] is None or not page['width'] or not page['height']:
                            raise ValueError('Page geometry not verified against PDF')
                        raw = self.backend.predict(candidate, [asdict(blocks[i]) for i in ids], page, self.timeout_s)
                        pred.native = raw.get('native', {})
                        pred.status = raw.get('status', 'PASS')
                        pred.ordered_ids = raw.get('ordered_ids')
                        pred.reason = raw.get('reason')
                        pred.transformations = raw.get('transformations', {})
                        pred.costs = raw.get('costs', {})
                        pred.validate(ids)
                    except Exception as error:
                        pred.status, pred.ordered_ids, pred.reason = 'FAIL', None, type(error).__name__
                        from .colab_backend import TransportError
                        if isinstance(error,TransportError):transport_available=False
                    pred.costs['controller_elapsed_s'] = time.monotonic()-start
                    report['predictions'].append(asdict(pred))
                    save()
        return report
