"""Settings (OP-13): the stored file, or the defaults when there is none, and the checks a replacement must pass."""
import hashlib
import json
import os
from pathlib import Path

from ..domain.catalogs import DEFAULT_SETTINGS, OTHER
from ..storage.atomic import atomic_write_bytes

SCHEMA = 'parsing-validator-settings/1'
KINDS = ('text', 'figure', 'table')
PATH_KEYS = ('results', 'pdfs', 'originals', 'annotations')
APPEARANCE_KEYS = ('density', 'text_size', 'palette')


def defaults(config):
    return {
        'schema': SCHEMA,
        'paths': {'results': str(config.collection), 'pdfs': str(config.pdfs), 'originals': str(config.originals),
                  'annotations': str(config.annotations)},
        'tags': [dict(t) for t in DEFAULT_SETTINGS['tags']],
        'error_types': list(DEFAULT_SETTINGS['error_types']),
        'delete_reasons': list(DEFAULT_SETTINGS['delete_reasons']),
        'draft_interval_minutes': 30, 'papers_per_set': 12,
        'appearance': {'density': 'comfortable', 'text_size': 'medium', 'palette': 'default'},
    }


def load(config):
    """``(settings, warning)``: an unreadable or foreign file is reported and the defaults are used, the file untouched."""
    base = defaults(config)
    try:
        raw = config.settings_file.read_bytes()
    except FileNotFoundError:
        return base, None
    except OSError:
        return base, {'code': 'file_invalid', 'file': config.settings_file.name}
    try:
        stored = json.loads(raw)
        if not isinstance(stored, dict) or stored.get('schema') != SCHEMA:
            raise ValueError
    except ValueError:
        return base, {'code': 'file_invalid', 'file': config.settings_file.name}
    return {**base, **stored}, None


def etag(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _names(value):
    ok = isinstance(value, list) and all(isinstance(x, str) and x.strip() and x != OTHER for x in value)
    return ok and len(set(value)) == len(value)


def shape_problems(body):
    """Pointers and messages for everything wrong with the shape of a settings object (empty when it is fine)."""
    bad = []
    if not isinstance(body, dict) or body.get('schema') != SCHEMA:
        return [{'pointer': '/schema', 'message': f'must be {SCHEMA}'}]
    paths = body.get('paths')
    if not (isinstance(paths, dict) and all(isinstance(paths.get(k), str) and paths[k].strip() for k in PATH_KEYS)):
        bad.append({'pointer': '/paths', 'message': 'needs non-empty text for ' + ', '.join(PATH_KEYS)})
    tags = body.get('tags')
    names = [t.get('name') for t in tags] if isinstance(tags, list) and all(isinstance(t, dict) for t in tags or []) else None
    if not (names is not None and tags and all(isinstance(n, str) and n.strip() and n != OTHER for n in names)
            and len(set(names)) == len(names) and all(t.get('kind') in KINDS for t in tags)):
        bad.append({'pointer': '/tags', 'message': f'a non-empty list of unique {{name, kind}} with kind in {", ".join(KINDS)}; '
                                                  f'"{OTHER}" is fixed and not listed'})
    for key in ('error_types', 'delete_reasons'):
        if not _names(body.get(key)):
            bad.append({'pointer': f'/{key}', 'message': f'a list of unique, non-empty names; "{OTHER}" is fixed and not listed'})
    for key, low, high in (('draft_interval_minutes', 1, 1440), ('papers_per_set', 1, 1000)):
        value = body.get(key)
        if not (isinstance(value, int) and not isinstance(value, bool) and low <= value <= high):
            bad.append({'pointer': f'/{key}', 'message': f'an integer from {low} to {high}'})
    appearance = body.get('appearance')
    if not (isinstance(appearance, dict) and all(isinstance(appearance.get(k), str) for k in APPEARANCE_KEYS)):
        bad.append({'pointer': '/appearance', 'message': 'needs text for ' + ', '.join(APPEARANCE_KEYS)})
    return bad


def _inside(child, parent):
    child, parent = Path(os.path.abspath(child)), Path(os.path.abspath(parent))
    return child == parent or parent in child.parents


def path_problems(paths):
    """Checks of OP-13 on the four folders (the collection catalog itself is checked by the caller)."""
    bad = []
    for key in ('results', 'pdfs'):
        folder = Path(paths[key])
        if not (folder.is_dir() and os.access(folder, os.R_OK)):
            bad.append({'pointer': f'/paths/{key}', 'message': 'must be an existing, readable folder'})
    for key in ('originals', 'annotations'):
        for sealed in ('results', 'pdfs'):
            if _inside(paths[key], paths[sealed]) or _inside(paths[sealed], paths[key]):
                bad.append({'pointer': f'/paths/{key}', 'message': f'must not be inside, or contain, the {sealed} folder'})
    if _inside(paths['originals'], paths['annotations']) or _inside(paths['annotations'], paths['originals']):
        bad.append({'pointer': '/paths/annotations', 'message': 'originals and annotations must be separate folders'})
    return bad


def save(config, settings):
    atomic_write_bytes(config.settings_file, json.dumps(settings, ensure_ascii=False, indent=1).encode('utf-8') + b'\n')
