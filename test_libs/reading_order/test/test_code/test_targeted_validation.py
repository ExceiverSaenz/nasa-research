import pytest


def test_runner_executes_only_selected_candidates(tmp_path):
    from reading_order.runner import Runner
    from reading_order.contracts import InputDocument,Block
    calls=[]
    class Backend:
        def predict(self,candidate,blocks,page,timeout):
            calls.append(candidate);return dict(ordered_ids=[b['id'] for b in blocks],native={})
    doc=InputDocument('12','f'*64,[dict(page_idx=0,width=600,height=800,rotation=0)],
                      [Block('a','f'*64,0,'text',[.1,.1,.2,.2],None,'synthetic')],{})
    result=Runner(Backend(),candidates=('docling',)).execute([doc],{'input_profile_id':'fixed'},tmp_path/'run')
    assert calls==['docling']
    assert result['candidate_ids']==['docling']


@pytest.mark.parametrize('candidates',[(),('unknown',),('docling','docling')])
def test_invalid_selection_is_rejected(candidates):
    from reading_order.runner import Runner
    with pytest.raises(ValueError):Runner(None,candidates=candidates)


def test_hantian_diagnostics_capture_only_rank_submatrix_and_torch_tie_order():
    from reading_order.adapters.engines import hantian_diagnostics
    class Matrix:
        def __getitem__(self,key):
            assert key==(slice(1,3),slice(None,2));return self
        def tolist(self):return [[2.,1.],[3.,4.]]
        def argsort(self,descending):
            assert descending is False
            return type('Indices',(),{'tolist':lambda self:[[1,0],[0,1]]})()
    assert hantian_diagnostics(Matrix(),2)==dict(rank_logits=[[2.,1.],[3.,4.]],rank_candidates=[[1,0],[0,1]])


def test_diagnostic_request_is_explicit_and_candidate_specific():
    from reading_order.colab_backend import MemoryBackend
    sent=[]
    backend=MemoryBackend(lambda r:sent.append(r),capture_diagnostics=('hantian',))
    backend.predict('docling',[],{},10);backend.predict('hantian',[],{},10)
    assert not sent[0]['capture_diagnostics'] and sent[1]['capture_diagnostics']
    assert all(not r['persist_input'] for r in sent)
