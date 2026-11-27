"""Extracting one paper, shared by tests and launches: the model call with the run's retries, the cost added to the
key's spending, and the answer mapped to a result (BR-X04, BR-X10). Nothing here writes a result file."""
import time
from pathlib import Path

from ...storage import StorageError
from ...storage.prompts import PromptStore
from ..errors import ApiError
from ..workspace import PAPERS
from . import models, results

PAPER_FILE = '{paper}.pdf'


def pdf_path(ctx, run, paper):
    return Path(ctx.config.workspace) / PAPERS / run['set'] / PAPER_FILE.format(paper=paper)


def set_papers(ctx, run):
    """Paper ids of the run's set (PDF stems), in numeric order."""
    folder = Path(ctx.config.workspace) / PAPERS / run['set'] if ctx.config.workspace else None
    try:
        stems = [p.stem for p in folder.glob('*.pdf')] if folder else []
    except OSError:
        stems = []
    return sorted(stems, key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s))


def current_prompt(ctx, run):
    """(number, text) of the prompt the run would use now: the launched version for a launched run."""
    store = PromptStore(ctx.runs.run_dir(run['id']))
    if run['prompt_version']:
        data, _problem = store.read_version(run['prompt_version'])
        return (run['prompt_version'], data['text']) if data else (0, '')
    k, latest, _n, _problems = store.current()
    return (k, latest['text']) if latest else (0, '')


def require_ready(ctx, run):
    """409 with the first reason the run cannot be tested or launched (BR-X07), or no saved prompt."""
    blocked = ctx.blocked(run)
    if blocked:
        raise ApiError(409, blocked[0]['code'], blocked[0]['message'], {'blocked': blocked})
    if not current_prompt(ctx, run)[0]:
        raise ApiError(409, 'no_prompt', 'Save the prompt first.')


def key_text(ctx, key_id):
    try:
        entry = next((k for k in ctx.secrets.read()['keys'] if k['id'] == key_id), None)
    except StorageError:
        entry = None
    if entry is None:
        raise models.ModelError('key_not_found', 'This API key was removed.', False)
    return entry['key']


def extract_one(ctx, run, prompt, paper, should_stop=lambda: False):
    """(answer, result, attempts) for one paper, trying again on failures that may pass (Settings: retries, time limit
    per paper). Each attempt that the provider billed adds to the key's spending. Raises ModelError after the last."""
    settings = ctx.settings_now()['extraction']
    provider, model = run['model'].split(':', 1)
    attempts, last = 0, None
    for attempt in range(1 + settings['retries']):
        if should_stop() and attempt:
            break
        attempts += 1
        try:
            answer = models.extract(provider, model, key_text(ctx, run['key_id']), prompt, pdf_path(ctx, run, paper),
                                    settings['minutes'] * 60)
        except models.ModelError as error:
            last = error
            if not error.retry:
                break
            time.sleep(min(2 ** attempt, 30) * ctx.backoff)
            continue
        if answer.usd:
            ctx.spending.add(run['key_id'], ctx.month(), answer.usd)
        result = results.to_result(answer.data, run, paper, pdf_path(ctx, run, paper), run['set'])
        return answer, result, attempts
    raise last or models.ModelError('stopped', 'Stopped before the paper was extracted.', False)
