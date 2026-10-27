"""Integrity, append-only publication and portable archive helpers; stdlib only."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def safe_name(name):
    p = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or p.is_absolute()
            or any(x in ('', '.', '..') for x in name.split('/'))
            or p.as_posix() != name):
        raise ValueError('Unsafe archive path: ' + name)
    return p


def check_members(z):
    infos = z.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(n.casefold() for n in names)):
        raise ValueError('Duplicate/case-colliding archive member')
    for item in infos:
        safe_name(item.filename)
        mode = (item.external_attr >> 16) & 0xffff
        if item.is_dir() or stat.S_ISLNK(mode) or item.flag_bits & 1:
            raise ValueError('Directories, symlinks or encrypted members not permitted')
    return names


def member_digest(z, name):
    h = hashlib.sha256()
    with z.open(name) as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def extract_bundle(archive, destination, expected_sha256):
    """Verify the entire package before writing any extracted file."""
    archive, destination = Path(archive), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if digest(archive) != expected_sha256:
        raise ValueError('Bundle SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        names = check_members(z)
        if sum(i.file_size for i in z.infolist()) > 20 * 1024**3:
            raise ValueError('Bundle exceeds 20 GiB expanded budget')
        manifest = json.loads(z.read('bundle-manifest.json'))
        if manifest.get('schema') != 'integration-demo-bundle/1':
            raise ValueError('Unsupported bundle manifest')
        files = manifest['files']
        if set(names) != set(files) | {'bundle-manifest.json'}:
            raise ValueError('Bundle manifest/member mismatch')
        for name, spec in files.items():
            if z.getinfo(name).file_size != spec['bytes'] or member_digest(z, name) != spec['sha256']:
                raise ValueError('Bundle member integrity: ' + name)
        destination.mkdir(parents=True, exist_ok=False)
        for name in names:
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
    return manifest


def durable_copy(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    partial = destination.with_name(destination.name + '.partial')
    with source.open('rb') as src, partial.open('xb') as dst:
        shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
    if digest(source) != digest(partial):
        raise ValueError('Backup copy SHA256 mismatch')
    partial.rename(destination)
    return digest(destination)


def make_archive(state, archive):
    """Bundle the full run, including raw prepared sources and failure logs."""
    state, archive = Path(state).resolve(), Path(archive).resolve()
    if archive == state or archive.is_relative_to(state):
        raise ValueError('Archive must be outside run directory')
    if archive.exists() or archive.with_suffix('.sha256').exists():
        raise FileExistsError(archive)
    status = read_json(state / 'status.json')
    if status['status'] not in ('completed', 'failed', 'partial'):
        raise ValueError('Cannot archive an active run')
    files = {p.relative_to(state).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p))
             for p in sorted(state.rglob('*')) if p.is_file()}
    if 'backup-manifest.json' in files or any(p.is_symlink() for p in state.rglob('*')):
        raise ValueError('Unexpected backup manifest or symlink')
    partial = archive.with_name(archive.name + '.partial')
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
        for name in files:
            z.write(state / name, name)
        z.writestr('backup-manifest.json', json.dumps(dict(schema='integration-demo-backup/1',
                   status=status['status'], files=files), ensure_ascii=False, sort_keys=True))
    partial.rename(archive)
    with archive.with_suffix('.sha256').open('x', encoding='ascii') as stream:
        stream.write(digest(archive) + '\n')
    return verify_archive(archive, archive.with_suffix('.sha256'))


def verify_archive(archive, sidecar):
    archive = Path(archive)
    if digest(archive) != Path(sidecar).read_text(encoding='ascii').strip():
        raise ValueError('Result archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        names = check_members(z)
        manifest = json.loads(z.read('backup-manifest.json'))
        if manifest.get('schema') != 'integration-demo-backup/1':
            raise ValueError('Unknown result archive schema')
        if set(names) != set(manifest['files']) | {'backup-manifest.json'}:
            raise ValueError('Result archive membership mismatch')
        for name, spec in manifest['files'].items():
            if z.getinfo(name).file_size != spec['bytes'] or member_digest(z, name) != spec['sha256']:
                raise ValueError('Result archive member mismatch: ' + name)
        status = json.loads(z.read('status.json'))['status']
        if status != manifest['status'] or status not in ('completed', 'failed', 'partial'):
            raise ValueError('Result terminal status mismatch')
    return dict(status=status, sha256=digest(archive), members=len(names), integrity_verified=True,
                semantic_validation='pending_after_full_mvp', visual_QA=False)
