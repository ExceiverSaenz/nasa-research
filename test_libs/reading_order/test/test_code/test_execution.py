import importlib.util
from dataclasses import asdict
import pytest


def api():
    assert importlib.util.find_spec('reading_order.runner'), 'runner is absent'
    from reading_order.runner import Runner
    return Runner


class FakeBackend:
    def predict(self, candidate, blocks, page, timeout_s):
        if candidate == 'hantian':
            raise TimeoutError()
        if candidate == 'xycut':
            return {'ordered_ids': [blocks[0]['id']] * len(blocks), 'native': {}}
        return {'ordered_ids': [b['id'] for b in blocks], 'native': {'synthetic': True}}


def test_runner_retains_timeout_and_invalid_output_and_refuses_overwrite(tmp_path):
    Runner = api()
    from reading_order.contracts import Block, InputDocument
    blocks = [Block(x, 'f'*64, 0, 'text', [.1,y,.9,y+.1], None, '#/'+x) for x,y in [('a',.1),('b',.3)]]
    doc = InputDocument('12', 'f'*64, [dict(page_idx=0,width=600,height=800,rotation=0)], blocks, {})
    run = tmp_path/'run'
    report = Runner(FakeBackend()).execute([doc], {'input_profile_id':'fixed'}, run)
    assert len(report['predictions']) == 6
    statuses = {p['candidate_id']:p['status'] for p in report['predictions']}
    assert statuses['hantian'] == 'FAIL'
    assert statuses['xycut'] == 'FAIL'
    assert statuses['docling'] == 'PASS'
    with pytest.raises(FileExistsError):
        Runner(FakeBackend()).execute([doc], {'input_profile_id':'fixed'}, run)


@pytest.mark.parametrize('ranks,expected', [
    ([2,0,1], ['b','c','a']),
    ([1,2,0], ['c','a','b']),
    ([0,0,2], None),
])
def test_pp_adapter_decodes_official_ranks_and_rejects_duplicates(monkeypatch,tmp_path,ranks,expected):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace
    import numpy as np
    from reading_order.adapters.engines import EngineAdapter

    class Tensor:
        def __init__(self,values): self.values=np.asarray(values)
        def unsqueeze(self,axis): return Tensor(np.expand_dims(self.values,axis))
        def cpu(self): return self
        def tolist(self): return self.values.tolist()

    logits=Tensor([[[0.,2.,-1.],[0.,0.,3.],[0.,0.,0.]]])
    calls=[]
    class Processor:
        def _get_order_seqs(self,actual):
            assert actual is logits
            calls.append(actual)
            return Tensor([ranks])

    def unexpected_load(*args,**kwargs):
        raise AssertionError('Offline adapter contract test must not load weights')
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(
        tensor=lambda values,**kw:Tensor(values),ones=lambda shape,**kw:Tensor(np.ones(shape)),
        bool=bool,inference_mode=nullcontext,isfinite=lambda value:np.isfinite(value.values)))
    monkeypatch.setitem(sys.modules,'safetensors.torch',SimpleNamespace(load_file=unexpected_load))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(
        AutoConfig=None,PPDocLayoutV2ReadingOrder=None,PPDocLayoutV2ImageProcessor=Processor))
    adapter=EngineAdapter('pp_doclayout_v2',tmp_path)
    adapter.config=SimpleNamespace(reading_order_config=SimpleNamespace(max_position_embeddings=512),
                                   id2label={0:'text'},class_order={0:0})
    adapter.model=lambda **kwargs:logits
    blocks=[dict(id=identity,raw_label='text',bbox=[.1,.1,.8,.2]) for identity in 'abc']
    if expected is None:
        with pytest.raises(ValueError): adapter.predict(blocks,dict(width=600,height=800))
    else:
        result=adapter.predict(blocks,dict(width=600,height=800))
        assert result['ordered_ids']==expected
        assert result['native']==dict(pair_logits=logits.tolist()[0],ranks=ranks)
        assert result['transformations']['decoder']=='Transformers PPDocLayoutV2ImageProcessor._get_order_seqs'
    assert calls==[logits]


def test_memory_transport_does_not_log_or_persist_payloads():
    assert importlib.util.find_spec('reading_order.colab_backend'), 'memory transport is absent'
    from reading_order.colab_backend import MemoryBackend
    messages = []
    def transport(request):
        messages.append(request)
        return dict(ordered_ids=['a'], native={'permutation':[0]})
    backend = MemoryBackend(transport)
    assert backend.predict('docling',[{'id':'a'}], {'page_idx':0},10)['ordered_ids'] == ['a']
    assert messages[0]['persist_input'] is False


def test_docling_uses_valid_temporary_refs_without_losing_original_ids(monkeypatch,tmp_path):
    import re,sys
    from types import SimpleNamespace
    from reading_order.adapters.engines import EngineAdapter
    def element(**values):
        assert re.fullmatch(r'#/texts/\d+',values['ref']['cref'])
        return SimpleNamespace(**values)
    class Predictor:
        def predict_reading_order(self,elements):return list(reversed(elements))
    monkeypatch.setitem(sys.modules,'docling.models.postprocessing.reading_order_rb',SimpleNamespace(
        ReadingOrderPredictor=Predictor,PageElement=element))
    monkeypatch.setitem(sys.modules,'docling_core.types.doc',SimpleNamespace(
        CoordOrigin=SimpleNamespace(TOPLEFT='TOPLEFT'),DocItemLabel=SimpleNamespace(TEXT='TEXT'),
        Size=lambda **kw:kw))
    result=EngineAdapter('docling',tmp_path)._docling(
        [dict(id='original-a',raw_label='text',text='a',page_idx=0,source_ref='fixture#/pages/0/blocks/0'),
         dict(id='original-b',raw_label='text',text='b',page_idx=0,source_ref='fixture#/pages/0/blocks/1')],
        dict(width=600,height=800,page_idx=0),[[.1,.1,.9,.2],[.1,.3,.9,.4]])
    assert result['ordered_ids']==['original-b','original-a']
