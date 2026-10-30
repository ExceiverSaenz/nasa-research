"""One discoverable run directory under the shared parser result root."""
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid


def results_root():
    package = Path(__file__).resolve().parents[2]
    return package.parent / 'results' / 'parse_results'


def resolve_output(value, *, base=None):
    """Resolve a new run name/path without creating it or escaping its system."""
    root = Path(base if base is not None else results_root()).resolve()
    if value is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        name = 'run-' + stamp + '-' + uuid.uuid4().hex
        return root / name
    requested = Path(value).expanduser()
    if requested.is_absolute():
        output = requested.resolve()
        if output.parent != root:
            raise ValueError('Output must be an immediate run directory inside ' + str(root))
    else:
        if len(requested.parts) != 1:
            raise ValueError('Use a run name or an absolute child of parse_results')
        output = root / requested
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', output.name):
        raise ValueError('Run name must use letters, digits, dots, underscores or hyphens')
    output = output.resolve()
    if output.parent != root:
        raise ValueError('Output escapes parse_results')
    return output
