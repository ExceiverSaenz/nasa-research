"""Normalize's files for one extraction, in <data>/normalize/<source>/ (92-normalize-interface-contract.md; ADR-035).

- ``rules/<field_id>/v<n>.json``: rule versions, each written once; numbers are never reused (BR-N04).
- ``values/<field_id>.json``: the normalized values of a feature and their validation, replaced atomically.
- ``apply.json``: the state of the current apply (features, batches), as Extraction's papers.json.

A file that cannot be read is reported, never repaired. Review's files are never touched from here.
"""
import json
import re
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes, reason

VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')
FIELD_ID = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}')


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


def safe_field(field_id):
    if not FIELD_ID.fullmatch(field_id or '') or '..' in field_id:
        raise StorageError('Not a field id')
    return field_id


class NormalizeStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    # --- rules ------------------------------------------------------------------------
    def rule_dir(self, field_id):
        return self.folder / 'rules' / safe_field(field_id)

    def rule_path(self, field_id, n):
        return self.rule_dir(field_id) / f'v{int(n)}.json'

    def rule_numbers(self, field_id):
        folder = self.rule_dir(field_id)
        if not folder.is_dir():
            return []
        return sorted((int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))), reverse=True)

    def ruled_fields(self):
        root = self.folder / 'rules'
        try:
            return sorted(p.name for p in root.iterdir() if p.is_dir() and FIELD_ID.fullmatch(p.name))
        except OSError:
            return []

    def read_rule(self, field_id, n):
        path = self.rule_path(field_id, n)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{field_id}/{path.name}: {type(error).__name__}'
        errs = schemas.errors('normalize-rule', data)
        if not errs and (data['n'] != n or data['field_id'] != field_id):
            errs = [('/n', 'does not match the file name')]
        return (None, f'{field_id}/{path.name}: {errs[0][0]} {errs[0][1]}') if errs else (data, None)

    def current_rule(self, field_id):
        """(current number, newest readable version or None, next free number, problems)."""
        nums, problems = self.rule_numbers(field_id), []
        for n in nums:
            data, problem = self.read_rule(field_id, n)
            if data is not None:
                return n, data, nums[0] + 1, problems
            problems.append(problem)
        return 0, None, (nums[0] + 1 if nums else 1), problems

    def write_rule(self, data):
        path = self.rule_path(data['field_id'], data['n'])
        if path.exists():
            raise StorageError(f'{path.name} already exists')
        atomic_write_bytes(path, _dumps(data))

    def prune_rules(self, field_id, keep):
        for n in self.rule_numbers(field_id)[keep:]:
            try:
                self.rule_path(field_id, n).unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise StorageError(f'Could not delete v{n}.json: {reason(error)}') from error

    # --- normalized values ------------------------------------------------------------
    def values_path(self, field_id):
        return self.folder / 'values' / f'{safe_field(field_id)}.json'

    def read_values(self, field_id):
        """({value id: value}, problem)."""
        path = self.values_path(field_id)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}, None
        except (OSError, ValueError) as error:
            return {}, f'values/{path.name}: {type(error).__name__}'
        errs = schemas.errors('normalized-values', data)
        if errs:
            return {}, f'values/{path.name}: {errs[0][0]} {errs[0][1]}'
        return data['values'], None

    def write_values(self, field_id, values):
        atomic_write_bytes(self.values_path(field_id), _dumps({'schema': 'value-review-normalized-values/1', 'field_id': field_id, 'values': values}))

    # --- the apply's state ------------------------------------------------------------
    def apply_path(self):
        return self.folder / 'apply.json'

    def read_apply(self):
        try:
            data = json.loads(self.apply_path().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        return data if isinstance(data, dict) and isinstance(data.get('features'), dict) else {'status': 'idle', 'features': {}}

    def write_apply(self, state):
        atomic_write_bytes(self.apply_path(), _dumps(state))
