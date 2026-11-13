"""Tag usage and tag replacement across every review, draft and temporary version (BR-16, OP-08).

A replacement changes ``tag.value`` (and ``other_label``) only: ``tag.predicted`` stays as MinerU emitted it, which
is how a tag correction is recorded. Originals are never touched. Papers are processed one at a time under every
paper lock taken in id order; one paper that cannot be rewritten is reported in ``failures`` and the others apply.
"""
import copy
from contextlib import ExitStack

from ..domain import DecisionRulesViolation, check_state
from ..domain.catalogs import OTHER
from ..storage import versions as chain_tools
from ..storage.atomic import StorageError
from ..storage.files import DRAFT_VERSION_CAP
from .errors import ApiError

STATE_KEYS = ('reviewed', 'next_new_id', 'pages')


def tagged(state, name):
    """``[(page, block id)]`` of the blocks whose tag is ``name``."""
    return [(page, bid) for page, content in state['pages'].items() for bid, block in content['blocks'].items()
            if block['tag']['value'] == name]


def replace_in(state, name, to, other_label):
    """Retag in place; returns the changed ``[(page, block id)]``."""
    changed = tagged(state, name)
    for page, bid in changed:
        tag = state['pages'][page]['blocks'][bid]['tag']
        tag['value'] = to
        tag['other_label'] = other_label if to == OTHER else None
    return changed


def draft_states(draft):
    """The draft's version states rebuilt from its undo chain (raises ``VersionError`` if one is corrupt)."""
    return [chain_tools.restore(draft['state'], draft['versions'], i) for i in range(len(draft['versions']))]


def usage(store, papers, name):
    """How many blocks (review and current draft) and temporary versions still use tag ``name``."""
    blocks = versions = 0
    for paper in papers:
        stored = store.read(paper)
        for state in (stored['review'], stored['draft_file'] and stored['draft_file']['state']):
            if state:
                blocks += len(tagged(state, name))
        if stored['draft_file']:
            try:
                versions += sum(bool(tagged(s, name)) for s in draft_states(stored['draft_file']))
            except chain_tools.VersionError:
                versions += 1  # an unreadable chain is treated as in use rather than silently ignored
    return {'blocks': blocks, 'versions': versions}


def replace_tag(services, source, to, other_label, dry_run):
    store, library = services.store, services.library
    result = {'papers': [], 'failures': []}
    with ExitStack() as stack:
        for lock in store.all_locks(library.papers):
            stack.enter_context(lock)
        for paper in sorted(library.papers, key=int):
            outcome = _one_paper(services, paper, source, to, other_label, dry_run)
            if outcome.get('failure'):
                result['failures'].append({'paper': paper, **outcome['failure']})
            elif outcome['reviews_changed'] or outcome['drafts_changed']:
                result['papers'].append({'id': paper, **{k: v for k, v in outcome.items() if k != 'failure'}})
    return result


def _one_paper(services, paper, source, to, other_label, dry_run):
    store, library = services.store, services.library
    stored = store.read(paper)
    if stored['warnings']:   # an invalid file cannot be rewritten safely (BR-20): report it, change nothing
        return {'failure': {'reason': 'file_invalid', 'files': [w['file'] for w in stored['warnings']]}}
    outcome = {'reviews_changed': 0, 'drafts_changed': 0, 'blocks_changed': 0, 'versions_changed': 0}
    touched = set()
    review, draft = stored['review'], stored['draft_file']
    new_review = new_draft = None
    revision = stored['revision']

    if review is not None:
        new_review = copy.deepcopy(review)
        changed = replace_in(new_review, source, to, other_label)
        if changed:
            touched.update((p, b) for p, b in changed)
            outcome['reviews_changed'] = 1
            try:
                check_state(new_review, library.ensure_original(paper), _settings_for_check(services))
            except DecisionRulesViolation as error:
                return {'failure': {'reason': 'decision_rules_violation', 'violations': len(error.violations),
                                    'detail': error.violations[:5]}}
            except ApiError as error:
                return {'failure': {'reason': error.code}}
            revision += 1
            new_review['revision'] = revision
            new_review['saved_at'] = store._now()
        else:
            new_review = None

    if draft is not None:
        try:
            versions = [copy.deepcopy(v) for v in draft_states(draft)]   # restored states share subtrees: copy before editing
        except chain_tools.VersionError as error:
            return {'failure': {'reason': 'version_corrupt', 'detail': str(error)}}
        state = copy.deepcopy(draft['state'])
        current = replace_in(state, source, to, other_label)
        touched.update(current)
        changed_versions = [bool(replace_in(v, source, to, other_label)) for v in versions]
        if current or any(changed_versions):
            outcome['drafts_changed'] = 1
            outcome['versions_changed'] = sum(changed_versions)
            chain = chain_tools.append([], None, [{'label': v['label'], 'at': v['at'], 'state': s}
                                                  for v, s in zip(draft['versions'], versions)], state, DRAFT_VERSION_CAP)
            base = revision if draft['base_revision'] == stored['revision'] else draft['base_revision']
            new_draft = {**draft, 'state': state, 'versions': chain, 'base_revision': base, 'saved_at': store._now()}

    outcome['blocks_changed'] = len(touched)
    if dry_run or (new_review is None and new_draft is None):
        return outcome
    try:
        store.rewrite(paper, review=new_review, draft=new_draft)
    except (StorageError, ValueError) as error:
        return {'failure': {'reason': 'storage_error', 'detail': str(error)[:200]}}
    return outcome


def _settings_for_check(services):
    from . import settings as settings_module
    settings, _ = settings_module.load(services.config)
    return settings
