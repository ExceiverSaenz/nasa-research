"""The working copy (state.schema.json): an overlay on the original (ADR-004)."""

SCHEMA = 'value-review-state/1'


def empty_state():
    """The working copy that equals the original: no decisions and no edits."""
    return {'schema': SCHEMA, 'decisions': {}, 'column_moves': {}, 'record_moves': {}, 'record_edits': {},
            'added_records': [], 'added_values': [], 'boxes': {}}


def progress(original, state):
    """(reviewed, total): values with a decision, over the model's values plus the reviewer's added ones."""
    ids = {o['observation_id'] for o in original['observations']}
    ids.update(v['observation_id'] for v in state.get('added_values', []))
    decided = sum(1 for k in state.get('decisions', {}) if k in ids)
    return decided, len(ids)


def status_of(reviewed, total):
    if total and reviewed >= total:
        return 'done'
    return 'in_progress' if reviewed else 'not_started'
