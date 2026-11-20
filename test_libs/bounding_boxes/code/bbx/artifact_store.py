"""Local content-addressed storage; result paths remain hardlink references.

Shared artifacts must be replaced atomically, never edited in place. No model,
PDF renderer, network, symlink, or filesystem-permission change is used here.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
import zipfile

from .contracts import sha256, write_json
from .layout import project_root, resolve_path


def contained(root, path):
    root = Path(root).resolve()
    path = Path(path).absolute()
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved != path:
        raise ValueError('Artifact path escapes root or uses a symbolic link')
    return path


def candidate(path):
    return path.suffix.lower() in ('.png', '.jpg', '.jpeg') or path.name == 'viewer.json'


def plan_duplicates(root):
    root = Path(root).resolve()
    sizes = defaultdict(list)
    for path in sorted(resolve_path(root / 'results', root=root).rglob('*')):
        if path.is_file() and candidate(path):
            contained(root, path)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('Artifact must be a regular file')
            sizes[path.stat().st_size].append(path)
    groups = []
    for size, paths in sizes.items():
        if len(paths) < 2:
            continue
        digests = defaultdict(list)
        for path in paths:
            digests[sha256(path)].append(path)
        for digest, aliases in digests.items():
            physical = {(p.stat().st_dev, p.stat().st_ino) for p in aliases}
            if len(physical) > 1:
                groups.append(dict(sha256=digest, bytes=size,
                    paths=[p.relative_to(root).as_posix() for p in aliases],
                    saved_bytes=size * (len(physical) - 1)))
    return dict(schema='bounding-box-artifact-storage/1', groups=groups,
                saved_bytes=sum(g['saved_bytes'] for g in groups))


def validate_plan(root, plan):
    seen = set()
    if plan.get('schema') != 'bounding-box-artifact-storage/1':
        raise ValueError('Unknown storage manifest')
    for group in plan['groups']:
        digest = group['sha256']
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid content identity')
        for rel in group['paths']:
            p = contained(root, resolve_path(Path(root) / rel, root=root))
            if Path(rel).is_absolute() or not p.is_relative_to(resolve_path(Path(root) / 'results', root=root)) or not candidate(p) or p in seen:
                raise ValueError('Invalid or repeated result alias')
            seen.add(p)


class ArtifactStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.cache = self.root / 'runtime' / 'artifact-cache'
        self.index = self.cache / 'migration.json'

    def object_path(self, digest):
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid content identity')
        return contained(self.root, self.cache / 'objects' / digest[:2] / digest)

    def share(self, source, destination):
        source = contained(self.root, source)
        destination = contained(self.root, destination)
        digest = sha256(source)
        obj = self.object_path(digest)
        obj.parent.mkdir(parents=True, exist_ok=True)
        if obj.exists():
            if sha256(obj) != digest:
                raise ValueError('Corrupt cached object')
        else:
            try:
                os.link(source, obj)
            except FileExistsError:
                pass  # Another writer may have interned the same digest.
            if sha256(obj) != digest:
                raise ValueError('Source changed while interning artifact')
        if sha256(source) != digest:
            raise ValueError('Source changed before linking artifact')
        # Builders only replace their destination; inputs stay read-only. The
        # explicit migration passes every backed-up original path as destination.
        for alias in (destination,):
            if alias.exists() and os.path.samefile(obj, alias):
                continue
            alias.parent.mkdir(parents=True, exist_ok=True)
            temp = alias.with_name('.' + alias.name + '.' + uuid.uuid4().hex + '.link')
            try:
                os.link(obj, temp)
                os.replace(temp, alias)
            finally:
                temp.unlink(missing_ok=True)
        return obj

    def migrate(self, backup):
        prior = None
        if self.index.exists():
            prior = json.loads(self.index.read_text(encoding='utf-8'))
            validate_plan(self.root, prior)
            if prior.get('state') not in ('verified', 'restored'):
                raise ValueError('Incomplete migration; restore its backup before retrying')
            current = []
            for group in prior['groups']:
                obj = self.object_path(group['sha256'])
                if not obj.exists() and prior.get('state') == 'restored':
                    continue  # The recovered transaction may not have reached this object.
                if not obj.exists() or sha256(obj) != group['sha256']:
                    raise ValueError('Corrupt cached object')
                paths = [rel for rel in group['paths'] if (resolve_path(self.root / rel, root=self.root)).is_file()
                         and os.path.samefile(obj, resolve_path(self.root / rel, root=self.root))]
                if paths:
                    current.append({**group, 'paths': paths})
            prior = {**prior, 'groups': current, 'state': 'verified'}
        plan = plan_duplicates(self.root)
        if not plan['groups']:
            if prior is not None:
                write_json(self.index, prior)
                self.verify()
            return dict(saved_bytes=0, groups=0)
        validate_plan(self.root, plan)
        backup = Path(backup).absolute()
        if backup.exists():
            raise FileExistsError('Choose a new backup path; existing backups are preserved')
        if backup.is_relative_to(resolve_path(self.root / 'results', root=self.root)) or backup.is_relative_to(self.cache):
            raise ValueError('Backup must be separate from result aliases and cache')
        # Validate every input/cache object and hardlink support before replacing inputs.
        for group in plan['groups']:
            for rel in group['paths']:
                if sha256(resolve_path(self.root / rel, root=self.root)) != group['sha256']:
                    raise ValueError('Input changed before migration')
            obj = self.object_path(group['sha256'])
            if obj.exists() and sha256(obj) != group['sha256']:
                raise ValueError('Corrupt cached object')
        contained(self.root, self.cache).mkdir(parents=True, exist_ok=True)
        probe = self.cache / (uuid.uuid4().hex + '.probe')
        try:
            os.link(resolve_path(self.root / plan['groups'][0]['paths'][0], root=self.root), probe)
        finally:
            probe.unlink(missing_ok=True)
        backup.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(backup, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(plan, indent=2))
            for group in plan['groups']:
                archive.write(resolve_path(self.root / group['paths'][0], root=self.root), 'objects/' + group['sha256'])
        # Reread the independent backup before replacing even one original path.
        with zipfile.ZipFile(backup) as archive:
            for group in plan['groups']:
                if hashlib.sha256(archive.read('objects/' + group['sha256'])).hexdigest() != group['sha256']:
                    raise ValueError('Backup integrity failure')
        if prior is not None:
            combined = {g['sha256']: {**g, 'paths': list(g['paths'])} for g in prior['groups']}
            for group in plan['groups']:
                old_paths = combined.get(group['sha256'], {}).get('paths', [])
                combined[group['sha256']] = {**group, 'paths': sorted(set(group['paths'] + old_paths))}
            journal = {**plan, 'groups': list(combined.values())}
        else:
            journal = plan.copy()
        journal.update(state='prepared', backup=str(backup))
        write_json(self.index, journal)
        for group in plan['groups']:
            source = resolve_path(self.root / group['paths'][0], root=self.root)
            for rel in group['paths']:
                path = resolve_path(self.root / rel, root=self.root)
                if sha256(path) != group['sha256']:
                    raise ValueError('Input changed during migration; backup retained')
                self.share(source, path)
        result = self.verify()
        journal.update(state='verified', verification=result)
        write_json(self.index, journal)
        return dict(saved_bytes=plan['saved_bytes'], groups=len(plan['groups']),
                    backup_bytes=backup.stat().st_size, **result)

    def verify(self):
        plan = json.loads(self.index.read_text(encoding='utf-8'))
        validate_plan(self.root, plan)
        count = 0
        for group in plan['groups']:
            obj = self.object_path(group['sha256'])
            if sha256(obj) != group['sha256']:
                raise ValueError('Corrupt cached object')
            for rel in group['paths']:
                path = resolve_path(self.root / rel, root=self.root)
                if sha256(path) != group['sha256'] or not os.path.samefile(obj, path):
                    raise ValueError('Alias content or physical identity changed: ' + rel)
                count += 1
        return dict(aliases=count, objects=len(plan['groups']), hashes_preserved=True)


def restore_backup(root, backup):
    root = Path(root).resolve()
    with zipfile.ZipFile(backup) as archive:
        plan = json.loads(archive.read('manifest.json'))
        validate_plan(root, plan)
        # Validate all entries and existing aliases before overwriting anything.
        for group in plan['groups']:
            if hashlib.sha256(archive.read('objects/' + group['sha256'])).hexdigest() != group['sha256']:
                raise ValueError('Corrupt backup')
            for rel in group['paths']:
                path = resolve_path(root / rel, root=root)
                if path.exists() and sha256(path) != group['sha256']:
                    raise ValueError('Alias changed since backup: ' + rel)
        for group in plan['groups']:
            content = archive.read('objects/' + group['sha256'])
            for rel in group['paths']:
                path = resolve_path(root / rel, root=root)
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.restore')
                try:
                    temp.write_bytes(content)
                    os.replace(temp, path)
                finally:
                    temp.unlink(missing_ok=True)
    index = ArtifactStore(root).index
    if index.exists():
        journal = json.loads(index.read_text(encoding='utf-8'))
        if Path(journal.get('backup', '')).resolve() == Path(backup).resolve():
            journal.update(state='restored', restored_backup=str(Path(backup).resolve()))
            write_json(index, journal)
    return dict(restored_aliases=sum(len(g['paths']) for g in plan['groups']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'apply', 'verify', 'restore'))
    parser.add_argument('--root', type=Path, default=project_root(__file__))
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    store = ArtifactStore(args.root)
    if args.action in ('apply', 'restore') and not args.backup:
        parser.error('apply/restore requires --backup')
    if args.action == 'inspect':
        result = plan_duplicates(args.root)
    elif args.action == 'apply':
        result = store.migrate(args.backup)
    elif args.action == 'restore':
        result = restore_backup(args.root, args.backup)
    else:
        result = store.verify()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
