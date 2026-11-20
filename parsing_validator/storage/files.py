"""Review and draft stores over the annotations folder.

* ``annotations/<n>.review.json`` is the only file edited in place, only by ``save_review`` (BR-04).
* ``annotations/<n>.draft.json`` holds the current state and its temporary versions (BR-05).
* A save writes the review first and removes the draft second; a draft whose ``base_revision`` is lower
  than the review's revision is stale: reported, never restored, never deleted automatically (BR-07, OQ-08).
* A malformed file is reported and left untouched; the paper opens from the next source (BR-20).
* Business decision rules and MathML are not applied here; the service validates before calling.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .atomic import StorageError, atomic_write_bytes, remove_leftover_temporaries
from . import versions as chain_tools
from .schemas import problems

DRAFT_VERSION_CAP = 100


class RevisionConflict(Exception):
    """``If-Match`` does not equal the stored revision."""

    def __init__(self, expected, stored):
        super().__init__(f'expected revision {expected}, stored {stored}')
        self.expected, self.stored = expected, stored


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False).encode('utf-8') + b'\n'


class AnnotationStore:
    def __init__(self, folder, *, now=_now, fault=None):
        self.folder = Path(folder)
        self._now = now
        self._fault = fault  # test hook: called with the name of a step
        self._locks = {}
        self._guard = threading.Lock()

    # --- paths and locks -----------------------------------------------------
    def _check(self, paper):
        if problems('paper', paper):
            raise ValueError(f'Invalid paper id: {paper!r}')  # ids are digits only: no path ever comes from a request
        return paper

    def review_path(self, paper):
        return self.folder / f'{self._check(paper)}.review.json'

    def draft_path(self, paper):
        return self.folder / f'{self._check(paper)}.draft.json'

    def lock(self, paper):
        """Per-paper lock (use as a context manager)."""
        with self._guard:
            return self._locks.setdefault(self._check(paper), threading.RLock())

    def all_locks(self, papers):
        """Locks of several papers taken in numeric id order, as ``tags/replace`` needs."""
        return [self.lock(p) for p in sorted(papers, key=int)]

    # --- start-up ------------------------------------------------------------
    def startup(self):
        """Remove interrupted temporaries; report stale drafts and invalid files. Deletes nothing else."""
        self.folder.mkdir(parents=True, exist_ok=True)
        removed = remove_leftover_temporaries(self.folder)
        stale, invalid = [], []
        for draft in sorted(self.folder.glob('*.draft.json'), key=lambda p: int(p.name.split('.')[0])):
            paper = draft.name.split('.')[0]
            state = self.read(paper)
            if state['draft'] and state['draft']['stale']:
                stale.append(paper)
            invalid.extend(w['file'] for w in state['warnings'])
        return {'temporaries_removed': removed, 'stale_drafts': stale, 'invalid_files': sorted(set(invalid))}

    # --- reading -------------------------------------------------------------
    def _load(self, path, kind):
        """(value, warning): a missing file is (None, None); an unreadable or invalid one is (None, warning)."""
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None, None
        except OSError:
            return None, {'code': 'file_invalid', 'file': path.name}
        try:
            value = json.loads(raw)
        except ValueError:
            return None, {'code': 'file_invalid', 'file': path.name}
        if problems(kind, value) or value.get('paper') != path.name.split('.')[0]:
            return None, {'code': 'file_invalid', 'file': path.name}
        return value, None

    def read(self, paper):
        """What exists for a paper: ``{review, draft, revision, warnings}``. Writes nothing."""
        warnings = []
        review, warning = self._load(self.review_path(paper), 'review')
        if warning:
            warnings.append(warning)
        draft, warning = self._load(self.draft_path(paper), 'draft')
        if warning:
            warnings.append(warning)
        revision = review['revision'] if review else 0
        info = None
        if draft:
            info = {'exists': True, 'stale': draft['base_revision'] < revision, 'trigger': draft['trigger'],
                    'saved_at': draft['saved_at'], 'versions': len(draft['versions'])}
        return {'review': review, 'draft': info, 'draft_file': draft, 'revision': revision, 'warnings': warnings}

    # --- writing -------------------------------------------------------------
    def save_draft(self, paper, *, base_revision, trigger, state, new_versions=()):
        """Replace the paper's draft atomically; the review file is not touched (BR-05).

        ``new_versions`` (``{label, at, state}`` each, oldest first) are appended to the versions already in the
        draft; they are stored as an undo chain (ADR-005). The oldest are dropped past the cap, never the newest.
        """
        with self.lock(paper):
            existing, _ = self._load(self.draft_path(paper), 'draft')
            chain = existing['versions'] if existing else []
            current = existing['state'] if existing else None
            try:
                chain = chain_tools.append(chain, current, list(new_versions), state, DRAFT_VERSION_CAP)
            except chain_tools.VersionError as error:
                raise StorageError(f'The stored versions cannot be extended: {error}') from error
            draft = {'schema': 'parsing-validator-draft/1', 'paper': paper, 'base_revision': base_revision,
                     'saved_at': self._now(), 'trigger': trigger, 'state': state, 'versions': chain}
            bad = problems('draft', draft)
            if bad:
                raise ValueError('; '.join(bad[:5]))
            atomic_write_bytes(self.draft_path(paper), _dumps(draft), fault=self._fault)
            return {'saved_at': draft['saved_at'], 'versions': len(chain)}

    def save_review(self, paper, state, *, if_match, source):
        """Commit the review at ``revision + 1`` and then remove the draft (BR-07).

        Returns ``{revision, saved_at, warnings}``. If removing the draft fails the review is still
        the new truth and the leftover draft is stale on the next read.
        """
        with self.lock(paper):
            stored = self.read(paper)['revision']
            if if_match != stored:
                raise RevisionConflict(if_match, stored)
            body = {k: state[k] for k in ('reviewed', 'next_new_id', 'pages')}
            review = {'schema': 'parsing-validator-review/1', 'paper': paper, 'revision': stored + 1,
                      'saved_at': self._now(), 'source': source, **body}
            bad = problems('review', review)
            if bad:
                raise ValueError('; '.join(bad[:5]))
            atomic_write_bytes(self.review_path(paper), _dumps(review), fault=self._fault)
            if self._fault:
                self._fault('review_written')
            warnings = []
            try:
                self.draft_path(paper).unlink(missing_ok=True)
            except OSError:
                warnings.append({'code': 'draft_not_removed', 'file': self.draft_path(paper).name})
            return {'revision': review['revision'], 'saved_at': review['saved_at'], 'warnings': warnings}

    def rewrite(self, paper, *, review=None, draft=None):
        """Replace whole, already built files (the tag replacement of OP-08); each file is fully old or fully new.

        The draft is written before the review: if the process stops in between, the draft already claims the new
        revision (never stale) and re-running the operation finishes the review.
        """
        with self.lock(paper):
            for kind, value in (('draft', draft), ('review', review)):
                if value is not None:
                    bad = problems(kind, value)
                    if bad:
                        raise ValueError('; '.join(bad[:5]))
            if draft is not None:
                atomic_write_bytes(self.draft_path(paper), _dumps(draft), fault=self._fault)
            if review is not None:
                atomic_write_bytes(self.review_path(paper), _dumps(review), fault=self._fault)

    def draft_versions(self, paper):
        """``[{index, label, at, sha256}]`` of the paper's draft, without any state."""
        draft, _ = self._load(self.draft_path(paper), 'draft')
        return chain_tools.listing(draft['versions']) if draft else []

    def version_state(self, paper, index):
        """State of one temporary version, rebuilt and hash-checked; ``VersionError`` if it cannot be."""
        draft, _ = self._load(self.draft_path(paper), 'draft')
        if draft is None:
            raise chain_tools.VersionError('No draft')
        return chain_tools.restore(draft['state'], draft['versions'], index)

    def discard_draft(self, paper):
        """The user's explicit choice (Discard); the only way a draft is deleted apart from saving."""
        with self.lock(paper):
            try:
                self.draft_path(paper).unlink(missing_ok=True)
            except OSError as error:
                raise StorageError(f'Could not remove the draft: {error}') from error
