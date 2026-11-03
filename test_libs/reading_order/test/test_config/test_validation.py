"""Offline tests of the configuration gate; no models, network or installs."""
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


def load_validation():
    path = Path(__file__).with_name('validation.py')
    assert path.is_file(), 'configuration gate is not implemented'
    spec = importlib.util.spec_from_file_location('order_config_validation', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('status,expected', [('PASS', True), ('FAIL', False),
                                           ('NOT_RUN', False), ('UNSUPPORTED', False)])
def test_gate_never_accepts_incomplete_required_check(status, expected):
    api = load_validation()
    report = api.ConfigReport('run-a', [api.CheckResult('cuda', status, {})])
    assert report.ready({'cuda'}) is expected


def test_gate_rejects_missing_duplicate_and_unexpected_checks():
    api = load_validation()
    good = api.CheckResult('cuda', 'PASS', {})
    assert not api.ConfigReport('r', []).ready({'cuda'})
    assert not api.ConfigReport('r', [good, good]).ready({'cuda'})
    assert not api.ConfigReport('r', [good]).ready({'cuda', 'r2'})


def test_invalid_status_is_rejected():
    api = load_validation()
    with pytest.raises(ValueError):
        api.CheckResult('cuda', 'SKIPPED', {})


def test_pdf_requires_full_hash_and_header():
    api = load_validation()
    data = b'%PDF-1.7\nsynthetic fixture, not a real paper'
    expected = hashlib.sha256(data).hexdigest()
    assert api.verify_pdf(data, expected)['sha256'] == expected
    with pytest.raises(ValueError):
        api.verify_pdf(data, '0' * 64)
    with pytest.raises(ValueError):
        api.verify_pdf(b'<html>denied</html>', hashlib.sha256(b'<html>denied</html>').hexdigest())


def test_receipt_identity_changes_with_environment_or_probe():
    api = load_validation()
    a = api.fingerprint({'torch': 'a'}, 'probe-a')
    assert a == api.fingerprint({'torch': 'a'}, 'probe-a')
    assert a != api.fingerprint({'torch': 'b'}, 'probe-a')
    assert a != api.fingerprint({'torch': 'a'}, 'probe-b')


def test_receipt_must_belong_to_expected_run():
    api = load_validation()
    with pytest.raises(ValueError):
        api.ConfigReport.from_dict({'run_id': 'other', 'checks': []}, 'expected')


def test_secret_metadata_cannot_enter_receipt():
    api = load_validation()
    with pytest.raises(ValueError):
        api.CheckResult('r2', 'PASS', {'url': 'https://example.invalid/?X-Amz-Signature=secret'})


def test_failed_check_is_preserved_and_does_not_abort_following_checks():
    api = load_validation()
    def broken():
        raise RuntimeError('secret-url-must-not-be-logged')
    checks = [api.FunctionCheck('first', broken), api.FunctionCheck('second', lambda: {'value': 7})]
    report = api.run_checks('r', checks)
    assert [c.status for c in report.checks] == ['FAIL', 'PASS']
    assert report.checks[1].details == {'value': 7}
    assert 'secret-url' not in str(report.to_dict())


def test_source_check_rejects_changed_middle_and_bad_pointer(tmp_path):
    api = load_validation()
    assert hasattr(api, 'verify_mineru_references'), 'source reference check is missing'
    import json
    folder = tmp_path / '12'
    folder.mkdir()
    middle = b'{"pages":[{"blocks":[{"type":"text","bbox":[0.1,0.1,0.9,0.2]}]}]}'
    (folder / 'middle.json').write_bytes(middle)
    row = {'id': 'a', 'paper_sha256': 'b' * 64,
           'original_ref': '/content/old/12/middle.json#/pages/0/blocks/0',
           'original_sha256': hashlib.sha256(middle).hexdigest()}
    (folder / 'normalized.json').write_text(json.dumps([row]))
    assert api.verify_mineru_references(tmp_path)['documents'] == 1
    row['original_ref'] = '/content/old/12/middle.json#/pages/0/blocks/7'
    (folder / 'normalized.json').write_text(json.dumps([row]))
    with pytest.raises(ValueError):
        api.verify_mineru_references(tmp_path)
    row['original_ref'] = '/content/old/12/middle.json#/pages/0/blocks/0'
    (folder / 'normalized.json').write_text(json.dumps([row]))
    (folder / 'middle.json').write_bytes(middle + b' ')
    with pytest.raises(ValueError):
        api.verify_mineru_references(tmp_path)


def test_imports_do_not_start_processes_open_network_or_read_datasets(monkeypatch):
    import socket
    import subprocess
    def forbidden(*args, **kwargs):
        raise AssertionError('import attempted an external effect')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    for name in ('probe_environment', 'prepare_environment', 'run_config', 'inspect_host'):
        spec = importlib.util.spec_from_file_location('inert_' + name, Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def test_controller_import_does_not_assume_project_layout(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    source = Path(__file__).with_name('run_config.py').read_text()
    exec(compile(source, '/content/config/run_config.py', 'exec'),
         {'__file__': '/content/config/run_config.py', '__name__': 'configuration_import_test'})


def test_prepared_identity_detects_changed_candidate_and_checkpoint(tmp_path):
    monkey_path = Path(__file__).with_name('environment_identity.py')
    assert monkey_path.exists(), 'prepared environment identity gate is missing'
    spec = importlib.util.spec_from_file_location('config_identity', monkey_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact = tmp_path / 'model.safetensors'
    artifact.write_bytes(b'old checkpoint')
    record = {'requirements_sha256': 'a', 'sources_sha256': 'b',
              'artifacts': {'model.safetensors': hashlib.sha256(b'old checkpoint').hexdigest()},
              'versions': {'torch': 'one'}}
    assert module.validate_identity(tmp_path, record, 'a', 'b', {'torch': 'one'})
    for candidate, sources, versions in [('changed', 'b', {'torch': 'one'}),
                                          ('a', 'changed', {'torch': 'one'}),
                                          ('a', 'b', {'torch': 'two'})]:
        with pytest.raises(ValueError):
            module.validate_identity(tmp_path, record, candidate, sources, versions)
    artifact.write_bytes(b'different checkpoint')
    with pytest.raises(ValueError):
        module.validate_identity(tmp_path, record, 'a', 'b', {'torch': 'one'})


def test_checkpoint_only_allows_explicit_documented_unused_keys():
    api = load_validation()
    assert hasattr(api, 'validate_checkpoint_keys'), 'checkpoint key policy is missing'
    assert api.validate_checkpoint_keys({'active', 'unused'}, {'active'}, {'unused'}) == ['unused']
    with pytest.raises(ValueError):
        api.validate_checkpoint_keys({'active', 'unused'}, {'unused'}, {'unused'})
    with pytest.raises(ValueError):
        api.validate_checkpoint_keys({'active'}, {'active', 'extra'}, set())
