"""Offline all-pairs checks with hand-calculated expectations; no engines."""
import copy
import json

import pytest

from reading_order.contracts import CANDIDATES, identity


def collection():
    inventory = {}
    predictions = []
    for paper, page, ids in [('A', 0, ['a', 'b', 'c']), ('A', 1, ['f', 'g', 'h']),
                             ('B', 0, ['d', 'e']), ('B', 1, [])]:
        inventory[(paper, page)] = dict(ids=ids, raw_labels=['text'] * len(ids),
                                       layout='unknown', route='unknown')
        scope = dict(paper_id=paper, page_idx=page, input_profile_id='profile',
                     eligible_ids_hash=identity(sorted(ids)), permutation_seed=None, route=None)
        for candidate in CANDIDATES:
            order = ids[::-1] if candidate == 'hantian' and (paper, page) == ('A', 0) else ids[:]
            predictions.append(dict(candidate_id=candidate, scope=scope.copy(), status='PASS',
                                    ordered_ids=order, transformations={'cid_contract': 'fixed/v1'}))
    return dict(candidate_ids=list(CANDIDATES), input_profile_id='profile', predictions=predictions), inventory


def pair(report, a='hantian', b='docling'):
    return next(row for row in report['pair_summaries'] if {row['candidate_a'], row['candidate_b']} == {a, b})


def test_all_fifteen_pairs_and_macro_micro_denominators():
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    report = analyze_predictions(run, inventory)
    assert len(report['comparisons']) == 60  # 15 pairs x 4 page scopes
    assert len(report['pair_summaries']) == 15
    result = pair(report)
    assert result['macro']['precedence_disagreement'] == .25
    assert result['micro']['precedence_disagreement'] == pytest.approx(3 / 7)
    assert result['macro']['successor_jaccard'] == .75
    assert result['micro']['successor_jaccard'] == pytest.approx(3 / 7)
    assert result['macro']['exact_match'] == .75
    assert result['micro']['exact_match'] == pytest.approx(2 / 3)
    assert result['coverage'] == dict(expected=4, comparable=4, evaluated=3, degenerate=1,
                                     not_comparable=0, documents_expected=2, documents_evaluated=2)
    assert result['distributions']['precedence_disagreement']['document']['median'] == .25
    assert result['common_scopes']['macro'] == result['macro']
    assert report['human_review'] == 'pending'
    assert report['selection'] == 'selection_pending'
    matrix = report['matrices']['precedence_disagreement']
    assert len(matrix) == 6 and all(len(row) == 6 for row in matrix)
    assert matrix[0][1] == matrix[1][0] == .25
    assert all(matrix[i][i] == 0 for i in range(6))


@pytest.mark.parametrize('damage', ['missing_id', 'same_wrong_ids', 'duplicate_id', 'wrong_scope_hash',
                                    'failed', 'missing_prediction'])
def test_invalid_or_missing_outputs_remain_in_coverage(damage):
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    left = run['predictions'][0]
    if damage == 'missing_id':
        left['ordered_ids'].pop()
    elif damage == 'same_wrong_ids':
        for p in run['predictions'][:6]:
            p['ordered_ids'] = ['x', 'y', 'z']
    elif damage == 'duplicate_id':
        left['ordered_ids'] = ['a', 'a', 'c']
    elif damage == 'wrong_scope_hash':
        left['scope']['eligible_ids_hash'] = 'wrong'
    elif damage == 'failed':
        left.update(status='FAIL', ordered_ids=None)
    else:
        run['predictions'].pop(0)
    report = analyze_predictions(run, inventory)
    result = pair(report)
    assert result['coverage']['not_comparable'] == 1
    assert result['coverage']['evaluated'] == 2
    # One bad candidate also removes the scope from the common-six comparison.
    assert report['common_scope_coverage']['evaluated'] == 2
    assert pair(report, 'xycut', 'doctr')['common_scopes']['coverage']['evaluated'] == 2
    assert len(report['comparisons']) == 60


def test_duplicate_or_foreign_predictions_are_rejected_instead_of_overwritten():
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    run['predictions'].append(copy.deepcopy(run['predictions'][0]))
    with pytest.raises(ValueError, match='Duplicate'):
        analyze_predictions(run, inventory)
    run['predictions'][-1]['scope']['paper_id'] = 'foreign'
    with pytest.raises(ValueError, match='Unknown'):
        analyze_predictions(run, inventory)


def test_saved_run_identity_and_sources_are_verified_without_engine(tmp_path):
    from reading_order.ingest import Ingestor, LocalReferences
    from pairwise_analysis import load_saved_inventory
    import hashlib
    root = tmp_path / 'source'
    folder = root / '12'
    folder.mkdir(parents=True)
    middle = dict(metadata={'document': {'page_count': 1}}, pages=[{'blocks': [
        {'type': 'text', 'content': []}, {'type': 'text', 'content': []}]}],
        extensions={'docvortex_layout': {'pages': [dict(page_idx=0, width_pt=600, height_pt=800)]}})
    raw = json.dumps(middle).encode()
    (folder / 'middle.json').write_bytes(raw)
    rows = [dict(id=x, paper_sha256='a' * 64, page_idx=0, raw_label='text',
                 bbox_normalized=[.1, .1, .9, .2], original_sha256=hashlib.sha256(raw).hexdigest(),
                 original_ref=f'/content/12/middle.json#/pages/0/blocks/{i}') for i, x in enumerate(['a', 'b'])]
    (folder / 'normalized.json').write_text(json.dumps(rows))
    frozen = Ingestor(LocalReferences(root)).freeze(['12'], tmp_path / 'input')
    run = dict(input_reference=frozen, input_profile_id=frozen['input_profile_id'])
    inventory, references = load_saved_inventory(run, root)
    assert inventory[('12', 0)]['ids'] == ['a', 'b']
    assert len(references) == 2
    (folder / 'middle.json').write_bytes(raw + b' ')
    with pytest.raises(ValueError, match='SHA256'):
        load_saved_inventory(run, root)
    (folder / 'middle.json').write_bytes(raw)
    run['input_reference']['documents'][0]['pages'][0]['width'] = 999
    with pytest.raises(ValueError, match='identity'):
        load_saved_inventory(run, root)


def test_output_guard_uses_relocated_source_before_any_analysis(tmp_path,monkeypatch):
    from reading_order import ingest
    from pairwise_analysis import analyze_saved_run
    monkeypatch.setattr(ingest,'PROJECT_ROOT',tmp_path)
    source=tmp_path/'test_libs/bounding_boxes/saved'
    source.mkdir(parents=True)
    run=tmp_path/'run';run.mkdir();(run/'manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='outside source'):
        analyze_saved_run(run,source/'generated','/mnt/c/old/test_libs/bounding_boxes/saved')
    assert not (source/'generated').exists()


def test_successor_differences_keep_original_ids():
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    row = next(r for r in analyze_predictions(run, inventory)['comparisons']
               if r['candidate_a'] == 'hantian' and r['candidate_b'] == 'docling'
               and r['paper_id'] == 'A' and r['page_idx'] == 0)
    assert sorted(row['successors_only_a']) == [['b', 'a'], ['c', 'b']]
    assert sorted(row['successors_only_b']) == [['a', 'b'], ['b', 'c']]
    assert row['pairs_inverted'] == 3


def test_mixed_docling_contracts_cannot_be_aggregated():
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    run['predictions'][7]['transformations']['cid_contract'] = 'different/v1'
    with pytest.raises(ValueError, match='CID'):
        analyze_predictions(run, inventory)


def test_empty_scope_has_no_decoder_contract_but_nonempty_scope_requires_one():
    from pairwise_analysis import analyze_predictions
    run, inventory = collection()
    run['predictions'][19]['transformations'] = {}
    run['predictions'][19]['native'] = {'empty_scope': True}
    assert pair(analyze_predictions(run, inventory))['coverage']['degenerate'] == 1
    run['predictions'][1]['transformations'] = {}
    with pytest.raises(ValueError, match='CID'):
        analyze_predictions(run, inventory)
