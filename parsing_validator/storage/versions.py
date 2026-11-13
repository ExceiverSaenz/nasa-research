"""Undo chain of a draft's temporary versions (ADR-005, option B as amended).

The draft keeps the current ``state`` in full. Each version stores only an *undo patch* that turns
the state that follows it (the next version, or the current state for the last one) back into its
own state, plus the SHA-256 of that state. Restoring version ``i`` replays the undo patches from the
current state backwards and checks the hash, so a wrong patch is detected instead of corrupting
silently. Dropping the oldest versions needs no rewrite.

Patches are a subset of RFC 6902 (``add``, ``remove``, ``replace``) over JSON objects; a list that
differs is replaced as a whole (reading orders are short lists).
"""
import copy
import hashlib
import json


class VersionError(Exception):
    """A version cannot be rebuilt (bad index, failed patch or hash mismatch)."""


def _escape(key):
    return key.replace('~', '~0').replace('/', '~1')


def _unescape(key):
    return key.replace('~1', '/').replace('~0', '~')


def digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def diff(source, target, path=''):
    """Patch that turns ``source`` into ``target``."""
    if source == target:
        return []
    if isinstance(source, dict) and isinstance(target, dict):
        ops = []
        for key in source:
            if key not in target:
                ops.append({'op': 'remove', 'path': f'{path}/{_escape(key)}'})
        for key, value in target.items():
            here = f'{path}/{_escape(key)}'
            if key not in source:
                ops.append({'op': 'add', 'path': here, 'value': value})
            else:
                ops.extend(diff(source[key], value, here))
        return ops
    return [{'op': 'replace', 'path': path, 'value': target}]


def apply(state, ops):
    """New state with ``ops`` applied. ``state`` is not modified: only the objects along each patched
    path are copied, everything else is shared with the input (treat the result as read-only)."""
    for op in ops:
        state = _apply_one(state, op)
    return state


def _apply_one(node, op):
    if op['path'] == '':
        if op['op'] != 'replace':
            raise VersionError('Only replace is allowed on the root')
        return copy.deepcopy(op['value'])
    return _walk(node, [_unescape(p) for p in op['path'].split('/')[1:]], op)


def _walk(node, keys, op):
    if not isinstance(node, dict):
        raise VersionError(f"Path not found: {op['path']}")
    key, new = keys[0], dict(node)
    if len(keys) > 1:
        if key not in new:
            raise VersionError(f"Path not found: {op['path']}")
        new[key] = _walk(new[key], keys[1:], op)
    elif op['op'] == 'remove':
        if key not in new:
            raise VersionError(f"Nothing to remove at {op['path']}")
        del new[key]
    elif op['op'] in ('add', 'replace'):
        if op['op'] == 'replace' and key not in new:
            raise VersionError(f"Nothing to replace at {op['path']}")
        new[key] = copy.deepcopy(op['value'])
    else:
        raise VersionError(f"Unknown operation {op['op']}")
    return new


def restore(current, chain, index):
    """State of version ``index`` rebuilt from the current state; the hash is verified."""
    if not 0 <= index < len(chain):
        raise VersionError(f'No version {index}')
    state = current
    for version in reversed(chain[index:]):
        state = apply(state, version['undo'])
    if digest(state) != chain[index]['sha256']:
        raise VersionError(f'Version {index} fails its hash check')
    return state


def append(chain, current, new_versions, state, cap):
    """New chain after saving ``state`` with ``new_versions`` (list of ``{label, at, state}``), capped."""
    sequence = []
    if chain:
        sequence.append((chain[-1]['label'], chain[-1]['at'], apply(current, chain[-1]['undo'])))
    sequence.extend((v['label'], v['at'], v['state']) for v in new_versions)
    rebuilt = []
    for j, (label, at, version_state) in enumerate(sequence):
        following = sequence[j + 1][2] if j + 1 < len(sequence) else state
        rebuilt.append({'label': label, 'at': at, 'undo': diff(following, version_state), 'sha256': digest(version_state)})
    return (chain[:-1] + rebuilt)[-cap:]


def listing(chain):
    return [{'index': i, 'label': v['label'], 'at': v['at'], 'sha256': v['sha256']} for i, v in enumerate(chain)]
