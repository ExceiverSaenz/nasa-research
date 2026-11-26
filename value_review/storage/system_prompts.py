"""System prompt files under annotations/system-prompts/ (42-settings-interface-contract.md, OP-T02; ADR-019).

One folder per kind (``extraction``, ``normalization``) holding its versions ``v<n>.json``, each written once and never
changed or deleted (BR-T06). A number is never reused, even when the newest file cannot be read. A file that cannot be
read is reported, never repaired or deleted.
"""
import json
import os
import re
import shutil
from pathlib import Path

from .. import schemas
from .atomic import StorageError, atomic_write_bytes

KINDS = ('extraction', 'normalization')
VERSION_FILE = re.compile(r'v([1-9][0-9]{0,5})\.json')

# Version 1 of each prompt: the current texts of the canvas Settings board (OQ-T01).
_EXT_RULES = [
    'ask for one row per specimen or test condition;',
    'list every field of the schema, with its unit and description;',
    'ask for each value exactly as written in the paper, with its symbols (for example 710 ± 25), without converting units or rounding;',
    'ask for the page where each value was found;',
    'say to leave a field empty when the paper does not give it, and never to guess;',
    'treat the schema as a guide: if the paper reports something relevant that the schema does not list, say so in a note and do not drop it.',
]
_NORM_RULES = [
    'follow the rule of the case that fits the value, and never invent a rule;',
    'keep the symbols and the uncertainty as the rule says (for example 710 ± 25 becomes the value 710 and the uncertainty 25);',
    'say when you converted a unit, and how;',
    'if no case fits, or the value is ambiguous, do not guess: return it unchanged and flag it for the expert;',
    'never change the reviewed value itself.',
]
SEED_TEXT = {
    'extraction': (
        'You write extraction prompts for a tool that reads scientific papers and returns tables of values.\n\n'
        'You are given a schema: groups of fields, each with a name, an optional unit, type, allowed values and description. '
        'Write one prompt for another model that will read a paper and fill that schema.\n\n'
        'The prompt you write must:\n' + '\n'.join(f'- {r}' for r in _EXT_RULES) +
        '\n\nWrite in plain language. Do not add anything the expert did not ask for.'),
    'normalization': (
        'You apply a normalization rule, written by an expert, to values that an expert has already reviewed in tensile test papers.\n\n'
        'You are given the feature (name, type, target unit, allowed values), the expert’s rule for each case, the context '
        'and the examples, and one reviewed value.\n\n'
        'Your answer must:\n' + '\n'.join(f'- {r}' for r in _NORM_RULES)),
}


def _dumps(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


class SystemPromptStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    def kind_dir(self, kind):
        return self.folder / kind

    def version_path(self, kind, n):
        return self.kind_dir(kind) / f'v{int(n)}.json'

    def exists(self, kind):
        return self.kind_dir(kind).is_dir()

    def version_numbers(self, kind):
        """Numbers of the version files present, newest first."""
        folder = self.kind_dir(kind)
        if not folder.is_dir():
            return []
        return sorted((int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.fullmatch(p.name))), reverse=True)

    def read_version(self, kind, n):
        """(data, problem): data is None when the file is missing or does not match its JSON Schema."""
        path = self.version_path(kind, n)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError) as error:
            return None, f'{path.name}: {type(error).__name__}'
        errs = schemas.errors('system-prompt-version', data)
        if not errs and (data['kind'] != kind or data['n'] != n):
            errs = [('/n', 'does not match the file name')]
        return (None, f'{kind}/{path.name}: {errs[0][0]} {errs[0][1]}') if errs else (data, None)

    def current(self, kind):
        """(current number, newest readable version or None, next free number, problems)."""
        problems, latest = [], None
        nums = self.version_numbers(kind)
        for n in nums:
            data, problem = self.read_version(kind, n)
            if data is not None:
                latest = data
                break
            problems.append(problem)
        return (latest['n'] if latest else 0), latest, (nums[0] + 1 if nums else 1), problems

    def write_version(self, kind, data):
        """Write v<n> once; an existing file is never replaced."""
        path = self.version_path(kind, data['n'])
        if path.exists():
            raise StorageError(f'{path.name} already exists')
        atomic_write_bytes(path, _dumps(data))

    def seed(self, kind, at):
        """Make v1 from the canvas text once, when the kind's folder does not exist. Built in a temporary folder and
        moved into place, so a failure never leaves a half-made folder."""
        if self.exists(kind):
            return
        temp = self.folder / f'.{kind}.seeding'
        shutil.rmtree(temp, ignore_errors=True)
        version = {'schema': 'value-review-system-prompt-version/1', 'kind': kind, 'n': 1, 'saved_at': at,
                   'saved_by': 'value_review', 'note': 'Text of the canvas', 'text': SEED_TEXT[kind]}
        atomic_write_bytes(temp / 'v1.json', _dumps(version))
        try:
            os.replace(temp, self.kind_dir(kind))
        except OSError as error:
            shutil.rmtree(temp, ignore_errors=True)
            if not self.exists(kind):   # another request may have seeded it first
                raise StorageError(f'Could not create the {kind} System prompt: {error}') from error
