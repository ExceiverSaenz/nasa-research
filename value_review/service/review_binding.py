"""Which schema version an extraction in Review is bound to (BR-R01, BR-R09; ADR-030).

A results folder written by Extraction holds ``run.json`` with the run's ``schema_ref`` (ADR-028); every other folder
(folder pairs, the LLM run made before Extraction) is bound to the seeded "Tensile properties" v1, whose field ids are
the old extraction guide's. Only files are read.
"""
import json
from pathlib import Path

from .. import schemas
from ..domain.review_schema import fallback_fields, fields_of
from ..ingest.seed_schema import SEED_ID

MANIFEST = 'run.json'


def _manifest_ref(run_dir):
    """(ref, problem): the run's schema_ref and name, or (None, None) when the folder has no run.json."""
    path = Path(run_dir) / MANIFEST
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as error:
        return None, f'{MANIFEST} cannot be read ({type(error).__name__})'
    if schemas.errors('run-manifest', data):
        return None, f'{MANIFEST} does not have the expected shape'
    return {'id': data['schema_ref']['id'], 'version': data['schema_ref']['version'], 'name': data['schema_name']}, None


def bind(run_dir, schema_store, seed):
    """``{ref, content, problem}`` for an extraction's results folder.

    ``ref`` is ``{id, version, name}`` when the schema version can be read, else None; ``content`` is that version's
    content; ``problem`` is ``{code, message}`` or None. ``seed()`` makes the seeded schema when it was never made."""
    wanted, problem = _manifest_ref(run_dir)
    out = {'ref': None, 'content': None, 'problem': None}
    if wanted is None:
        wanted = {'id': SEED_ID, 'version': 1, 'name': None}
        if problem:
            out['problem'] = {'code': 'run_manifest_unreadable', 'message': f'{problem}; the papers use Tensile properties v1.'}
    seed()
    meta, _ = schema_store.read_meta(wanted['id'])
    version, _ = schema_store.read_version(wanted['id'], wanted['version'])
    name = (meta or {}).get('name') or wanted['name'] or wanted['id']
    if version is None:
        out['problem'] = {'code': 'schema_missing',
                          'message': f'Schema {name} v{wanted["version"]} is no longer available; the columns of the model output are used.',
                          'schema_ref': {'id': wanted['id'], 'version': wanted['version']}}
        return out
    out['ref'] = {'id': wanted['id'], 'version': wanted['version'], 'name': name}
    out['content'] = version['content']
    return out


def fields_for(binding, original):
    """The fields Review shows for one paper: the bound version's, or the original's own columns (BR-R09)."""
    return fields_of(binding['content']) if binding['content'] is not None else fallback_fields(original)
