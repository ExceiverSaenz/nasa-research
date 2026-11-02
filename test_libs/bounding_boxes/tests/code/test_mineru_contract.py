import json
import sys
import types
from pathlib import Path
from unittest.mock import patch
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))


def module(name,**members):
    m=types.ModuleType(name);m.__dict__.update(members);return m


def test_pinned_config_api_has_no_get_config(tmp_path):
    from bbx.adapters.mineru import run_mineru
    pdf=tmp_path/'1.pdf';pdf.write_bytes(b'%PDF-fixture')
    class Result:
        def to_json(self):return json.dumps({'pages':[{'page_idx':0,'blocks':[]}]})
        def save(self,writer):pass
    settings=types.SimpleNamespace(model=types.SimpleNamespace(vlm=types.SimpleNamespace(server_url=None)))
    modules={'torch':module('torch',cuda=types.SimpleNamespace(is_available=lambda:True,synchronize=lambda:None)),
        'mineru':module('mineru',__path__=[]),'mineru.config':module('mineru.config',config=settings),
        'mineru.parser':module('mineru.parser',parse=lambda *a,**kw:Result(),__path__=[]),
        'mineru.parser.writer':module('mineru.parser.writer',FileBasedDataWriter=lambda p:p)}
    with patch.dict(sys.modules,modules):
        result=run_mineru({'tier':'basic','id':'basic'},pdf,tmp_path/'out')
    assert result['page_indices']==[0]
