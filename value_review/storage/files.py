"""Files under annotations/: drafts, versions and settings (contract, "Files").

This module has the read side and settings; drafts and version writes are added in step 4.
A file that cannot be read (malformed JSON, wrong schema) is reported, never repaired or deleted.
"""
import json
import re
from pathlib import Path

from .. import schemas
from .atomic import atomic_write_bytes

VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')
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
    def _read(self, path, schema):
        """(data, problem): data is None when the file is missing or unusable."""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{path.name}: {type(error).__name__}'
        errs = schemas.errors(schema, data)
        if errs:
            return None, f'{path.name}: {errs[0][0]} {errs[0][1]}'
        return data, None

    def version_numbers(self, paper):
        """Numbers of the version files present, newest first."""
        folder = self.versions_dir(paper)
        if not folder.is_dir():
            return []
        nums = [int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))]
        return sorted(nums, reverse=True)

    def read_version(self, paper, n):
        return self._read(self.version_path(paper, n), 'version')

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

    # --- settings (OP-10) ------------------------------------------------------
    def settings(self):
        try:
            stored = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            stored = {}
        out = dict(SETTINGS_DEFAULTS)
        out.update({k: v for k, v in stored.items() if k in SETTINGS_DEFAULTS})
        return out

    def save_settings(self, values):
        atomic_write_bytes(self.settings_path, _dumps(values))
