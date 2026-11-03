from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

CANDIDATES = ('hantian', 'docling', 'xycut_plus_plus', 'xycut', 'pp_doclayout_v2', 'doctr')
STATUSES = ('PASS', 'FAIL', 'NOT_RUN', 'UNSUPPORTED')


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def require_permutation(sequence, ids):
    if not isinstance(sequence, list) or len(sequence) != len(ids) or len(set(sequence)) != len(sequence) or set(sequence) != set(ids):
        raise ValueError('Expected exact ID permutation; output was not repaired')
    return sequence


def ranks_to_ids(ranks, ids):
    require_permutation(ranks, list(range(len(ids))))
    return [ids[index] for index in sorted(range(len(ids)), key=lambda i: ranks[i])]


@dataclass(frozen=True)
class Experiment:
    source_root: Path
    pilot_document_ids: list[str]
    confirmation_document_ids: list[str]
    seed: int = 1729
    language: str = 'en'
    timeout_s: int = 300
    context_mode: str = 'full_page'

    def __post_init__(self):
        all_ids = self.pilot_document_ids + self.confirmation_document_ids
        if len(set(all_ids)) != len(all_ids) or self.timeout_s < 1 or self.context_mode != 'full_page':
            raise ValueError('Invalid experiment selection or scope')


@dataclass
class Block:
    id: str
    paper_sha256: str
    page_idx: int
    raw_label: str
    bbox: list | None
    parent_id: str | None
    source_ref: str
    text: str | None = None
    text_parts: list = field(default_factory=list)
    route: str | None = None
    group_ids: list = field(default_factory=list)
    exclusion: str | None = None


@dataclass
class InputDocument:
    paper_id: str
    paper_sha256: str
    pages: list[dict]
    blocks: list[Block]
    references: dict
    status: str = 'PASS'

    def eligible(self, page_idx):
        return [b.id for b in self.blocks if b.page_idx == page_idx and b.exclusion is None]


@dataclass(frozen=True)
class Scope:
    paper_id: str
    page_idx: int
    input_profile_id: str
    eligible_ids_hash: str
    permutation_seed: int
    route: str | None = None


@dataclass
class Prediction:
    candidate_id: str
    scope: dict
    status: str
    ordered_ids: list | None
    native: dict = field(default_factory=dict)
    reason: str | None = None
    costs: dict = field(default_factory=dict)
    transformations: dict = field(default_factory=dict)

    def validate(self, eligible_ids):
        if self.candidate_id not in CANDIDATES or self.status not in STATUSES:
            raise ValueError('Unknown candidate or status')
        if self.status == 'PASS':
            require_permutation(self.ordered_ids, eligible_ids)
        elif self.ordered_ids is not None:
            raise ValueError('Invalid predictions cannot publish an order')


def load_experiment(path):
    data = json.loads(Path(path).read_text())
    return Experiment(source_root=(Path(path).parent / data.pop('source_root')).resolve(), **data)


def validate_prediction(pred, scope, eligible_ids):
    try:
        pred.validate(eligible_ids)
        if pred.scope != scope:
            raise ValueError('Scope mismatch')
        return []
    except (TypeError, ValueError) as error:
        return [str(error)]
