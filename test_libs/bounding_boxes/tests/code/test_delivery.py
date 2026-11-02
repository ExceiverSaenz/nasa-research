import json
import sys
from pathlib import Path
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))
from bbx.delivery import aggregate


def test_aggregate_keeps_missing_tools_and_all_pages(tmp_path):
    papers=[{'name':'1.pdf','sha256':'p','pages':2}]
    config={'tools':[{'id':t} for t in ('heron','heron101','basic','standard')]}
    data=aggregate(tmp_path,papers,config,'r',render=False)
    assert len(data['pages'])==2
    assert all(p['status']=='failed' for p in data['pages'])
    assert all(len(p['tool_status'])==4 for p in data['pages'])


def test_aggregate_never_accepts_uninventoried_detections(tmp_path):
    p=tmp_path/'heron'/'1';p.mkdir(parents=True)
    (p/'normalized.json').write_text(json.dumps([{'paper_sha256':'other','page_idx':0}]))
    with pytest.raises(ValueError):aggregate(tmp_path,[{'name':'1.pdf','sha256':'p','pages':1}],{'tools':[{'id':'heron'}]},'r',render=False)
