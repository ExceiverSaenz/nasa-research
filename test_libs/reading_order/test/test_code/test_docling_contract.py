"""Docling identity contract using synthetic elements, never a real model."""
import copy
import itertools
import sys
from types import SimpleNamespace
import pytest


def block(identity,ordinal):
    return dict(id=identity,raw_label='text',text=identity,page_idx=2,
                source_ref=f'/remote/12/middle.json#/pages/2/blocks/{ordinal}',
                bbox=[.1,.1,.8,.2])


@pytest.fixture
def engine(monkeypatch,tmp_path):
    from reading_order.adapters.engines import EngineAdapter
    captured=[]
    behavior={'mode':'sorted'}
    class Predictor:
        def predict_reading_order(self,elements):
            captured.append(elements)
            if behavior['mode']=='unknown':return [SimpleNamespace(cid=999),*elements[1:]]
            if behavior['mode']=='duplicate':return [elements[0]]*len(elements)
            return sorted(elements,key=lambda e:e.cid)
    monkeypatch.setitem(sys.modules,'docling.models.postprocessing.reading_order_rb',SimpleNamespace(
        ReadingOrderPredictor=Predictor,PageElement=lambda **kw:SimpleNamespace(**kw)))
    monkeypatch.setitem(sys.modules,'docling_core.types.doc',SimpleNamespace(
        CoordOrigin=SimpleNamespace(TOPLEFT='TOPLEFT'),DocItemLabel=SimpleNamespace(TEXT='TEXT'),Size=lambda **kw:kw))
    adapter=EngineAdapter('docling',tmp_path)
    def predict(blocks):
        return adapter._docling(blocks,dict(page_idx=2,width=600,height=800),[b['bbox'] for b in blocks])
    return predict,captured,behavior


def test_source_cids_refs_and_decoding_survive_every_presentation_permutation(engine):
    predict,captured,_=engine
    blocks=[block('a',7),block('b',2),block('c',11)]
    preserved=copy.deepcopy(blocks)
    for incoming in itertools.permutations(blocks):
        result=predict(list(incoming))
        assert {e.text:e.cid for e in captured[-1]}=={'a':7,'b':2,'c':11}
        assert {e.text:e.ref['cref'] for e in captured[-1]}=={'a':'#/texts/7','b':'#/texts/2','c':'#/texts/11'}
        assert [e.text for e in captured[-1]]==[b['id'] for b in incoming]
        assert result['ordered_ids']==['b','a','c']
        assert [incoming[i]['id'] for i in result['native']['indices']]==result['ordered_ids']
        assert result['native']['cids']==[2,7,11]
        assert result['native']['cid_to_id']=={'2':'b','7':'a','11':'c'}
        assert result['transformations']['cid_contract']=='mineru_top_level_block_ordinal/v1'
    assert blocks==preserved


def test_source_adjacency_is_preserved_and_gaps_are_not_compacted(engine):
    predict,captured,_=engine
    blocks=[block('a',2),block('b',3),block('c',9)]
    for incoming in itertools.permutations(blocks):
        predict(list(incoming))
        entities=captured[-1]
        assert {(a.text,b.text) for a in entities for b in entities if a.cid+1==b.cid}=={('a','b')}


@pytest.mark.parametrize('reference',[
    'unresolved','file#/pages/1/blocks/7','file#/pages/2/blocks/7/content/0',
    'file#/pages/2/blocks/-1','file#/pages/2/blocks/07','file#/pages/2/blocks/7/'])
def test_unresolved_or_non_root_reference_is_rejected_before_predictor(engine,reference):
    predict,captured,_=engine
    value=block('a',7);value['source_ref']=reference
    with pytest.raises(ValueError):predict([value])
    assert captured==[]


@pytest.mark.parametrize('change',['duplicate_cid','duplicate_id','different_page'])
def test_ambiguous_identity_is_rejected_before_predictor(engine,change):
    predict,captured,_=engine
    a,b=block('a',2),block('b',3)
    if change=='duplicate_cid':b['source_ref']=a['source_ref']
    if change=='duplicate_id':b['id']=a['id']
    if change=='different_page':b['page_idx']=1
    with pytest.raises(ValueError):predict([a,b])
    assert captured==[]


@pytest.mark.parametrize('mode',['unknown','duplicate'])
def test_invalid_native_cids_are_not_repaired(engine,mode):
    predict,_,behavior=engine
    behavior['mode']=mode
    with pytest.raises(ValueError):predict([block('a',2),block('b',7)])
