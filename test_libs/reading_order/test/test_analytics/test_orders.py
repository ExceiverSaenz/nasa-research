import importlib.util
import pytest


def api():
    assert importlib.util.find_spec('compare_orders'), 'analytics is absent'
    from compare_orders import compare_pair, summarize_coverage
    return compare_pair, summarize_coverage


def prediction(ids, status='PASS', **scope):
    return dict(candidate_id='docling', scope=dict(paper_id='12', page_idx=0,
                input_profile_id='a', eligible_ids_hash='abc', permutation_seed=1729, route=None, **scope),
                status=status, ordered_ids=ids)


@pytest.mark.parametrize('left,right,inversion,jaccard', [(['a','b','c'], ['a','b','c'], 0, 1),
                                                         (['a','b','c'], ['c','b','a'], 1, 0)])
def test_agreement_metrics_hand_checked(left, right, inversion, jaccard):
    compare, _ = api()
    result = compare(prediction(left), prediction(right))
    assert result['precedence_disagreement'] == inversion
    assert result['successor_jaccard'] == jaccard
    assert result['pairs_evaluated'] == 3
    assert result['metric_kind'] == 'agreement'


@pytest.mark.parametrize('ids', [[], ['a']])
def test_small_scopes_are_valid_but_have_no_metrics(ids):
    compare, _ = api()
    assert compare(prediction(ids), prediction(ids))['precedence_disagreement'] is None


def test_scopes_and_failures_are_not_comparable():
    compare, _ = api()
    left = prediction(['a','b'])
    right = prediction(['a','b'])
    right['scope']['route'] = 'independent'
    assert compare(left, right)['status'] == 'not_comparable'
    assert compare(left, prediction(None, 'FAIL'))['status'] == 'not_comparable'


def test_coverage_does_not_hide_failures_in_valid_mean():
    _, coverage = api()
    result = coverage([prediction(['a']), prediction(None, 'FAIL'), prediction(None, 'UNSUPPORTED')])
    assert result['expected'] == 3
    assert result['produced_valid'] == 1
    assert result['failed'] == 1
    assert result['unsupported'] == 1


def test_repeated_observations_are_not_multiple_votes():
    assert importlib.util.find_spec('summarize_reviews'), 'review analytics is absent'
    from summarize_reviews import summarize
    notes = [dict(id='one', case_id='p0-hantian', candidate_id='hantian', paper_id='12',
                  pages=[0], preference='equivalent', issue_type='column_mix'),
             dict(id='two', case_id='p0-hantian', candidate_id='hantian', paper_id='12',
                  pages=[0], preference='equivalent', issue_type='paragraph_break')]
    result = summarize(dict(revision=2, observations=notes, states={'p0-hantian': 'reviewed', 'p1-hantian': 'not_reviewed'}))
    assert result['reviewed_cases'] == 1
    assert result['not_reviewed_cases'] == 1
    assert result['preferences']['equivalent'] == 1
    assert result['affected_pages'] == 1


def test_preferences_remain_attributed_and_paired_coverage_is_explicit():
    from summarize_reviews import summarize
    result=summarize(dict(revision=1,states={'12:0:hantian':'reviewed','12:0:doctr':'not_reviewed',
                                            '14:0:doctr':'reviewed'},observations=[
        dict(id='a',case_id='12:0:hantian',candidate_id='hantian',paper_id='12',pages=[0],
             preference='candidate_better',issue_type=None),
        dict(id='b',case_id='14:0:doctr',candidate_id='doctr',paper_id='14',pages=[0],
             preference='docling_better',issue_type=None)]))
    assert 'by_candidate' in result, 'candidate attribution is absent'
    assert result['by_candidate']['hantian']['preferences']['candidate_better']==1
    assert result['by_candidate']['doctr']['preferences']['docling_better']==1
    assert result['common_fully_reviewed_documents']==[]
