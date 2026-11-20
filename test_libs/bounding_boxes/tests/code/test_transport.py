import json
import sys
import zipfile
from pathlib import Path
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))
from bbx.transport import ColabTransport,pack_code
from bbx.models import validate_manifest,verify_models


def test_transport_never_creates_without_explicit_authorization(tmp_path):
    calls=[]
    t=ColabTransport(tmp_path,runner=lambda args,**kw:calls.append(args))
    with pytest.raises(ValueError):t.create('test',authorized=False)
    assert calls==[]


def test_bundle_contains_no_runtime_credentials_or_original_pdfs(tmp_path):
    pack_code(ROOT,tmp_path/'code.zip')
    with zipfile.ZipFile(tmp_path/'code.zip') as z:
        assert 'run.py' in z.namelist()
        assert not any('runtime' in Path(n).parts or n.endswith('.env') or n.endswith('.pdf') for n in z.namelist())


def test_manifest_requires_complete_immutable_identity():
    with pytest.raises(ValueError):validate_manifest({'repo':'x','revision':'main','files':{}})


def test_missing_models_do_not_download(tmp_path):
    manifest={'repo':'x','revision':'a'*40,'files':{'weights.bin':{'bytes':1,'sha256':'b'*64}}}
    assert verify_models(tmp_path,manifest)[0]['status']=='NOT_RUN'


def test_cli_uses_existing_absolute_path_when_nonlogin_path_is_missing(tmp_path):
    from unittest.mock import patch
    from types import SimpleNamespace
    existing=tmp_path/'.local/bin/colab';existing.parent.mkdir(parents=True);existing.write_text('fixture')
    calls=[]
    def runner(args,**kwargs):calls.append(args);return SimpleNamespace(stdout='',stderr='')
    with patch('shutil.which',return_value=None),patch.object(Path,'home',return_value=tmp_path):
        t=ColabTransport(tmp_path/'transport',runner=runner);t.command(['sessions'])
    assert calls[0][0]==str(existing)
