"""Shape validation of the review and draft files (not the business decision rules of OP-07)."""
from jsonschema import Draft202012Validator

PAPER = {'type': 'string', 'pattern': '^[0-9]+$'}
STATE = {
    'type': 'object',
    'required': ['reviewed', 'next_new_id', 'pages'],
    'properties': {
        'reviewed': {'type': 'object', 'required': ['marked', 'marked_at']},
        'next_new_id': {'type': 'integer', 'minimum': 1},
        'pages': {'type': 'object'},
    },
}
REVIEW = {
    'type': 'object',
    'required': ['schema', 'paper', 'revision', 'saved_at', 'source', 'reviewed', 'next_new_id', 'pages'],
    'properties': {
        'schema': {'const': 'parsing-validator-review/1'},
        'paper': PAPER,
        'revision': {'type': 'integer', 'minimum': 1},
        'saved_at': {'type': 'string'},
        'source': {'type': 'object', 'required': ['original_file', 'original_sha256']},
        **STATE['properties'],
    },
}
DRAFT = {
    'type': 'object',
    'required': ['schema', 'paper', 'base_revision', 'saved_at', 'trigger', 'state', 'versions'],
    'properties': {
        'schema': {'const': 'parsing-validator-draft/1'},
        'paper': PAPER,
        'base_revision': {'type': 'integer', 'minimum': 0},
        'saved_at': {'type': 'string'},
        'trigger': {'enum': ['manual', 'auto', 'pagehide']},
        'state': STATE,
        'versions': {
            'type': 'array',
            'items': {'type': 'object', 'required': ['label', 'at', 'undo', 'sha256'],
                      'properties': {'label': {'type': 'string'}, 'at': {'type': 'string'},
                                     'undo': {'type': 'array'}, 'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}}},
        },
    },
}

_VALIDATORS = {'review': Draft202012Validator(REVIEW), 'draft': Draft202012Validator(DRAFT),
               'state': Draft202012Validator(STATE), 'paper': Draft202012Validator(PAPER)}


def problems(kind, value):
    """List of ``pointer: message`` strings; empty when the shape is valid."""
    return [f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message[:120]}" for e in _VALIDATORS[kind].iter_errors(value)]
