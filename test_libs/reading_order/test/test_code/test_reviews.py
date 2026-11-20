import importlib.util
import json
import pytest


def store(tmp_path):
    assert importlib.util.find_spec('reading_order.reviews'), 'review store is absent'
    from reading_order.reviews import ReviewStore
    run = tmp_path/'run'
    run.mkdir()
    manifest = dict(run_id='run',input_profile_id='input',predictions=[dict(candidate_id='hantian',
                    scope=dict(paper_id='12',page_idx=0),status='PASS',ordered_ids=['a','b'])])
    (run/'manifest.json').write_text(json.dumps(manifest))
    return ReviewStore(run)


def observation(s):
    return dict(id='one',run_id='run',input_profile_id='input',run_sha256=s.run_sha256,
                case_id='12:0:hantian',candidate_id='hantian',control='docling',paper_id='12',pages=[0],
                block_ids=['a'],scope='transition',preference='equivalent',issue_type='other',
                note='<img src=x onerror=alert(1)>',ambiguity=True,author='reviewer',review_state='partial')


def test_revision_conflict_and_safe_text_roundtrip(tmp_path):
    s = store(tmp_path)
    note = observation(s)
    result = s.save(note,0)
    assert result['revision'] == 1
    assert s.load()['observations'][0]['note'] == note['note']
    with pytest.raises(ValueError):
        s.save(note,0)
    note['note'] = 'second version'
    s.save(note,1)
    assert '<img' in (s.directory/'history.jsonl').read_text()


@pytest.mark.parametrize('field,value',[('input_profile_id','other'),('run_id','other'),('block_ids',['unknown']),
                                        ('case_id','another'),('candidate_id','microsoft_layoutreader')])
def test_observations_cannot_escape_run_or_scope(tmp_path, field, value):
    s = store(tmp_path)
    note = observation(s)
    note[field] = value
    with pytest.raises(ValueError):
        s.save(note,0)
    assert s.load()['revision'] == 0


def test_import_idempotent_and_reviewed_without_incidents(tmp_path):
    s = store(tmp_path)
    note = observation(s)
    note.update(issue_type=None,preference='equivalent',review_state='reviewed')
    s.save(note,0)
    exported = s.load()
    result = s.import_data(exported,1)
    assert len(result['observations']) == 1
    assert result['states']['12:0:hantian'] == 'reviewed'


def test_server_rejects_foreign_origin_and_token(tmp_path):
    s = store(tmp_path)
    assert importlib.util.find_spec('reading_order.server'), 'server is absent'
    from reading_order.server import authorized
    assert authorized('127.0.0.1','127.0.0.1:8765','http://127.0.0.1:8765','token','token',8765,True)
    assert not authorized('127.0.0.1','foreign.invalid','http://foreign.invalid','token','token',8765,True)
    assert not authorized('127.0.0.1','127.0.0.1:8765','http://127.0.0.1:8765',None,'token',8765,True)
