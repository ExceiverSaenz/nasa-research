import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())))
from bbx.artifact_store import ArtifactStore, plan_duplicates, restore_backup


def fixture_files(root):
    paths = [root / 'results' / name / 'pages' / '0.png' for name in ('a', 'b')]
    for p in paths:
        p.parent.mkdir(parents=True)
        p.write_bytes(b'original image bytes')
    return paths


def test_plan_limits_scope_and_preserves_different_content(tmp_path):
    paths = fixture_files(tmp_path)
    (paths[0].parent / '1.png').write_bytes(b'different')
    (tmp_path / 'results' / 'a' / 'private.json').write_bytes(paths[0].read_bytes())
    plan = plan_duplicates(tmp_path)
    assert len(plan['groups']) == 1
    assert plan['groups'][0]['paths'] == [p.relative_to(tmp_path).as_posix() for p in paths]


def test_migration_preserves_bytes_and_replaces_copies_with_references(tmp_path):
    paths = fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    result = store.migrate(tmp_path / 'backup.zip')
    assert result['saved_bytes'] == len(b'original image bytes')
    assert os.path.samefile(*paths)
    assert paths[0].read_bytes() == b'original image bytes'
    assert store.verify()['aliases'] == 2
    assert store.migrate(tmp_path / 'unused-backup.zip')['saved_bytes'] == 0
    assert not (tmp_path / 'unused-backup.zip').exists()


def test_backup_restores_independent_original_paths(tmp_path):
    paths = fixture_files(tmp_path)
    backup = tmp_path / 'backup.zip'
    ArtifactStore(tmp_path).migrate(backup)
    restore_backup(tmp_path, backup)
    assert not os.path.samefile(*paths)
    assert all(p.read_bytes() == b'original image bytes' for p in paths)


def test_corrupt_existing_cache_fails_before_replacing_inputs(tmp_path):
    paths = fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    obj = store.object_path(hashlib.sha256(paths[0].read_bytes()).hexdigest())
    obj.parent.mkdir(parents=True)
    obj.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='[Cc]orrupt'):
        store.migrate(tmp_path / 'backup.zip')
    assert not os.path.samefile(*paths)
    assert all(p.read_bytes() == b'original image bytes' for p in paths)


def test_hardlink_failure_leaves_inputs_untouched(tmp_path):
    paths = fixture_files(tmp_path)
    with patch('bbx.artifact_store.os.link', side_effect=OSError('unsupported')):
        with pytest.raises(OSError):
            ArtifactStore(tmp_path).migrate(tmp_path / 'backup.zip')
    assert not os.path.samefile(*paths)
    assert all(p.read_bytes() == b'original image bytes' for p in paths)


def test_sharing_rejects_paths_outside_root(tmp_path):
    store = ArtifactStore(tmp_path / 'allowed')
    outsider = tmp_path / 'outside.png'
    outsider.write_bytes(b'private')
    with pytest.raises(ValueError):
        store.share(outsider, tmp_path / 'allowed' / 'copy.png')


def test_sharing_a_cached_input_does_not_replace_the_read_only_source(tmp_path):
    store = ArtifactStore(tmp_path)
    seed, source, destination = [tmp_path / name for name in ('seed.png', 'source.png', 'view.png')]
    seed.write_bytes(b'same')
    source.write_bytes(b'same')
    store.share(seed, seed)
    identity = source.stat().st_ino
    store.share(source, destination)
    assert source.stat().st_ino == identity
    assert os.path.samefile(seed, destination)


def test_atomic_updates_do_not_mutate_other_aliases(tmp_path):
    paths = fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    store.migrate(tmp_path / 'backup.zip')
    replacement = paths[0].with_suffix('.new')
    replacement.write_bytes(b'new output')
    replacement.replace(paths[0])
    assert paths[1].read_bytes() == b'original image bytes'
    assert store.object_path(hashlib.sha256(paths[1].read_bytes()).hexdigest()).read_bytes() == paths[1].read_bytes()




def test_restore_refuses_to_overwrite_later_edits(tmp_path):
    paths = fixture_files(tmp_path)
    backup = tmp_path / 'backup.zip'
    ArtifactStore(tmp_path).migrate(backup)
    new = paths[0].with_suffix('.new')
    new.write_bytes(b'user edit')
    new.replace(paths[0])
    with pytest.raises(ValueError, match='changed'):
        restore_backup(tmp_path, backup)
    assert paths[0].read_bytes() == b'user edit'


def test_later_migration_does_not_touch_superseded_aliases(tmp_path):
    import zipfile
    paths = fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    store.migrate(tmp_path / 'first.zip')
    replacement = paths[0].with_suffix('.new')
    replacement.write_bytes(b'new result')
    replacement.replace(paths[0])
    third = tmp_path / 'results/c/0.png'
    third.parent.mkdir()
    third.write_bytes(paths[1].read_bytes())
    backup = tmp_path / 'second.zip'
    store.migrate(backup)
    assert paths[0].read_bytes() == b'new result'
    assert os.path.samefile(paths[1], third)
    with zipfile.ZipFile(backup) as archive:
        plan = json.loads(archive.read('manifest.json'))
    assert {p for g in plan['groups'] for p in g['paths']} == {
        paths[1].relative_to(tmp_path).as_posix(), third.relative_to(tmp_path).as_posix()}


def test_idempotent_migration_detects_corruption(tmp_path):
    paths = fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    store.migrate(tmp_path / 'backup.zip')
    paths[0].write_bytes(b'in-place corruption')
    with pytest.raises(ValueError, match='[Cc]orrupt'):
        store.migrate(tmp_path / 'second.zip')


def test_incomplete_migration_requires_recovery(tmp_path):
    fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    store.migrate(tmp_path / 'backup.zip')
    journal = json.loads(store.index.read_text())
    journal['state'] = 'prepared'
    store.index.write_text(json.dumps(journal))
    with pytest.raises(ValueError, match='[Ii]ncomplete'):
        store.migrate(tmp_path / 'second.zip')
    restore_backup(tmp_path, tmp_path / 'backup.zip')
    assert store.migrate(tmp_path / 'second.zip')['saved_bytes'] > 0


def test_recovery_before_any_object_was_created_can_retry(tmp_path):
    fixture_files(tmp_path)
    store = ArtifactStore(tmp_path)
    backup = tmp_path / 'backup.zip'
    with patch.object(store, 'share', side_effect=OSError('interrupted')):
        with pytest.raises(OSError):
            store.migrate(backup)
    restore_backup(tmp_path, backup)
    assert store.migrate(tmp_path / 'retry.zip')['hashes_preserved']


def test_restore_rejects_traversal_before_any_write(tmp_path):
    import zipfile
    content = b'x'
    digest = hashlib.sha256(content).hexdigest()
    plan = {'schema': 'bounding-box-artifact-storage/1', 'groups': [
        {'sha256': digest, 'paths': ['../outside.png'], 'bytes': 1}]}
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('manifest.json', json.dumps(plan))
        z.writestr('objects/' + digest, content)
    with pytest.raises(ValueError):
        restore_backup(tmp_path, archive)


def test_render_replacement_cannot_write_through_shared_background(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bbx.delivery import aggregate
    attempt = tmp_path / 'attempt'
    image = attempt / 'pages' / 'sha' / '0.png'
    image.parent.mkdir(parents=True)
    image.write_bytes(b'preserved old image')
    other = tmp_path / 'other.png'
    os.link(image, other)

    class FakeImage:
        def save(self, path):
            Path(path).write_bytes(b'new rendered bytes')

    class FakePage:
        def render(self, **kwargs):
            return SimpleNamespace(to_pil=lambda: FakeImage())

    class FakeDocument:
        def __getitem__(self, page):
            return FakePage()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, 'pypdfium2', SimpleNamespace(PdfDocument=lambda _: FakeDocument()))
    aggregate(attempt, [{'name': '1.pdf', 'sha256': 'sha', 'pages': 1}],
              {'tools': []}, 'fixture', render=True, pdf_dir=tmp_path)
    assert image.read_bytes() == b'new rendered bytes'
    assert other.read_bytes() == b'preserved old image'
