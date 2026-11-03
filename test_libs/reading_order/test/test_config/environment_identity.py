"""Identity of a prepared environment; verification never installs or repairs."""
import hashlib
import importlib.metadata
import json
from pathlib import Path


def file_sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def versions():
    return {item.metadata['Name'].lower().replace('_', '-'): item.version
            for item in importlib.metadata.distributions()}


def validate_identity(root, record, requirements_sha256, sources_sha256, installed_versions):
    if (record['requirements_sha256'] != requirements_sha256
            or record['sources_sha256'] != sources_sha256 or record['versions'] != installed_versions):
        raise ValueError('Prepared candidate or installed versions changed')
    for name, expected in record['artifacts'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or file_sha(path) != expected:
            raise ValueError('Prepared artifact identity changed')
    return True


def seal(root, expected_requirements, expected_sources):
    if file_sha(root / 'requirements.in') != expected_requirements or file_sha(root / 'sources.json') != expected_sources:
        raise ValueError('Candidate differs from the explicit preparation receipt')
    sources = json.loads((root / 'sources.json').read_text())
    helper_hashes = json.loads((root / 'source-hashes.json').read_text())
    artifacts = {'requirements.lock': file_sha(root / 'requirements.lock')}
    for name in ('hantian_helpers.py', 'xycut.py'):
        if file_sha(root / name) != helper_hashes[name]:
            raise ValueError('Prepared helper changed')
        artifacts[name] = helper_hashes[name]
    for model, folder in [('hantian/layoutreader', 'hantian'),
                          ('PaddlePaddle/PP-DocLayoutV2_safetensors', 'pp_doclayout_v2')]:
        for name in ('config.json', 'model.safetensors'):
            path = root / 'models' / folder / name
            metadata = (path.parent / '.cache/huggingface/download' / (name + '.metadata')).read_text().splitlines()
            if metadata[0] != sources['models'][model]:
                raise ValueError('Checkpoint revision differs from pinned preparation')
            digest = file_sha(path)
            if name == 'model.safetensors' and metadata[1] != digest:
                raise ValueError('Checkpoint content differs from LFS SHA256')
            artifacts[str(path.relative_to(root))] = digest
    for path in (root / 'xy-smoke/target/release/order-config-smoke', root / 'xy-smoke/Cargo.lock'):
        artifacts[str(path.relative_to(root))] = file_sha(path)
    record = {'requirements_sha256': expected_requirements, 'sources_sha256': expected_sources,
              'artifacts': artifacts, 'versions': versions()}
    target = root / 'prepared-identity.json'
    with target.open('x') as stream:
        json.dump(record, stream, indent=2)
    return record


def verify(root):
    record = json.loads((root / 'prepared-identity.json').read_text())
    validate_identity(root, record, file_sha(root / 'requirements.in'), file_sha(root / 'sources.json'), versions())
    return {'prepared_identity_sha256': file_sha(root / 'prepared-identity.json'),
            'verified_artifacts': len(record['artifacts']), 'installed_packages': len(record['versions'])}
