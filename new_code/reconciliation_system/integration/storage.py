"""Resolve reconciliation attempts beneath the shared results directory."""
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid


def results_root():
    return Path(__file__).resolve().parents[1].parent / 'results' / 'reconciliation_results'


def resolve_output(value=None, *, base=None):
    root=Path(base if base is not None else results_root()).resolve()
    if value is None:
        value='run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex
    requested=Path(value).expanduser()
    if requested.is_absolute():
        output=requested.resolve()
    else:
        if len(requested.parts)!=1:
            raise ValueError('Use one run name within reconciliation_results')
        output=(root/requested).resolve()
    if output.parent!=root or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',output.name):
        raise ValueError('Output must be an immediate run directory in reconciliation_results')
    return output
