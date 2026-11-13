"""Settings (OP-13), read side: the stored file, or the defaults when there is none. Writing comes with the write endpoints."""
import hashlib
import json

from ..domain.catalogs import DEFAULT_SETTINGS

SCHEMA = 'parsing-validator-settings/1'


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
