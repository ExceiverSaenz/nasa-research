"""Bug reports (OP-12, BR-19): validated, written as one new local JSON file, sent nowhere."""
import json
import os
import re
import tempfile
from pathlib import Path

from ..storage.atomic import StorageError

SCHEMA = 'parsing-validator-bug-report/1'
CATEGORIES = ('display', 'boxes', 'text', 'table', 'layers', 'saving', 'loading', 'export', 'settings', 'text-ui', 'speed', 'other')
SEVERITIES = ('blocks', 'annoying', 'minor')
LONG_TEXT = 10000
SHORT_TEXT = 200
LABEL = 120
MAX_ACTIONS = 50
MAX_BODY = 200_000
CONTEXT_TEXT = ('screen', 'tool', 'browser')


def _text(value, limit, pointer, bad, required=False):
    if value is None or value == '':
        if required:
            bad.append({'pointer': pointer, 'message': 'is required'})
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        bad.append({'pointer': pointer, 'message': 'must be text' + (' and not empty' if required else '')})
        return None
    if len(value) > limit:
        bad.append({'pointer': pointer, 'message': f'at most {limit} characters'})
        return None
    return value


def _context(raw, bad, tool_version):
    """Whitelisted session data; ``included: false`` (or no context) keeps nothing else. Unknown keys are dropped."""
    if not isinstance(raw, dict) or raw.get('included') is not True:
        return {'included': False}
    out = {'included': True}
    for key in CONTEXT_TEXT:
        out[key] = _text(raw.get(key), SHORT_TEXT, f'/context/{key}', bad)
    paper = raw.get('paper')
    out['paper'] = paper if paper is None or (isinstance(paper, str) and re.fullmatch(r'[0-9]+', paper)) else bad.append(
        {'pointer': '/context/paper', 'message': 'must be a paper id (digits)'})
    for key in ('page',):
        value = raw.get(key)
        out[key] = value if value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0) else bad.append(
            {'pointer': f'/context/{key}', 'message': 'must be a non-negative integer'})
    out['box'] = _text(raw.get('box'), SHORT_TEXT, '/context/box', bad)
    out['tool_version'] = tool_version                           # the service is the authority on its own version
    actions = raw.get('last_actions') or []
    if not (isinstance(actions, list) and all(isinstance(a, str) and len(a) <= LABEL for a in actions)):
        bad.append({'pointer': '/context/last_actions', 'message': f'a list of labels of at most {LABEL} characters'})
        actions = []
    out['last_actions'] = actions[-MAX_ACTIONS:]                 # labels only; the most recent ones
    window = raw.get('window')
    ok = isinstance(window, dict) and all(isinstance(window.get(k), int) and not isinstance(window.get(k), bool) and window[k] >= 0 for k in 'wh')
    if window is not None and not ok:
        bad.append({'pointer': '/context/window', 'message': 'needs integer w and h'})
    out['window'] = {'w': window['w'], 'h': window['h']} if ok else None
    return out


def build(body, created_at, tool_version):
    """``(report, problems)``; ``report`` is None when anything is invalid."""
    bad = []
    if not isinstance(body, dict):
        return None, [{'pointer': '', 'message': 'must be an object'}]
    category = body.get('category')
    if category not in CATEGORIES:
        bad.append({'pointer': '/category', 'message': 'must be one of ' + ', '.join(CATEGORIES)})
    other = _text(body.get('category_other'), SHORT_TEXT, '/category_other', bad, required=category == 'other')
    if body.get('severity') not in SEVERITIES:
        bad.append({'pointer': '/severity', 'message': 'must be one of ' + ', '.join(SEVERITIES)})
    what = _text(body.get('what_happened'), LONG_TEXT, '/what_happened', bad, required=True)
    expected = _text(body.get('expected'), LONG_TEXT, '/expected', bad)
    context = _context(body.get('context'), bad, tool_version)
    if bad:
        return None, bad
    return {'schema': SCHEMA, 'created_at': created_at, 'category': category,
            'category_other': other if category == 'other' else None, 'severity': body['severity'],
            'what_happened': what, 'expected': expected, 'context': context}, []


def write(folder, report):
    """Create ``bug-<category>-<utc timestamp>.json`` (a numeric suffix on a collision); never overwrites."""
    folder = Path(folder)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = report['created_at'].replace(':', '-')
        data = json.dumps(report, ensure_ascii=False, indent=1).encode('utf-8') + b'\n'
        descriptor, temp = tempfile.mkstemp(dir=folder, suffix='.tmp')
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(1, 1000):
                name = f"bug-{report['category']}-{stamp}{'' if attempt == 1 else f'-{attempt}'}.json"
                try:
                    os.link(temp, folder / name)
                    return name
                except FileExistsError:
                    continue
            raise StorageError('Too many bug reports with the same name')
        finally:
            try:
                os.unlink(temp)
            except OSError:
                pass
    except StorageError:
        raise
    except OSError as error:
        raise StorageError(f'Could not write the bug report: {type(error).__name__}') from error
