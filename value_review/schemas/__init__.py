"""JSON Schemas of the contract (03-interface-contract.md) and a validator factory with $ref resolution."""
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

FOLDER = Path(__file__).resolve().parent
NAMES = ('state', 'draft', 'version', 'export', 'original',
         'schema-content', 'schema-version', 'schema-draft', 'schema-meta',   # these four: 22-schema-interface-contract.md
         'settings', 'system-prompt-version')   # these two: 42-settings-interface-contract.md


@lru_cache(maxsize=None)
def _registry():
    reg = Registry()
    for name in NAMES:
        schema = json.loads((FOLDER / f'{name}.schema.json').read_text(encoding='utf-8'))
        reg = reg.with_resource(schema['$id'], Resource.from_contents(schema))
    return reg


@lru_cache(maxsize=None)
def validator(name):
    schema = json.loads((FOLDER / f'{name}.schema.json').read_text(encoding='utf-8'))
    return Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker())


def errors(name, instance):
    """List of (json_pointer, message) for an instance; empty when valid."""
    return [('/' + '/'.join(str(p) for p in e.absolute_path), e.message) for e in validator(name).iter_errors(instance)]
