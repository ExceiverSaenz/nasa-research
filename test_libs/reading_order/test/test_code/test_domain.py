import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def api():
    assert importlib.util.find_spec('reading_order'), 'production package is absent'
    from reading_order import contracts, geometry, context
    return contracts, geometry, context


@pytest.mark.parametrize('reference', [
    'test_libs/reading_order/raw_results/example.json',
    r'C:\old checkout\test_libs\reading_order\raw_results\example.json',
    '/mnt/c/old checkout/test_libs/reading_order/raw_results/example.json',
])
def test_saved_references_follow_the_clone_not_the_original_machine(tmp_path,monkeypatch,reference):
    from reading_order import ingest
    clone=tmp_path/'different clone'
    target=clone/'test_libs/reading_order/raw_results/example.json'
    target.parent.mkdir(parents=True);target.write_text('{"verified":true}')
    monkeypatch.setattr(ingest,'PROJECT_ROOT',clone)
    monkeypatch.chdir(tmp_path)
    assert ingest.resolve_reference(reference).read_text()=='{"verified":true}'
    assert ingest.portable_reference(target)=='test_libs/reading_order/raw_results/example.json'


def test_rebased_reference_cannot_escape_the_project(tmp_path,monkeypatch):
    from reading_order import ingest
    monkeypatch.setattr(ingest,'PROJECT_ROOT',tmp_path)
    with pytest.raises(ValueError):
        ingest.resolve_reference('/old/test_libs/../../outside.json')


def test_explicit_run_argument_remains_relative_to_working_directory(tmp_path,monkeypatch):
    from reading_order.stability import read_reference,verify_unchanged
    monkeypatch.chdir(tmp_path)
    (tmp_path/'manifest.json').write_text('{"status":"PASS"}')
    run,reference=read_reference(Path('manifest.json'))
    assert run['status']=='PASS'
    verify_unchanged([reference])


@pytest.mark.parametrize('sequence', [['a', 'a'], ['a'], ['a', 'x'], [1, 0]])
def test_invalid_permutations_are_not_repaired(sequence):
    c, _, _ = api()
    with pytest.raises(ValueError):
        c.require_permutation(sequence, ['a', 'b'])


def test_registry_six_candidates_and_disjoint_sets():
    c, _, _ = api()
    assert len(c.CANDIDATES) == 6
    with pytest.raises(ValueError):
        c.Experiment(Path('.'), ['12'], ['12'])


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
@pytest.mark.parametrize('origin', ['top_left', 'bottom_left'])
def test_geometry_roundtrip_real_dimensions(rotation, origin):
    _, g, _ = api()
    raw = [0.1, 0.2, 0.7, 0.8]
    points = g.convert_box(raw, 600, 800, scale='normalized', origin=origin, rotation=rotation)
    assert g.inverse_box(points, 600, 800, scale='normalized', origin=origin, rotation=rotation) == pytest.approx(raw)


@pytest.mark.parametrize('box,width,height', [([.1, .1, .1, .2], 600, 800),
                                              ([0, 0, 1, 1], 1, 1),
                                              ([0, 0, 1, float('nan')], 600, 800)])
def test_invalid_geometry_never_becomes_zero(box, width, height):
    _, g, _ = api()
    with pytest.raises(ValueError):
        g.convert_box(box, width, height)


def test_ranks_are_inverted_and_routes_preserve_relative_order():
    c, _, ctx = api()
    assert c.ranks_to_ids([2, 0, 1], ['a', 'b', 'c']) == ['b', 'c', 'a']
    assert ctx.project(['b', 'c', 'a'], {'a', 'b'}) == ['b', 'a']
    assert ctx.permute(['a', 'b', 'c'], 1729) == ctx.permute(['a', 'b', 'c'], 1729)


def test_ingest_retains_child_without_bbox_and_null_text(tmp_path):
    api()
    from reading_order.ingest import Ingestor, LocalReferences
    folder = tmp_path / '12'
    folder.mkdir()
    middle = {'schema': 'docvortex.middle', 'schema_version': '2.0',
              'metadata': {'document': {'page_count': 1}},
              'extensions': {'docvortex_layout': {'pages': [{'page_idx': 0, 'width_pt': 600, 'height_pt': 800}]}},
              'pages': [{'page_idx': 0, 'blocks': [{'type': 'image', 'bbox': [.1, .1, .8, .8],
                                                  'content': [{'type': 'text', 'content': 'caption'}]}]}]}
    payload = json.dumps(middle).encode()
    (folder / 'middle.json').write_bytes(payload)
    prefix = '/content/previous/12/middle.json'
    rows = [dict(id='parent', paper_sha256='b' * 64, page_idx=0, raw_label='image',
                 bbox_normalized=[.1, .1, .8, .8], coordinate_system='normalized_top_left',
                 original_ref=prefix+'#/pages/0/blocks/0', original_sha256=hashlib.sha256(payload).hexdigest(),
                 native_parent_ref=None),
            dict(id='child', paper_sha256='b' * 64, page_idx=0, raw_label='text', bbox_normalized=None,
                 coordinate_system='normalized_top_left', original_ref=prefix+'#/pages/0/blocks/0/content/0',
                 original_sha256=hashlib.sha256(payload).hexdigest(), native_parent_ref=prefix+'#/pages/0/blocks/0')]
    (folder / 'normalized.json').write_text(json.dumps(rows))
    ingestor = Ingestor(LocalReferences(tmp_path))
    doc = ingestor.read('12', pdf_pages=[{'width': 600, 'height': 800, 'rotation': 0}])
    assert doc.eligible(0) == ['parent']
    assert doc.blocks[1].bbox is None
    assert doc.blocks[1].parent_id == 'parent'
    assert doc.blocks[0].text is None  # An image does not become its child's caption.
    assert doc.blocks[1].text == 'caption'
    before = payload
    manifest = ingestor.freeze(['12'], tmp_path / 'frozen', pdf_metadata={'12': [{'width': 600, 'height': 800, 'rotation': 0}]})
    assert (folder / 'middle.json').read_bytes() == before
    assert not list((tmp_path / 'frozen').rglob('normalized.json'))
    assert 'blocks' not in manifest['documents'][0]  # References, not a duplicated dataset.
    (folder / 'middle.json').write_bytes(payload + b' ')
    with pytest.raises(ValueError):
        ingestor.resolve(manifest)


def test_parent_cycles_are_rejected():
    _, _, ctx = api()
    with pytest.raises(ValueError):
        ctx.validate_parents({'a': 'b', 'b': 'a'})


def test_missing_model_input_is_unsupported_not_dropped():
    api()
    from reading_order.adapters.base import validate_length
    with pytest.raises(ValueError):
        validate_length(511, 510)
