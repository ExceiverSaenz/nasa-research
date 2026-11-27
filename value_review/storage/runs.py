"""Extraction runs in <data>/extraction/runs/<id>/ (72-extraction-interface-contract.md, OP-X01; ADR-025).

One folder per run: ``run.json`` (its settings and status) and, from later steps, its prompt versions and the state of
each paper. A run's results are written to the workspace (``results/<set>/<folder>/``), never here. A file that cannot
be read is reported, never repaired or deleted.
"""
import json
import re
import secrets as _random
import shutil
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes, reason

RUN_ID = re.compile(r'r_[0-9a-f]{8}')


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


class RunStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    def run_dir(self, rid):
        return self.folder / rid

    def ids(self):
        if not self.folder.is_dir():
            return []
        return sorted(p.name for p in self.folder.iterdir() if p.is_dir() and RUN_ID.fullmatch(p.name))

    def read(self, rid):
        """(run, problem): run is None when missing or not matching run.schema.json."""
        if not RUN_ID.fullmatch(rid):
            return None, None
        path = self.run_dir(rid) / 'run.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{rid}/run.json: {type(error).__name__}'
        errs = schemas.errors('run', data)
        if not errs and data['id'] != rid:
            errs = [('/id', 'does not match the folder')]
        return (None, f'{rid}/run.json: {errs[0][0]} {errs[0][1]}') if errs else (data, None)

    def write(self, run):
        errs = schemas.errors('run', run)
        if errs:   # a bug, not a client error
            raise RuntimeError(f'run would not validate: {errs[:3]}')
        atomic_write_bytes(self.run_dir(run['id']) / 'run.json', _dumps(run))

    def new_id(self):
        while True:
            rid = 'r_' + _random.token_hex(4)
            if not self.run_dir(rid).exists():
                return rid

    def delete(self, rid):
        try:
            shutil.rmtree(self.run_dir(rid))
        except FileNotFoundError:
            pass
        except OSError as error:
            raise StorageError(f'Could not delete the run: {reason(error)}') from error
