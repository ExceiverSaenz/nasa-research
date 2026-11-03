"""Small configuration gate shared by local and remote test probes.

No import performs I/O. Checks depend on callables, not on an installer or CLI.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Callable, Protocol


def _safe(value):
    text = json.dumps(value, sort_keys=True)
    if any(term in text.lower() for term in ('x-amz-', 'aws_secret_access_key', 'aws_access_key_id',
                                              'authorization', 'bearer ', 'https://', 'http://')):
        raise ValueError('Sensitive transport metadata is forbidden in receipts')


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    details: dict

    def __post_init__(self):
        if self.status not in {'PASS', 'FAIL', 'NOT_RUN', 'UNSUPPORTED'}:
            raise ValueError('Unknown check status')
        _safe(self.details)


class Check(Protocol):
    def run(self) -> CheckResult: ...


@dataclass
class FunctionCheck:
    name: str
    operation: Callable[[], dict]

    def run(self):
        try:
            return CheckResult(self.name, 'PASS', self.operation())
        except Exception as exc:
            # Upstream exception messages may contain bearer URLs or credentials.
            return CheckResult(self.name, 'FAIL', {'error_type': type(exc).__name__})


@dataclass
class ConfigReport:
    run_id: str
    checks: list[CheckResult]

    def ready(self, required: set[str]) -> bool:
        names = [check.name for check in self.checks]
        return (len(names) == len(set(names)) and set(names) == required
                and all(check.status == 'PASS' for check in self.checks))

    def to_dict(self):
        return {'schema': 'reading-order-config/1', 'run_id': self.run_id,
                'checks': [asdict(check) for check in self.checks]}

    @classmethod
    def from_dict(cls, value, expected_run):
        if value.get('schema') != 'reading-order-config/1' or value.get('run_id') != expected_run:
            raise ValueError('Receipt identity mismatch')
        return cls(expected_run, [CheckResult(**item) for item in value['checks']])


def run_checks(run_id: str, checks: list[Check]) -> ConfigReport:
    return ConfigReport(run_id, [check.run() for check in checks])


def fingerprint(versions: dict, probe_hash: str) -> str:
    return hashlib.sha256(json.dumps({'versions': versions, 'probe': probe_hash},
                                    sort_keys=True).encode()).hexdigest()


def verify_pdf(content: bytes, expected_sha256: str) -> dict:
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256 or b'%PDF-' not in content[:1024]:
        raise ValueError('PDF identity or header mismatch')
    return {'sha256': actual, 'bytes': len(content)}


def validate_checkpoint_keys(expected: set, supplied: set, allowed_missing: set) -> list:
    missing = expected - supplied
    if supplied - expected or missing - allowed_missing:
        raise ValueError('Checkpoint has unexpected keys or missing active parameters')
    return sorted(missing)


def verify_mineru_references(root) -> dict:
    """Verify existing references in place. Never write or return source contents."""
    documents = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        normalized_path = folder / 'normalized.json'
        middle_path = folder / 'middle.json'
        normalized_bytes = normalized_path.read_bytes()
        middle_bytes = middle_path.read_bytes()
        rows = json.loads(normalized_bytes)
        middle = json.loads(middle_bytes)
        middle_sha = hashlib.sha256(middle_bytes).hexdigest()
        ids = set()
        papers = set()
        for row in rows:
            if row['id'] in ids or row['original_sha256'] != middle_sha:
                raise ValueError('Duplicate ID or changed original')
            ids.add(row['id'])
            papers.add(row['paper_sha256'])
            path, separator, pointer = row['original_ref'].partition('#')
            if not separator or not path.endswith('/' + folder.name + '/middle.json') or not pointer.startswith('/'):
                raise ValueError('Unsupported source reference')
            target = middle
            try:
                for part in pointer[1:].split('/'):
                    part = part.replace('~1', '/').replace('~0', '~')
                    if isinstance(target, list):
                        if not part.isdigit():
                            raise ValueError('Invalid array index')
                        target = target[int(part)]
                    else:
                        target = target[part]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError('Unresolved JSON Pointer') from exc
        if not ids or len(papers) != 1:
            raise ValueError('Missing or ambiguous document identity')
        documents.append({'paper': folder.name + '.pdf', 'paper_sha256': next(iter(papers)),
                          'records': len(rows), 'middle_sha256': middle_sha,
                          'normalized_sha256': hashlib.sha256(normalized_bytes).hexdigest()})
    if not documents:
        raise ValueError('No documents found')
    return {'documents': len(documents), 'files': documents, 'persistence': 'reference_only',
            'scope': 'hashes_unique_ids_and_json_pointers; not full ingest or semantic validation'}
