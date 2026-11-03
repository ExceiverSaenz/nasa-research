import json
from pathlib import Path
import pytest


def test_collection_selection_is_explicit_and_unique(tmp_path):
    from reading_order.collection import load_selection
    config=tmp_path/'selection.json'
    config.write_text(json.dumps(dict(source_root='original',paper_ids=['1','12'],timeout_s=300)))
    selected=load_selection(config)
    assert selected.paper_ids==['1','12'] and selected.source_root==tmp_path/'original'
    config.write_text(json.dumps(dict(source_root='original',paper_ids=['12','12'],timeout_s=300)))
    with pytest.raises(ValueError):load_selection(config)


def test_index_category_has_explicit_model_projections():
    from reading_order.adapters.engines import EngineAdapter,DOCLING_LABELS,DOCTR_LABELS,PP_CATEGORY_NAMES
    assert EngineAdapter('docling',Path('.'))._labels([{'raw_label':'index'}])==['index']
    assert DOCLING_LABELS['index']=='DOCUMENT_INDEX'
    assert DOCTR_LABELS['index']=='text'
    assert PP_CATEGORY_NAMES['index']=='content'
    with pytest.raises(ValueError):EngineAdapter('docling',Path('.'))._labels([{'raw_label':'unknown'}])


def test_resumption_requires_same_code_and_frozen_input(tmp_path):
    from reading_order.collection import validated_reuse
    prior=tmp_path/'prior';(prior/'canonical').mkdir(parents=True)
    context=dict(code_files={'engine':'v1'},input_profile_id='fixed',environment={'lock_sha256':'lock-v1'})
    (prior/'run-context.json').write_text(json.dumps(context))
    prediction=dict(candidate_id='docling',scope=dict(paper_id='12',page_idx=0),status='PASS',ordered_ids=['a'])
    (prior/'canonical/manifest.json').write_text(json.dumps(dict(input_profile_id='fixed',predictions=[prediction])))
    result=validated_reuse(prior,context)
    assert ('docling','12',0) in result and 'reused_from' in result['docling','12',0]
    with pytest.raises(ValueError):validated_reuse(prior,dict(context,code_files={'engine':'v2'}))
    with pytest.raises(ValueError):validated_reuse(prior,dict(context,input_profile_id='different'))
    with pytest.raises(ValueError):validated_reuse(prior,dict(context,environment={'lock_sha256':'lock-v2'}))


def test_collection_memory_only_pdf_and_reference_flow(tmp_path):
    from test_integration import synthetic_run
    from reading_order.collection import Selection,execute_collection
    from reading_order.contracts import CANDIDATES
    synthetic_run(tmp_path)
    source=tmp_path/'source/assembled/basic'
    before={str(p):p.read_bytes() for p in source.rglob('*.json')}
    class Transport:
        def __init__(self):self.pdf_requests=0;self.real_predictions=0
        def __call__(self,request):
            assert request['persist_input'] is False
            if request['action']=='pdf_metadata':
                self.pdf_requests+=1
                assert request['url']=='private-temporary-url'
                return dict(status='PASS',sha256='a'*64,pages=[dict(width=600,height=800,rotation=0)]*2)
            if request['blocks'][0]['id'].startswith('block-'):
                assert self.pdf_requests==1
                self.real_predictions+=1
            return dict(status='PASS',ordered_ids=[b['id'] for b in request['blocks']],native={})
    transport=Transport();output=tmp_path/'collection'
    summary=execute_collection(Selection(source,['12']),transport,lambda paper:'private-temporary-url',output,{}, {})
    assert summary['status']=='PASS' and summary['expected']==12
    assert transport.real_predictions==12
    assert all(row['statuses']['PASS']==2 for row in summary['per_candidate'])
    assert len(summary['per_candidate'])==len(CANDIDATES)
    assert before=={str(p):p.read_bytes() for p in source.rglob('*.json')}
    assert not list(output.rglob('*.pdf')) and not list(output.rglob('normalized.json')) and not list(output.rglob('middle.json'))
    for path in output.rglob('*.json'):
        assert 'private-temporary-url' not in path.read_text()
        assert '<script>unsafe()' not in path.read_text()


def test_collection_rejects_pdf_identity_before_real_inference(tmp_path):
    from test_integration import synthetic_run
    from reading_order.collection import Selection,execute_collection
    synthetic_run(tmp_path)
    class Transport:
        def __call__(self,request):
            if request['action']=='pdf_metadata':return dict(status='FAIL')
            assert all(b['id'].startswith('synthetic-') for b in request['blocks'])
            return dict(status='PASS',ordered_ids=[b['id'] for b in request['blocks']],native={})
    output=tmp_path/'collection'
    with pytest.raises(ValueError,match='identity'):
        execute_collection(Selection(tmp_path/'source/assembled/basic',['12']),Transport(),lambda paper:'private',output,{}, {})
    assert not (output/'canonical').exists()


def test_existing_collection_output_is_rejected_before_gates_or_colab(tmp_path,monkeypatch):
    from reading_order import collection
    output=tmp_path/'previous';output.mkdir()
    prior=output/'failure.json';prior.write_text('preserved')
    def forbidden(*args):pytest.fail('Existing output reached execution lifecycle')
    monkeypatch.setattr(collection,'require_test_receipt',forbidden)
    with pytest.raises(FileExistsError):
        collection.main(['--session','not-created','--environment-receipt','unused',
            '--test-receipt','unused','--output',str(output)])
    assert prior.read_text()=='preserved' and len(list(output.iterdir()))==1


def test_session_release_is_bounded_and_records_unconfirmed_close(tmp_path,monkeypatch):
    from reading_order import collection
    import subprocess
    def blocked(command,**kwargs):
        assert kwargs['timeout']==45
        raise subprocess.TimeoutExpired(command,45)
    monkeypatch.setattr(collection.subprocess,'run',blocked)
    with pytest.raises(RuntimeError):collection.release_session('owned-session',tmp_path)
    status=json.loads((tmp_path/'session-status.json').read_text())
    assert status==dict(session='owned-session',closed=False,error_type='TimeoutExpired')


def test_verified_pdf_metadata_reference_avoids_remote_pdf_requests(tmp_path):
    from test_integration import synthetic_run
    from reading_order.collection import Selection,execute_collection
    from reading_order.ingest import Ingestor,LocalReferences
    synthetic_run(tmp_path);source=tmp_path/'source/assembled/basic'
    doc=Ingestor(LocalReferences(source)).read('12')
    metadata={'12':dict(status='PASS',sha256='a'*64,pages=[dict(width=600,height=800,rotation=0)]*2,source=doc.references)}
    class Transport:
        def __call__(self,request):
            assert request['action']=='predict', 'PDF requests must stay on the verification host'
            return dict(status='PASS',ordered_ids=[b['id'] for b in request['blocks']],native={})
    def forbidden(paper):pytest.fail('Verified metadata must not request a bearer URL')
    summary=execute_collection(Selection(source,['12']),Transport(),forbidden,tmp_path/'collection',{}, {},
        pdf_metadata=metadata,pdf_metadata_reference={'path':'receipt.json','sha256':'receipt-sha'})
    assert summary['status']=='PASS'
    context=json.loads((tmp_path/'collection/run-context.json').read_text())
    assert context['pdf_metadata_reference']['sha256']=='receipt-sha'
    metadata['12']['source']={}
    with pytest.raises(ValueError,match='reference'):
        execute_collection(Selection(source,['12']),Transport(),forbidden,tmp_path/'wrong-source',{}, {},pdf_metadata=metadata)


def test_explicit_transport_recovery_keeps_model_code_identity_strict(tmp_path):
    from reading_order.collection import validated_reuse
    prior=tmp_path/'prior';(prior/'canonical').mkdir(parents=True)
    transport='code/reading_order/colab_backend.py'
    old=dict(code_files={transport:'old','engine':'fixed'},input_profile_id='fixed',environment={'lock_sha256':'fixed'})
    (prior/'run-context.json').write_text(json.dumps(old))
    pred=dict(candidate_id='hantian',scope=dict(paper_id='1',page_idx=0),status='PASS',ordered_ids=['a'])
    (prior/'canonical/manifest.json').write_text(json.dumps(dict(input_profile_id='fixed',predictions=[pred])))
    current=dict(old,code_files={transport:'new','engine':'fixed'})
    with pytest.raises(ValueError):validated_reuse(prior,current)
    assert len(validated_reuse(prior,current,allowed_code_changes=(transport,)))==1
    with pytest.raises(ValueError):validated_reuse(prior,dict(current,code_files={transport:'new','engine':'changed'}),allowed_code_changes=(transport,))
