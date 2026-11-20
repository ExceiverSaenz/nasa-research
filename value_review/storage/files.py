"""Files under annotations/: drafts, versions and settings (contract, "Files").

Reading, settings, draft writes, version writes and pruning.
A file that cannot be read (malformed JSON, wrong schema) is reported, never repaired or deleted.
"""
import json
import os
import re
import threading
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes, reason

VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')
_CACHE = {}            # (path, header) -> ((size, mtime_ns, schema), (data, problem)), see AnnotationStore._read
_CACHE_MAX = 2000
_CACHE_LOCK = threading.Lock()
_EMPTY_STATE = {'schema': 'value-review-state/1', 'decisions': {}, 'column_moves': {}, 'record_moves': {}, 'record_edits': {},
                'added_records': [], 'added_values': [], 'boxes': {}}
SETTINGS_DEFAULTS = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5}


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


class AnnotationStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    # --- paths ---------------------------------------------------------------
    def draft_path(self, paper):
        return self.folder / 'drafts' / f'{paper}.draft.json'

    def versions_dir(self, paper):
        return self.folder / 'versions' / str(paper)

    def version_path(self, paper, n):
        return self.versions_dir(paper) / f'v{int(n)}.json'

    @property
    def settings_path(self):
        return self.folder / 'settings.json'

    @property
    def lock_path(self):
        return self.folder / 'value-review.lock'

    # --- reading ---------------------------------------------------------------
    def _read(self, path, schema, header=False):
        """(data, problem): data is None when the file is missing or unusable.

        A file is parsed and validated once per process and size/modification time (13-performance-report.md, B-2):
        versions never change, and a draft or a damaged file that does change gets a new size or time and is read again.
        Callers must not modify the returned data, which is shared.

        ``header`` checks only a version's own fields (number, time, author, note, source, counts), not its state and
        values, and returns just those fields: enough to list versions without validating every full snapshot."""
        try:
            st = path.stat()
        except FileNotFoundError:
            return None, None
        except OSError as error:
            return None, f'{path.name}: {type(error).__name__}'
        key, stamp = (str(path), header), (st.st_size, st.st_mtime_ns, schema)
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{path.name}: {type(error).__name__}'
        if header:
            if not isinstance(data, dict):
                return None, f'{path.name}: not an object'
            data = {k: v for k, v in data.items() if k not in ('state', 'values')}
            errs = schemas.errors(schema, {**data, 'state': _EMPTY_STATE, 'values': []})
        else:
            errs = schemas.errors(schema, data)
        result = (None, f'{path.name}: {errs[0][0]} {errs[0][1]}') if errs else (data, None)
        with _CACHE_LOCK:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.pop(next(iter(_CACHE)))   # oldest entry first
            _CACHE[key] = (stamp, result)
        return result

    def version_numbers(self, paper):
        """Numbers of the version files present, newest first."""
        folder = self.versions_dir(paper)
        if not folder.is_dir():
            return []
        nums = [int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))]
        return sorted(nums, reverse=True)

    def read_version(self, paper, n):
        return self._read(self.version_path(paper, n), 'version')

    def version_header(self, paper, n):
        """(header, problem) of version n: its fields without state and values, checked against the version schema."""
        return self._read(self.version_path(paper, n), 'version', header=True)

    def latest(self, paper):
        """(version or None, problems): the newest readable version; unreadable ones are reported."""
        problems = []
        for n in self.version_numbers(paper):
            data, problem = self.read_version(paper, n)
            if data is not None:
                return data, problems
            problems.append(problem)
        return None, problems

    def read_draft(self, paper):
        return self._read(self.draft_path(paper), 'draft')

    def current(self, paper):
        """(current version number, newest readable version or None, next free number, problems).

        The current version is the newest readable one; the next number is one past every file present,
        so a number is never reused even when the newest file is unreadable (BR-03)."""
        latest, problems = self.latest(paper)
        nums = self.version_numbers(paper)
        return (latest['n'] if latest else 0), latest, (nums[0] + 1 if nums else 1), problems

    # --- writing versions (OP-05) -------------------------------------------------
    def write_version(self, paper, data):
        """Write v<n> once; an existing file is never replaced (versions are immutable)."""
        path = self.version_path(paper, data['n'])
        if path.exists():
            raise StorageError(f'{path.name} already exists')
        atomic_write_bytes(path, _dumps(data))

    def prune(self, paper, keep):
        """Delete the oldest version files beyond the ``keep`` newest. Returns the numbers deleted."""
        deleted = []
        for n in self.version_numbers(paper)[keep:]:
            try:
                self.version_path(paper, n).unlink()
                deleted.append(n)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise StorageError(f'Could not delete v{n}.json: {reason(error)}') from error
        return deleted

    def write_draft(self, paper, data):
        """Replace the paper's draft (at most one per paper; a draft is not a version, BR-02)."""
        atomic_write_bytes(self.draft_path(paper), _dumps(data))

    def delete_draft(self, paper):
        try:
            self.draft_path(paper).unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            raise StorageError(f'Could not delete the draft: {reason(error)}') from error

    # --- settings (OP-10) ------------------------------------------------------
    def stored_settings(self):
        """The settings file as saved ({} when missing or unreadable)."""
        try:
            stored = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        return stored if isinstance(stored, dict) else {}

    def settings(self):
        """Reviewer settings over the defaults (the folder pairs are read by the service). The default reviewer name
        comes from ``VALUE_REVIEW_REVIEWER`` when set (each tester's container sets it); a name saved in Settings wins."""
        stored = self.stored_settings()
        out = dict(SETTINGS_DEFAULTS)
        name = os.environ.get('VALUE_REVIEW_REVIEWER', '').strip()
        if name:
            out['reviewer_name'] = name[:80]
        out.update({k: v for k, v in stored.items() if k in out})
        return out

    def save_settings(self, values):
        atomic_write_bytes(self.settings_path, _dumps(values))
