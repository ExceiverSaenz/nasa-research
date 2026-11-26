"""Schema files under annotations/schemas/ (22-schema-interface-contract.md, "Files"; ADR-010).

One folder per schema: ``schema.json`` (its name, not versioned), at most one ``draft.json`` and the versions
``versions/v<n>.json``, each written once. A deleted schema's folder is moved to ``.trash/``; nothing is erased and its
id is never given to another schema (BR-S09). A file that cannot be read is reported, never repaired or deleted.
"""
import json
import os
import re
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes, reason

SCHEMA_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')
TRASH = '.trash'


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


def empty_content():
    return {'schema': 'value-review-schema/1', 'description': '', 'groups': []}


def slug(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:56].strip('-')
    return s or 'schema'


class SchemaStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    # --- paths -------------------------------------------------------------------
    def schema_dir(self, sid):
        return self.folder / sid

    def meta_path(self, sid):
        return self.schema_dir(sid) / 'schema.json'

    def draft_path(self, sid):
        return self.schema_dir(sid) / 'draft.json'

    def versions_dir(self, sid):
        return self.schema_dir(sid) / 'versions'

    def version_path(self, sid, n):
        return self.versions_dir(sid) / f'v{int(n)}.json'

    def exists(self):
        """True once the schemas folder exists (the seed has run or a schema was made)."""
        return self.folder.is_dir()

    # --- ids ---------------------------------------------------------------------
    def ids(self):
        """Ids of the schemas in the list (folders holding a schema.json), sorted."""
        if not self.folder.is_dir():
            return []
        return sorted(p.name for p in self.folder.iterdir()
                      if p.is_dir() and SCHEMA_ID.fullmatch(p.name) and (p / 'schema.json').exists())

    def taken(self):
        """Every id in use or ever used: the folders present and the ones in the trash."""
        out = set()
        if self.folder.is_dir():
            out |= {p.name for p in self.folder.iterdir() if p.is_dir() and p.name != TRASH}
            trash = self.folder / TRASH
            if trash.is_dir():
                out |= {p.name.split('.', 1)[0] for p in trash.iterdir()}
        return out

    def new_id(self, name):
        base, taken = slug(name), self.taken()
        sid, k = base, 2
        while sid in taken:
            sid, k = f'{base[:58]}-{k}', k + 1
        return sid

    # --- reading -------------------------------------------------------------------
    @staticmethod
    def _read(path, name):
        """(data, problem): data is None when the file is missing or unusable."""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{path.name}: {type(error).__name__}'
        errs = schemas.errors(name, data)
        return (None, f'{path.name}: {errs[0][0]} {errs[0][1]}') if errs else (data, None)

    def read_meta(self, sid):
        return self._read(self.meta_path(sid), 'schema-meta')

    def read_draft(self, sid):
        return self._read(self.draft_path(sid), 'schema-draft')

    def read_version(self, sid, n):
        return self._read(self.version_path(sid, n), 'schema-version')

    def version_numbers(self, sid):
        """Numbers of the version files present, newest first."""
        folder = self.versions_dir(sid)
        if not folder.is_dir():
            return []
        return sorted((int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))), reverse=True)

    def latest(self, sid):
        """(newest readable version or None, problems)."""
        problems = []
        for n in self.version_numbers(sid):
            data, problem = self.read_version(sid, n)
            if data is not None:
                return data, problems
            problems.append(problem)
        return None, problems

    def current(self, sid):
        """(current version number, newest readable version or None, next free number, problems).

        The next number is one past every file present, so a number is never reused (BR-S05)."""
        latest, problems = self.latest(sid)
        nums = self.version_numbers(sid)
        return (latest['n'] if latest else 0), latest, (nums[0] + 1 if nums else 1), problems

    # --- writing -------------------------------------------------------------------
    def write_meta(self, sid, meta):
        atomic_write_bytes(self.meta_path(sid), _dumps(meta))

    def write_draft(self, sid, draft):
        atomic_write_bytes(self.draft_path(sid), _dumps(draft))

    def delete_draft(self, sid):
        try:
            self.draft_path(sid).unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            raise StorageError(f'Could not delete the draft: {reason(error)}') from error

    def write_version(self, sid, data):
        """Write v<n> once; an existing file is never replaced (versions are immutable)."""
        path = self.version_path(sid, data['n'])
        if path.exists():
            raise StorageError(f'{path.name} already exists')
        atomic_write_bytes(path, _dumps(data))

    def prune(self, sid, keep):
        """Delete the oldest version files beyond the ``keep`` newest (BR-S06). Returns the numbers deleted."""
        deleted = []
        for n in self.version_numbers(sid)[keep:]:
            try:
                self.version_path(sid, n).unlink()
                deleted.append(n)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise StorageError(f'Could not delete v{n}.json: {reason(error)}') from error
        return deleted

    def trash(self, sid, stamp):
        """Move the schema's folder to .trash/<id>.<stamp>/ (BR-S09). Returns the new folder."""
        target = self.folder / TRASH / f'{sid}.{stamp}'
        k = 2
        while target.exists():
            target = self.folder / TRASH / f'{sid}.{stamp}-{k}'
            k += 1
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(self.schema_dir(sid), target)
        except OSError as error:
            raise StorageError(f'Could not move the schema to the trash: {reason(error)}') from error
        return target
