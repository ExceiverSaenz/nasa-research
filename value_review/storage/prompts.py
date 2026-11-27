"""A run's prompt versions in <data>/extraction/runs/<id>/prompt/v<n>.json (OP-X03; BR-X02).

Each version is written once; numbers are never reused, even after the oldest are deleted beyond the 20 kept. A file that
cannot be read is reported, never repaired.
"""
import json
import re
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes, reason

VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')
KEEP = 20


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


class PromptStore:
    def __init__(self, run_dir):
        self.folder = Path(run_dir) / 'prompt'

    def path(self, n):
        return self.folder / f'v{int(n)}.json'

    def version_numbers(self):
        if not self.folder.is_dir():
            return []
        return sorted((int(m.group(1)) for p in self.folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))), reverse=True)

    def read_version(self, n):
        path = self.path(n)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{path.name}: {type(error).__name__}'
        errs = schemas.errors('prompt-version', data)
        if not errs and data['n'] != n:
            errs = [('/n', 'does not match the file name')]
        return (None, f'{path.name}: {errs[0][0]} {errs[0][1]}') if errs else (data, None)

    def current(self):
        """(current number, newest readable version or None, next free number, problems)."""
        nums, problems = self.version_numbers(), []
        for n in nums:
            data, problem = self.read_version(n)
            if data is not None:
                return n, data, nums[0] + 1, problems
            problems.append(problem)
        return 0, None, (nums[0] + 1 if nums else 1), problems

    def write_version(self, data):
        path = self.path(data['n'])
        if path.exists():
            raise StorageError(f'{path.name} already exists')
        atomic_write_bytes(path, _dumps(data))

    def prune(self, keep=KEEP):
        for n in self.version_numbers()[keep:]:
            try:
                self.path(n).unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise StorageError(f'Could not delete v{n}.json: {reason(error)}') from error
