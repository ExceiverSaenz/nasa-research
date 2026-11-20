from collections import Counter, defaultdict
import json
from pathlib import Path


def summarize(reviews):
    cases = defaultdict(list)
    pages = set()
    issues = Counter()
    for observation in reviews.get('observations', []):
        cases[observation['case_id']].append(observation)
        if observation.get('issue_type'):
            issues[observation['issue_type']] += 1
            pages.update((observation['paper_id'], p) for p in observation['pages'])
    preferences = Counter()
    for case,observations in cases.items():
        if reviews.get('states',{}).get(case,'not_reviewed')=='not_reviewed':
            continue
        values = {o['preference'] for o in observations if o.get('preference')}
        preferences[next(iter(values)) if len(values) == 1 else 'indeterminate'] += 1
    states = Counter(reviews.get('states', {}).values())
    by_candidate = {}
    case_metadata = {case:(notes[0]['candidate_id'],notes[0]['paper_id']) for case,notes in cases.items()}
    for case in reviews.get('states',{}):
        pieces = case.split(':')
        if len(pieces)==3:
            case_metadata.setdefault(case,(pieces[2],pieces[0]))
    for candidate in sorted({value[0] for value in case_metadata.values()}):
        selected = {case:state for case,state in reviews.get('states',{}).items()
                    if case_metadata.get(case,(None,None))[0]==candidate}
        counts = Counter(selected.values())
        documents = {case_metadata[case][1] for case in selected}
        fully = sorted(p for p in documents if all(state=='reviewed' for case,state in selected.items()
                                                   if case_metadata[case][1]==p))
        pref = Counter()
        for case,state in selected.items():
            if state=='not_reviewed':
                continue
            values = {o['preference'] for o in cases.get(case,[]) if o.get('preference')}
            if values:
                pref[next(iter(values)) if len(values)==1 else 'indeterminate']+=1
        by_candidate[candidate] = dict(expected_cases=len(selected),reviewed_cases=counts['reviewed'],
            partial_cases=counts['partial'],not_reviewed_cases=counts['not_reviewed'],preferences=dict(pref),
            expected_documents=sorted(documents),fully_reviewed_documents=fully)
    common = set.intersection(*(set(row['fully_reviewed_documents']) for row in by_candidate.values())) if by_candidate else set()
    return dict(revision=reviews['revision'], reviewed_cases=states['reviewed'], partial_cases=states['partial'],
                not_reviewed_cases=states['not_reviewed'], preferences=dict(preferences), issue_observations=dict(issues),
                reviewed_without_incidents=sum(state=='reviewed' and not any(o.get('issue_type') for o in cases.get(case,[]))
                                               for case,state in reviews.get('states',{}).items()),
                affected_pages=len(pages), by_candidate=by_candidate,common_fully_reviewed_documents=sorted(common),
                selection='selection_pending')


def summarize_reviews(run_path, reviews_revision, output):
    from reading_order.reviews import ReviewStore
    reviews = ReviewStore(Path(run_path)).load()
    if reviews['revision'] != reviews_revision:
        raise ValueError('Review revision changed')
    result = summarize(reviews)
    result['run_id'] = Path(run_path).name
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'reviews-summary.json').write_text(json.dumps(result, indent=2))
    return result
