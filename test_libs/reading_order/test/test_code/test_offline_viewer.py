"""Direct-file visualization must not depend on an HTTP process or copy inputs."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import pytest
from test_integration import synthetic_run


class SnapshotReader(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.parts=[]
    def handle_starttag(self,tag,attrs):
        self.active=tag=='script' and dict(attrs).get('id')=='reading-order-data'
    def handle_endtag(self,tag):
        if tag=='script':self.active=False
    def handle_data(self,data):
        if self.active:self.parts.append(data)


def snapshot(path):
    reader=SnapshotReader();reader.feed(path.read_text(encoding='utf-8'))
    return json.loads(''.join(reader.parts))


@pytest.mark.parametrize('legacy', [False,True])
def test_viewer_reopens_after_checkout_moves_without_changing_frozen_identity(tmp_path_factory,monkeypatch,legacy):
    from reading_order import ingest
    from reading_order.contracts import identity
    from reading_order.viewer import build_viewer,ViewerData
    tmp_path=tmp_path_factory.mktemp('move')
    old=tmp_path/'o';new=tmp_path/'n'
    monkeypatch.setattr(ingest,'PROJECT_ROOT',old)
    fixture=old/'test_libs/r'
    run=synthetic_run(fixture)
    image=fixture/'source/viewer_source/pages'/('a'*64)/'0.png'
    image.parent.mkdir(parents=True);image.write_bytes(b'background')
    manifest=run/'manifest.json';data=json.loads(manifest.read_text())
    if legacy:
        frozen=data['input_reference']
        frozen['source_root']='/mnt/c/previous-machine/test_libs/r/source/assembled/basic'
        frozen['input_profile_id']=identity({k:v for k,v in frozen.items() if k!='input_profile_id'})
        data['input_profile_id']=frozen['input_profile_id']
        for prediction in data['predictions']:prediction['scope']['input_profile_id']=frozen['input_profile_id']
        manifest.write_text(json.dumps(data))
    else:
        assert data['input_reference']['source_root']=='test_libs/r/source/assembled/basic'
    original=manifest.read_bytes()
    old.rename(new)
    monkeypatch.setattr(ingest,'PROJECT_ROOT',new)
    monkeypatch.chdir(tmp_path)
    relocated=new/'test_libs/r/run'
    build_viewer(relocated)
    assert ViewerData(relocated).page('12',0)['blocks'][0]['id']=='block-0'
    assert ViewerData(relocated).asset('12',0).read_bytes()==b'background'
    payload=snapshot(relocated/'viewer.html')
    assert (relocated/payload['pages']['12:0']['background']).resolve().read_bytes()==b'background'
    assert (relocated/'manifest.json').read_bytes()==original
    # Hash validation remains effective after rebasing.
    source=new/'test_libs/r/source/assembled/basic/12/middle.json'
    source.write_bytes(source.read_bytes()+b' ')
    with pytest.raises(ValueError,match='SHA256'):
        build_viewer(relocated)


def test_build_viewer_creates_direct_file_with_referenced_backgrounds(tmp_path):
    from reading_order.viewer import build_viewer
    run=synthetic_run(tmp_path)
    background=tmp_path/'source/viewer_source/pages'/('a'*64)/'0.png'
    background.parent.mkdir(parents=True);background.write_bytes(b'synthetic-background')
    original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path/'source').rglob('*') if p.is_file()}
    build_viewer(run)
    html=run/'viewer.html'
    assert html.is_file(), 'build-viewer must produce an HTML opened directly without a server'
    payload=snapshot(html);page=payload['pages']['12:0']
    assert (html.parent/page['background']).resolve()==background.resolve()
    assert page['blocks'][0]['id']=='block-0' and page['blocks'][0]['bbox']==[.1,.1,.9,.2]
    assert 'text' not in page['blocks'][0] and page['blocks'][0]['source_ref']
    assert payload['state']['run_sha256']==hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest()
    content=html.read_text(encoding='utf-8')
    assert 'connect-src &#x27;none&#x27;' in content or "connect-src 'none'" in content
    assert '<script src=' not in content and '<link rel="stylesheet"' not in content
    assert 'data:image/' not in content and '<script>unsafe()</script>' not in content
    assert not list(run.rglob('normalized.json')) and not list(run.rglob('*.pdf'))
    assert original=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in original}


def test_offline_snapshot_escapes_script_terminators_and_preserves_manifest(tmp_path):
    from reading_order.viewer import build_viewer
    run=synthetic_run(tmp_path);manifest=run/'manifest.json'
    data=json.loads(manifest.read_text());data['predictions'][0]['reason']='</script><img src=x onerror=alert(1)>'
    manifest.write_text(json.dumps(data));before=manifest.read_bytes()
    build_viewer(run);html=run/'viewer.html'
    assert html.exists(), 'Missing direct-file viewer'
    assert snapshot(html)['state']['run']['predictions'][0]['reason']==data['predictions'][0]['reason']
    assert data['predictions'][0]['reason'] not in html.read_text(encoding='utf-8')
    assert manifest.read_bytes()==before


def test_offline_export_rejects_changed_source_before_writing_html(tmp_path):
    from reading_order.viewer import build_viewer
    run=synthetic_run(tmp_path)
    source=tmp_path/'source/assembled/basic/12/middle.json'
    source.write_text(source.read_text()+' ')
    with pytest.raises(ValueError):build_viewer(run)
    assert not (run/'viewer.html').exists()


def test_offline_payload_is_visual_projection_not_full_dataset_or_score_copy(tmp_path):
    from reading_order.viewer import build_viewer
    run=synthetic_run(tmp_path);manifest=run/'manifest.json'
    original=json.loads(manifest.read_text())
    original['predictions'][0]['native']['pair_logits']=[[123.456]]
    manifest.write_text(json.dumps(original));before=manifest.read_bytes()
    build_viewer(run);payload=snapshot(run/'viewer.html')
    assert 'input_reference' not in payload['state']['run']
    assert 'pair_logits' not in payload['state']['run']['predictions'][0]['native']
    assert 'exclusions' not in payload['state']['run']['documents'][0]
    assert payload['manifest_href']=='manifest.json'
    assert manifest.read_bytes()==before
