"""Extraction (70-extraction-specification.md, 72-extraction-interface-contract.md; ADR-025 to ADR-029).

``install_extraction`` registers the routes. Runs live in <data>/extraction/runs/; their results go to the workspace.
"""
import os
import threading

from .runs import install_runs

__all__ = ['install_extraction']


def _warm_up():
    """Import the providers' SDKs once, in the background: they are large (seconds to load on a fresh start), and the
    first test or launch would otherwise wait for them."""
    for name in ('anthropic', 'openai'):
        try:
            __import__(name)
        except ImportError:   # reported by the first call that needs it
            pass


_warming = threading.Lock()
_warmed = []


def install_extraction(app, ctx):
    """``ctx``: the service pieces Extraction uses (see ``runs.Context``). The SDKs are loaded once per process, unless
    ``VALUE_REVIEW_WARM_UP=0`` (the browser tests' servers, which start often and rarely call a model)."""
    install_runs(app, ctx)
    with _warming:
        if _warmed or os.environ.get('VALUE_REVIEW_WARM_UP', '1') == '0':
            return
        _warmed.append(True)
    threading.Thread(target=_warm_up, daemon=True, name='extraction-warm-up').start()
