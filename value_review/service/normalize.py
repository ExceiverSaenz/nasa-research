"""Normalize on the service: OP-N01 to OP-N10 (92-normalize-interface-contract.md; 90-normalize-specification.md;
ADR-033 to ADR-036).

An extraction is a Review source (a folder pair or a workspace run). Its input is the latest submitted version of each
paper (BR-N02), read and never written. Rules, normalized values, validations and the apply's state live in
<data>/normalize/<source>/ (ADR-035). Applying sends one request per batch of at most 50 values of one feature
(ADR-034), with the model, key, retries, time limit, spending and blocked codes of Extraction (BR-N06).
"""
import csv
import io
import json
import math
import threading
import time
from dataclasses import dataclass, field as dc_field
from typing import Callable

from fastapi import Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..domain import normalize as nz
from ..domain.review_schema import fields_of
from ..ingest import features as guide
from ..storage import StorageError
from ..storage.normalize import FIELD_ID, NormalizeStore
from .errors import ApiError
from .exports import DELIMITERS, _text, cell
from .extraction import models
from . import sources as pairs
from . import workspace

API = '/api/v1/normalize'
SECONDS_PER_BATCH = 20   # the estimate's time per batch before any batch has been timed
REASONS = ['Wrong conversion', 'Value and uncertainty swapped', 'Should not be normalized', 'Wrong case for this value']


@dataclass
class NormalizeContext:
    """What Normalize takes from the rest of the service."""
    config: object
    settings_now: Callable
    clock: Callable
    source: Callable          # sid -> the Review source (``store``, ``library``, ``folders``), 404 when unknown
    binding: Callable         # source -> {ref, content, problem} (ADR-030)
    extraction: object        # Extraction's context: model and key checks, secrets, spending, System prompts
    locks: dict = dc_field(default_factory=dict)
    guard: object = dc_field(default_factory=threading.Lock)

    def store(self, sid):
        return NormalizeStore(self.config.data / 'normalize' / sid)

    def lock(self, *key):
        with self.guard:
            return self.locks.setdefault(key, threading.RLock())


class OutputField(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=80)
    on: bool = True


class Example(BaseModel):
    model_config = ConfigDict(extra='forbid')
    raw: str = Field(max_length=300)
    out: str = Field(max_length=300)


class RuleIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str = Field(pattern='^(norm|keep)$')
    text: str = Field(default='', max_length=50000)
    context: str = Field(default='', max_length=5000)
    output_fields: list[OutputField] = Field(default_factory=list, max_length=12)
    follow_examples: bool = False
    examples: list[Example] = Field(default_factory=list, max_length=30)
    decimals: str = Field(default='paper', pattern='^(paper|1|0)$')
    note: str = Field(default='', max_length=200)


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    features: list[str] | None = Field(default=None, max_length=500)
    model: str = Field(min_length=1, max_length=210)
    key_id: str | None = Field(default=None, max_length=10)


class TryIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rule: RuleIn
    model: str = Field(min_length=1, max_length=210)
    key_id: str | None = Field(default=None, max_length=10)


class ValidateIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(pattern='^(to_validate|accepted|corrected|rejected|unsure)$')
    reason: str = Field(default='', max_length=300)
    fields: list[dict] | None = Field(default=None, max_length=12)
    display: str | None = Field(default=None, max_length=300)


class CaseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case: str = Field(min_length=1, max_length=120)


def _etag(n):
    return f'"{n}"'


def if_match(request):
    raw = request.headers.get('if-match')
    if raw is None:
        raise ApiError(428, 'precondition_required', 'If-Match with the current version is required')
    text = raw.strip().removeprefix('W/').strip('"')
    try:
        return int(text)
    except ValueError:
        raise ApiError(400, 'invalid_request', 'If-Match must be a version number') from None


def storage(fn, *args):
    try:
        return fn(*args)
    except StorageError as error:
        raise ApiError(500, 'storage_error', str(error)) from None


def rule_out(field, rule, n):
    """The rule a feature has now (its saved version, or the defaults of its type)."""
    if rule is None:
        return {'n': 0, 'decision': nz.default_decision(field) if field else 'none', 'text': '', 'context': '',
                'output_fields': nz.default_output_fields(field) if field else [{'label': 'Value', 'on': True}],
                'follow_examples': False, 'examples': [], 'decimals': 'paper', 'saved_at': None, 'saved_by': None, 'note': ''}
    return {'n': n, **{k: rule[k] for k in ('decision', 'text', 'context', 'output_fields', 'follow_examples', 'examples', 'decimals',
                                             'saved_at', 'saved_by', 'note')}}


def build_prompt(system_text, field, rule, values):
    """The text of one request (BR-N06): the System prompt, the feature, the rule, its output fields and examples, then
    the values as JSON between <values> tags. The model answers each value by its id."""
    out_fields = [f['label'] for f in rule['output_fields'] if f['on']] or ['Value']
    lines = [system_text.strip(), '', '# Feature', f'Name: {field["label"]}', f'Type: {field["type"]}']
    if field.get('unit'):
        lines.append(f'Target unit: {field["unit"]}')
    if field.get('allowed'):
        lines.append('Allowed values: ' + ', '.join(field['allowed']))
    if field.get('description'):
        lines.append(f'Description: {field["description"]}')
    lines += ['', '# Rule', rule['text'].strip()]
    if rule['context'].strip():
        lines += ['', '# Context', rule['context'].strip()]
    lines += ['', '# Output fields', 'Return these fields for every value, by these names: ' + '; '.join(out_fields) + '.']
    if rule['follow_examples']:
        lines.append('Follow the format of the examples.')
    if rule['decimals'] != 'paper':
        lines.append(f'Round the value to {rule["decimals"]} decimal{"s" if rule["decimals"] != "1" else ""}.')
    if rule['examples']:
        lines += ['', '# Examples'] + [f'- {e["raw"]} → {e["out"]}' for e in rule['examples']]
    lines += ['', '# Values',
              'Answer once for every id below. "case" is the name of the case of the rule you applied. If no case fits, or the '
              'value is ambiguous, return it unchanged in "display", with flag true.',
              '<values>', json.dumps([{'id': v['id'], 'value': v['value'], 'unit': v['unit']} for v in values], ensure_ascii=False), '</values>']
    return '\n'.join(lines)


def install_normalize(app, ctx: NormalizeContext):
    ext = ctx.extraction
    runner = Runner(ctx)
    app.state.normalize = runner

    # --- reading an extraction -------------------------------------------------------
    def known_sources():
        """[{sid, name, set}] of the extractions Review knows: folder pairs and loaded workspace runs."""
        settings = ctx.settings_now()
        out, seen = [], set()
        for p in settings['sources']:
            out.append({'sid': p['id'], 'name': p['name'], 'set': None, 'kind': 'pair'})
            seen.add(p['id'])
        state = workspace.scan(ctx.config, settings['sources'])
        for s in state['sets']:
            for r in s['runs']:
                if r['source_id'] and r['source_id'] not in seen:
                    out.append({'sid': r['source_id'], 'name': r['name'], 'set': s['name'], 'kind': 'run',
                                'schema': (r['meta'] or {}).get('schema')})
                    seen.add(r['source_id'])
        return out

    def inputs(sid):
        """(source, reviewed values, {paper: latest n}, papers) of an extraction (BR-N02)."""
        c = ctx.source(sid)
        papers = c.library.papers()
        versions = {}
        for p in papers:
            latest, _problems = c.store.latest(p)
            versions[p] = latest
        return c, nz.reviewed_values(versions), {p: v['n'] for p, v in versions.items() if v}, papers

    def schema_fields(c, reviewed):
        """(fields, schema_ref, problem): the bound schema version's fields, else the reviewed values' own columns."""
        bound = ctx.binding(c)
        if bound['content'] is not None:
            return fields_of(bound['content']), bound['ref'], bound['problem']
        ids = list(dict.fromkeys(v['feature_id'] for v in reviewed))
        return ([{'field_id': i, 'label': guide.label(i), 'group_id': None, 'group': None, 'type': 'text', 'unit': '', 'allowed': [],
                  'multiple': False, 'description': '', 'family': None, 'calculated': False} for i in ids],
                None, bound['problem'])

    def all_features(sid, c, reviewed):
        """Schema fields in order, then archived ones (BR-N03): a field with a rule or values that the schema lacks."""
        fields, ref, problem = schema_fields(c, reviewed)
        fields = [nz.as_reviewed(f, [v for v in reviewed if v['feature_id'] == f['field_id']]) for f in fields]
        known = {f['field_id'] for f in fields}
        store = ctx.store(sid)
        extra = [fid for fid in store.ruled_fields() if fid not in known]
        for fid in extra:
            fields.append({'field_id': fid, 'label': guide.label(fid), 'group_id': None, 'group': 'Archived', 'type': 'text', 'unit': '',
                           'allowed': [], 'multiple': False, 'description': '', 'family': None, 'calculated': False, 'archived': True})
        return fields, ref, problem

    def find_field(sid, fid):
        c, reviewed, current, papers = inputs(sid)
        fields, _ref, _problem = all_features(sid, c, reviewed)
        f = next((x for x in fields if x['field_id'] == fid), None)
        if f is None or not FIELD_ID.fullmatch(fid):
            raise ApiError(404, 'feature_not_found', f'No feature {fid} in this extraction')
        return f, c, reviewed, current

    def current_rule(sid, fid):
        k, rule, _next, problems = ctx.store(sid).current_rule(fid)
        return k, rule, problems

    def feature_view(sid, f, reviewed, current, apply_state):
        fid = f['field_id']
        mine = [v for v in reviewed if v['feature_id'] == fid]
        k, rule, problems = current_rule(sid, fid)
        r = rule_out(f, rule, k)
        stored, problem = ctx.store(sid).read_values(fid)
        if problem:
            problems.append(problem)
        live = {v['id'] for v in mine}
        outdated = [s for s in stored.values() if s['id'] in live and nz.is_outdated(s, current, k)]
        fresh = [s for s in stored.values() if s['id'] in live and not nz.is_outdated(s, current, k)]
        missing = len(mine) - len(fresh) - len(outdated)
        validated = sum(1 for s in fresh if s['status'] in nz.VALIDATED)
        rejected = sum(1 for s in fresh if s['status'] == 'rejected')
        job = apply_state['features'].get(fid) if apply_state['status'] in ('running', 'paused') else None
        if f.get('archived'):
            status = 'archived'
        elif f['type'] == 'calculated':
            status = 'calc'
        elif r['decision'] in ('keep', 'calc'):
            status = 'kept'
        elif r['decision'] == 'none':
            status = 'none'
        elif job and job['status'] in ('queued', 'normalizing'):
            status = job['status']
        elif apply_state['features'].get(fid, {}).get('status') == 'failed' and (missing or outdated):
            status = 'failed'
        elif outdated:
            status = 'outdated'
        elif not r['text'].strip():
            status = 'draft'
        elif missing:
            status = 'ready'
        elif validated + rejected == len(mine) and mine:
            status = 'done'
        else:
            status = 'validating'
        return {
            'field_id': fid, 'label': f['label'], 'group': f['group'], 'type': f['type'], 'schema_type': f.get('schema_type', f['type']),
            'unit': f['unit'], 'allowed': f['allowed'],
            'description': f['description'], 'archived': bool(f.get('archived')), 'count': len(mine),
            'formats': nz.formats(f, mine), 'patterns': nz.patterns(f, mine),
            'decision': r['decision'], 'rule_version': k, 'rule_meta': {'saved_at': r['saved_at'], 'saved_by': r['saved_by']},
            'status': status, 'error': (apply_state['features'].get(fid) or {}).get('error'),
            'counts': {'values': len(mine), 'normalized': len(fresh), 'to_normalize': missing + len(outdated), 'outdated': len(outdated),
                       'validated': validated, 'rejected': rejected, 'to_validate': len(fresh) - validated - rejected},
            'problems': problems,
        }

    # --- OP-N01 ------------------------------------------------------------------------
    @app.get(f'{API}/extractions')
    def extractions():
        out = []
        for s in known_sources():
            try:
                c, reviewed, current, papers = inputs(s['sid'])
            except ApiError:
                continue
            if not papers:
                continue
            bound = ctx.binding(c)
            out.append({**s, 'schema_ref': bound['ref'], 'papers': len(papers), 'reviewed': len(current),
                        'reviewed_papers': sorted(current, key=workspace._order), 'values': len(reviewed),
                        'apply': runner.state(s['sid'])['status']})
        return {'extractions': out}

    # --- OP-N02 ------------------------------------------------------------------------
    @app.get(f'{API}/{{sid}}/features')
    def features(sid: str):
        c, reviewed, current, papers = inputs(sid)
        fields, ref, problem = all_features(sid, c, reviewed)
        state = runner.state(sid)
        return {'sid': sid, 'schema_ref': ref, 'schema_problem': problem,
                'coverage': {'papers': len(papers), 'reviewed': len(current), 'reviewed_papers': sorted(current, key=workspace._order),
                             'values': len(reviewed)},
                'features': [feature_view(sid, f, reviewed, current, state) for f in fields],
                'apply': state, 'keep': ctx.settings_now()['keep_rule_versions']}

    # --- OP-N03, OP-N04: rules -----------------------------------------------------------
    @app.get(f'{API}/{{sid}}/rules/{{fid}}')
    def get_rule(sid: str, fid: str, response: Response):
        f, *_ = find_field(sid, fid)
        k, rule, problems = current_rule(sid, fid)
        response.headers['ETag'] = _etag(k)
        return {**rule_out(f, rule, k), 'field_id': fid, 'keep': ctx.settings_now()['keep_rule_versions'], 'problems': problems}

    @app.get(f'{API}/{{sid}}/rules/{{fid}}/versions')
    def rule_versions(sid: str, fid: str):
        find_field(sid, fid)
        store, out = ctx.store(sid), []
        for n in store.rule_numbers(fid):
            data, problem = store.read_rule(fid, n)
            out.append({'n': n, 'saved_at': data['saved_at'], 'saved_by': data['saved_by'], 'note': data['note'], 'decision': data['decision'],
                        'restored_from': data.get('restored_from')} if data else {'n': n, 'problem': problem})
        return {'versions': out, 'keep': ctx.settings_now()['keep_rule_versions']}

    @app.get(f'{API}/{{sid}}/rules/{{fid}}/versions/{{n}}')
    def rule_version(sid: str, fid: str, n: int):
        f, *_ = find_field(sid, fid)
        data, problem = ctx.store(sid).read_rule(fid, n) if n >= 1 else (None, None)
        if data is None:
            raise ApiError(404, 'version_not_found', f'No version {n} of this rule', {'problem': problem} if problem else None)
        return {**rule_out(f, data, n), 'field_id': fid, 'restored_from': data.get('restored_from')}

    def save_rule(sid, fid, request, content, note, restored_from=None):
        f, *_ = find_field(sid, fid)
        if f.get('archived') or f['type'] == 'calculated':
            raise ApiError(409, 'feature_read_only', 'This feature is archived or calculated: its rule cannot change.')
        sent = if_match(request)
        if not content['output_fields']:
            content = {**content, 'output_fields': nz.default_output_fields(f)}
        store = ctx.store(sid)
        with ctx.lock('rule', sid, fid):
            k, _rule, nxt, _problems = store.current_rule(fid)
            if sent != k:
                raise ApiError(409, 'version_conflict', 'The rule was saved meanwhile.', {'current': k})
            data = {'schema': 'value-review-normalize-rule/1', 'field_id': fid, 'n': nxt, 'saved_at': ctx.clock(),
                    'saved_by': ctx.settings_now()['reviewer_name'], 'note': note, **content}
            if restored_from:
                data['restored_from'] = restored_from
            storage(store.write_rule, data)
            storage(store.prune_rules, fid, ctx.settings_now()['keep_rule_versions'])
        return {**rule_out(f, data, nxt), 'field_id': fid}

    @app.post(f'{API}/{{sid}}/rules/{{fid}}/versions', status_code=201)
    def new_rule(sid: str, fid: str, body: RuleIn, request: Request, response: Response):
        content = body.model_dump(exclude={'note'})
        out = save_rule(sid, fid, request, content, body.note.strip())
        response.headers['ETag'] = _etag(out['n'])
        return out

    @app.post(f'{API}/{{sid}}/rules/{{fid}}/versions/{{n}}/restore', status_code=201)
    def restore_rule(sid: str, fid: str, n: int, request: Request, response: Response):
        data, problem = ctx.store(sid).read_rule(fid, n) if n >= 1 and FIELD_ID.fullmatch(fid) else (None, None)
        if data is None:
            raise ApiError(404, 'version_not_found', f'No version {n} of this rule', {'problem': problem} if problem else None)
        content = {k: data[k] for k in ('decision', 'text', 'context', 'output_fields', 'follow_examples', 'examples', 'decimals')}
        out = save_rule(sid, fid, request, content, f'Restored from v{n}', restored_from=n)
        response.headers['ETag'] = _etag(out['n'])
        return out

    @app.post(f'{API}/{{sid}}/rules/{{fid}}/draft')
    def draft(sid: str, fid: str):
        f, c, reviewed, _current = find_field(sid, fid)
        mine = [v for v in reviewed if v['feature_id'] == fid]
        return {'text': nz.draft_rule(f, nz.patterns(f, mine))}

    # --- OP-N05 to OP-N07: estimate, apply, try ------------------------------------------
    def plan(sid, wanted=None):
        """{fid: (field, rule, rule_n, values to normalize)} for the features to apply (BR-N06, BR-N07)."""
        c, reviewed, current, papers = inputs(sid)
        fields, _ref, _problem = all_features(sid, c, reviewed)
        out = {}
        for f in fields:
            fid = f['field_id']
            if (wanted is not None and fid not in wanted) or f.get('archived') or f['type'] == 'calculated':
                continue
            k, rule, _problems = current_rule(sid, fid)
            if rule is None or rule['decision'] != 'norm':
                continue
            if not rule['text'].strip():
                if wanted is not None:
                    raise ApiError(409, 'rule_empty', f'Write the rule of {f["label"]} first.', {'field_id': fid})
                continue
            stored, _problem = ctx.store(sid).read_values(fid)
            todo = [v for v in reviewed if v['feature_id'] == fid
                    and (v['id'] not in stored or nz.is_outdated(stored[v['id']], current, k))]
            if todo:
                out[fid] = (f, rule, k, todo)
        return out

    def estimate_of(work, model, key_id):
        provider, name = model.split(':', 1) if ':' in model else (model, '')
        price = models.price(provider, name)
        settings = ctx.settings_now()['extraction']
        n_values = sum(len(t) for _f, _r, _k, t in work.values())
        n_batches = sum(len(nz.batches(t)) for _f, _r, _k, t in work.values())
        usd = None
        if price is not None:
            tokens_in = sum((700 + len(r['text']) // 4) * len(nz.batches(t)) + 30 * len(t) for _f, r, _k, t in work.values())
            tokens_out = 80 * n_values
            usd = round((tokens_in * price['input'] + tokens_out * price['output']) / 1_000_000, 2)
        minutes = max(1, math.ceil(n_batches * SECONDS_PER_BATCH / settings['parallel'] / 60)) if n_batches else 0
        return {'features': len(work), 'values': n_values, 'batches': n_batches, 'usd': usd, 'price_known': price is not None,
                'minutes': minutes, 'warn_usd': settings['warn_usd'], 'over_warning': usd is not None and usd > settings['warn_usd'],
                'blocked': ext.model_blocked(model, key_id)}

    def key_for(model, key_id):
        provider = model.split(':', 1)[0]
        return key_id or ext.default_key(provider)

    @app.get(f'{API}/{{sid}}/estimate')
    def estimate(sid: str, model: str = Query(max_length=210), key_id: str | None = Query(default=None, max_length=10),
                 features: str | None = Query(default=None, max_length=20000)):
        wanted = set(features.split(',')) if features else None
        return estimate_of(plan(sid, wanted), model, key_for(model, key_id))

    @app.post(f'{API}/{{sid}}/apply', status_code=202)
    def apply(sid: str, body: ApplyIn):
        key_id = key_for(body.model, body.key_id)
        blocked = ext.model_blocked(body.model, key_id)
        if blocked:
            raise ApiError(409, blocked[0]['code'], blocked[0]['message'], {'blocked': blocked})
        work = plan(sid, set(body.features) if body.features else None)
        if not work:
            raise ApiError(422, 'nothing_to_normalize', 'Every value of these features is normalized with their current rule.')
        return runner.start(sid, body.model, key_id, work)

    @app.get(f'{API}/{{sid}}/apply')
    def apply_state(sid: str):
        ctx.source(sid)
        return runner.state(sid)

    @app.post(f'{API}/{{sid}}/apply/pause')
    def pause(sid: str):
        return runner.stop(sid, 'pause')

    @app.post(f'{API}/{{sid}}/apply/cancel')
    def cancel(sid: str):
        return runner.stop(sid, 'cancel')

    @app.post(f'{API}/{{sid}}/apply/resume', status_code=202)
    def resume(sid: str):
        state = runner.state(sid)
        if state['status'] != 'paused':
            raise ApiError(409, 'not_paused', 'Nothing is paused.')
        wanted = {fid for fid, f in state['features'].items() if f['status'] in ('queued', 'normalizing')}
        work = plan(sid, wanted) if wanted else {}
        if not work:
            runner.finish_idle(sid)
            return runner.state(sid)
        return runner.start(sid, state['model'], state['key_id'], work, resumed=True)

    @app.post(f'{API}/{{sid}}/apply/features/{{fid}}/retry', status_code=202)
    def retry(sid: str, fid: str):
        state = runner.state(sid)
        if (state['features'].get(fid) or {}).get('status') != 'failed':
            raise ApiError(409, 'not_failed', 'This feature did not fail.')
        work = plan(sid, {fid})
        if not work:
            raise ApiError(422, 'nothing_to_normalize', 'Every value of this feature is normalized.')
        return runner.start(sid, state['model'], state['key_id'], work)

    @app.post(f'{API}/{{sid}}/rules/{{fid}}/try')
    def try_rule(sid: str, fid: str, body: TryIn):
        f, c, reviewed, _current = find_field(sid, fid)
        key_id = key_for(body.model, body.key_id)
        blocked = ext.model_blocked(body.model, key_id)
        if blocked:
            raise ApiError(409, blocked[0]['code'], blocked[0]['message'], {'blocked': blocked})
        if not body.rule.text.strip():
            raise ApiError(409, 'rule_empty', 'Write the rule first.')
        mine = [v for v in reviewed if v['feature_id'] == fid][:10]
        if not mine:
            raise ApiError(422, 'nothing_to_normalize', 'This feature has no reviewed values.')
        results, usd = runner.call(f, body.rule.model_dump(), mine, body.model, key_id)
        return {'usd': usd, 'results': [{'id': v['id'], 'paper': v['paper'], 'reviewed': nz.shown(v['value'], v['unit']), **results[v['id']]}
                                        for v in mine]}

    # --- OP-N08, OP-N09: validate ------------------------------------------------------------
    def stored_view(s, current, k, mine_by_id):
        v = mine_by_id.get(s['id'])
        return {**{key: s[key] for key in ('id', 'paper', 'case', 'fields', 'unit', 'display', 'flag', 'note', 'status', 'reason', 'by',
                                            'validated_at', 'rule_version', 'model', 'at', 'version_n')},
                'reviewed': nz.shown(s['reviewed'], s['reviewed_unit']), 'record_labels': s.get('record_labels') or (v or {}).get('record_labels', []),
                'outdated': nz.is_outdated(s, current, k)}

    @app.get(f'{API}/{{sid}}/features/{{fid}}/values')
    def feature_values(sid: str, fid: str):
        f, c, reviewed, current = find_field(sid, fid)
        k, rule, _problems = current_rule(sid, fid)
        stored, problem = ctx.store(sid).read_values(fid)
        mine = {v['id']: v for v in reviewed if v['feature_id'] == fid}
        rows = [stored_view(s, current, k, mine) for s in stored.values() if s['id'] in mine]
        cases = {}
        for r in rows:
            cases.setdefault(r['case'], []).append(r)
        order = lambda r: (not r['flag'], r['paper'].zfill(6), r['id'])   # noqa: E731
        out = [{'case': name, 'n': len(vals), 'flagged': sum(1 for v in vals if v['flag']),
                'validated': sum(1 for v in vals if v['status'] in nz.VALIDATED), 'values': sorted(vals, key=order)}
               for name, vals in cases.items()]
        out.sort(key=lambda x: (-x['n'], x['case']))
        return {'field_id': fid, 'label': f['label'], 'unit': f['unit'], 'rule_version': k,
                'output_fields': [o['label'] for o in rule_out(f, rule, k)['output_fields'] if o['on']],
                'not_normalized': sum(1 for i in mine if i not in stored), 'cases': out, 'reasons': REASONS,
                'problems': [problem] if problem else []}

    def change_values(sid, fid, change):
        """Apply ``change(stored value) -> bool`` to the feature's values under its lock; returns how many changed."""
        store = ctx.store(sid)
        with ctx.lock('values', sid, fid):
            stored, problem = store.read_values(fid)
            if problem:
                raise ApiError(500, 'storage_error', 'The normalized values cannot be read', {'problem': problem})
            n = sum(1 for s in stored.values() if change(s))
            if n:
                storage(store.write_values, fid, stored)
        return n

    @app.patch(f'{API}/{{sid}}/values/{{vid}}')
    def validate(sid: str, vid: str, body: ValidateIn):
        c, reviewed, current, _papers = inputs(sid)
        mine = next((v for v in reviewed if v['id'] == vid), None)
        if mine is None:
            raise ApiError(404, 'value_not_found', 'No reviewed value with this id')
        fid = mine['feature_id']
        k, _rule, _problems = current_rule(sid, fid)
        if body.status == 'rejected' and not body.reason.strip():
            raise ApiError(422, 'reason_required', 'Say why the value is rejected.')
        if body.status == 'corrected' and not body.fields:
            raise ApiError(422, 'fields_required', 'A correction needs the corrected fields.')
        found = {}

        def change(s):
            if s['id'] != vid:
                return False
            if nz.is_outdated(s, current, k):
                raise ApiError(409, 'value_outdated', 'This value is Outdated: apply the rule again first.')
            s['status'], s['reason'] = body.status, body.reason.strip() if body.status == 'rejected' else ''
            if body.status == 'corrected':
                s['fields'] = [{'name': str(x.get('name', ''))[:80], 'value': None if x.get('value') in (None, '') else str(x['value'])[:200]}
                               for x in body.fields]
                s['display'] = (body.display or ' · '.join(f'{x["value"]}' for x in s['fields'] if x['value'])).strip()[:300]
            s['by'] = None if body.status == 'to_validate' else ctx.settings_now()['reviewer_name']
            s['validated_at'] = None if body.status == 'to_validate' else ctx.clock()
            found['value'] = s
            return True
        if not change_values(sid, fid, change):
            raise ApiError(409, 'not_normalized', 'This value was not normalized yet.')
        return stored_view(found['value'], current, k, {vid: mine})

    @app.post(f'{API}/{{sid}}/features/{{fid}}/accept-case')
    def accept_case(sid: str, fid: str, body: CaseIn):
        f, c, reviewed, current = find_field(sid, fid)
        k, _rule, _problems = current_rule(sid, fid)
        live = {v['id'] for v in reviewed if v['feature_id'] == fid}
        who, at = ctx.settings_now()['reviewer_name'], ctx.clock()

        def change(s):
            if (s['id'] in live and s['case'] == body.case and not s['flag'] and s['status'] == 'to_validate'
                    and not nz.is_outdated(s, current, k)):
                s.update({'status': 'accepted', 'reason': '', 'by': who, 'validated_at': at})
                return True
            return False
        return {'accepted': change_values(sid, fid, change)}

    # --- OP-N10: results ------------------------------------------------------------------
    def results_of(sid):
        c, reviewed, current, papers = inputs(sid)
        fields, _ref, _problem = all_features(sid, c, reviewed)
        columns, cells, left = [], {}, {'to_validate': 0, 'outdated': 0, 'rejected': 0, 'not_normalized': 0}
        rows = {}
        for v in reviewed:
            rows.setdefault((v['paper'], tuple(v['record_ids'])), {'paper': v['paper'], 'record': ', '.join(v['record_labels']) or '—'})
        for f in fields:
            fid = f['field_id']
            mine = [v for v in reviewed if v['feature_id'] == fid]
            if f.get('archived') or not mine:
                continue
            k, rule, _problems = current_rule(sid, fid)
            r = rule_out(f, rule, k)
            if f['type'] == 'calculated':
                columns.append({'id': fid, 'label': f['label'], 'unit': f['unit'], 'kind': 'calc'})
                continue
            if r['decision'] != 'norm':
                columns.append({'id': fid, 'label': f['label'], 'unit': '', 'kind': 'kept'})
                for v in mine:
                    cells.setdefault((v['paper'], tuple(v['record_ids']), fid), []).append(('', nz.shown(v['value'], v['unit']), 'ok'))
                continue
            names = [o['label'] for o in r['output_fields'] if o['on']] or ['Value']
            columns.append({'id': fid, 'label': f['label'], 'unit': f['unit'], 'kind': 'norm', 'fields': names})
            stored, _problem = ctx.store(sid).read_values(fid)
            for v in mine:
                s = stored.get(v['id'])
                key = (v['paper'], tuple(v['record_ids']), fid)
                if s is None:
                    left['not_normalized'] += 1
                    cells.setdefault(key, []).append((None, nz.shown(v['value'], v['unit']), 'pending'))
                elif nz.is_outdated(s, current, k):
                    left['outdated'] += 1
                    cells.setdefault(key, []).append((s, s['display'], 'outdated'))
                elif s['status'] == 'rejected':
                    left['rejected'] += 1
                    cells.setdefault(key, []).append((s, s['display'], 'rejected'))
                elif s['status'] in nz.VALIDATED:
                    cells.setdefault(key, []).append((s, s['display'], 'ok'))
                else:
                    left['to_validate'] += 1
                    cells.setdefault(key, []).append((s, s['display'], 'pending'))
        order = lambda key: (workspace._order(key[0]), key[1])   # noqa: E731
        out_rows = []
        for key in sorted(rows, key=order):
            row = rows[key]
            out_cells = []
            for col in columns:
                got = cells.get((key[0], key[1], col['id']), [])
                if not got:
                    out_cells.append({'value': '—', 'status': 'empty' if col['kind'] != 'calc' else 'calc', 'parts': []})
                    continue
                statuses = [g[2] for g in got]
                status = 'ok' if all(s == 'ok' for s in statuses) else next(s for s in ('outdated', 'pending', 'rejected') if s in statuses)
                out_cells.append({'value': '; '.join(g[1] for g in got), 'status': status, 'parts': got})
            out_rows.append({'paper': row['paper'], 'record': row['record'], 'cells': out_cells})
        return columns, out_rows, left, papers, current

    @app.get(f'{API}/{{sid}}/results')
    def results(sid: str):
        columns, rows, left, papers, current = results_of(sid)
        return {'columns': [{k: v for k, v in col.items()} for col in columns],
                'rows': [{'paper': r['paper'], 'record': r['record'], 'cells': [{'value': x['value'], 'status': x['status']} for x in r['cells']]}
                         for r in rows],
                'left_out': left, 'coverage': {'papers': len(papers), 'reviewed': len(current)}}

    @app.get(f'{API}/{{sid}}/results.csv')
    def results_csv(sid: str):
        columns, rows, _left, _papers, _current = results_of(sid)
        settings = ctx.settings_now()
        header = ['paper', 'record']
        for col in columns:
            if col['kind'] == 'norm':
                header += [f'{col["label"]} · {name}' for name in col['fields']] + [f'{col["label"]} · unit']
            else:
                header.append(col['label'] + (f' ({col["unit"]})' if col['unit'] else ''))
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=DELIMITERS[settings['csv_delimiter']], lineterminator='\r\n')
        writer.writerow(header)
        for r in rows:
            line = [r['paper'], r['record']]
            for col, x in zip(columns, r['cells'], strict=True):
                ok = [p for p in x['parts'] if p[2] == 'ok']
                if col['kind'] == 'norm':
                    for name in col['fields']:
                        line.append('; '.join(next((fv['value'] or '' for fv in p[0]['fields'] if fv['name'] == name), '') for p in ok))
                    line.append('; '.join((p[0]['unit'] or '') for p in ok))
                elif col['kind'] == 'calc':
                    line.append('')
                else:
                    line.append('; '.join(p[1] for p in ok))
            writer.writerow([cell(v) for v in line])
        name = f'normalized-{pairs.slug(sid) or "extraction"}.csv'
        return Response(_text(buf.getvalue(), settings['csv_encoding']), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="{name}"'})


class Runner:
    """Applies rules in background threads, at most "papers at the same time" batches per extraction (BR-N06). The state
    is saved in apply.json after every change; a restart turns a running apply into Paused (AC-N08)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.jobs = {}       # sid -> {'stop': None | 'pause' | 'cancel', 'threads': [...], 'queue': [...]}
        self.guard = threading.Lock()

    # --- state ------------------------------------------------------------------------
    def state(self, sid):
        store = self.ctx.store(sid)
        with self.ctx.lock('apply', sid):
            st = store.read_apply()
            st.setdefault('status', 'idle')
            if st['status'] == 'running' and sid not in self.jobs:   # the service stopped while applying
                st['status'] = 'paused'
                for f in st['features'].values():
                    if f['status'] == 'normalizing':
                        f['status'] = 'queued'
                storage(store.write_apply, st)
            return st

    def update(self, sid, fn):
        store = self.ctx.store(sid)
        with self.ctx.lock('apply', sid):
            st = store.read_apply()
            fn(st)
            storage(store.write_apply, st)
            return st

    def finish_idle(self, sid):
        self.update(sid, lambda st: st.update({'status': 'complete', 'finished_at': self.ctx.clock()}))

    def wait_idle(self, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.guard:
                if not self.jobs:
                    return True
            time.sleep(0.02)
        return False

    # --- one call ------------------------------------------------------------------------
    def system_prompt(self):
        sp = self.ctx.extraction.system_prompts
        if not sp.exists('normalization'):
            storage(sp.seed, 'normalization', self.ctx.clock())
        k, latest, _n, _problems = sp.current('normalization')
        return (k or None), (latest['text'] if latest else '')

    def call(self, field, rule, batch, model, key_id, should_stop=lambda: False):
        """({value id: result}, usd) for one batch, with the retries of Settings. Raises models.ModelError."""
        ext = self.ctx.extraction
        settings = self.ctx.settings_now()['extraction']
        _k, system_text = self.system_prompt()
        prompt = build_prompt(system_text, field, rule, batch)
        provider, name = model.split(':', 1)
        from .extraction.work import key_text
        last = None
        for attempt in range(1 + settings['retries']):
            if should_stop() and attempt:
                break
            try:
                answer = models.complete(provider, name, key_text(ext, key_id), prompt, 'normalize-answer', settings['minutes'] * 60)
            except models.ModelError as error:
                last = error
                if not error.retry:
                    break
                time.sleep(min(2 ** attempt, 30) * ext.backoff)
                continue
            if answer.usd:
                ext.spending.add(key_id, ext.month(), answer.usd)
            return nz.answer_by_id(batch, answer.data), answer.usd or 0
        raise last or models.ModelError('stopped', 'Stopped before the batch was normalized.', False)

    # --- the apply ----------------------------------------------------------------------
    def start(self, sid, model, key_id, work, resumed=False):
        with self.guard:
            if sid in self.jobs:
                raise ApiError(409, 'run_running', 'Rules are being applied in this extraction already.')
            queue = [(fid, i, batch) for fid, (_f, _r, _k, todo) in work.items() for i, batch in enumerate(nz.batches(todo))]
            job = {'stop': None, 'threads': [], 'queue': queue, 'running': 0, 'work': work, 'left': {fid: len(nz.batches(t)) for fid, (_f, _r, _k, t) in work.items()}}
            self.jobs[sid] = job
        at = self.ctx.clock()

        def begin(st):
            if not resumed:
                st['features'] = {fid: f for fid, f in st['features'].items() if fid not in work and f['status'] in ('done', 'failed')}
                st['usd'] = 0
                st['started_at'] = at
            st.update({'status': 'running', 'model': model, 'key_id': key_id, 'finished_at': None})
            for fid, (_f, _rule, k, todo) in work.items():
                st['features'][fid] = {'status': 'queued', 'values': len(todo), 'batches': len(nz.batches(todo)), 'batches_done': 0,
                                       'rule_version': k, 'error': None, 'usd': 0}
        self.update(sid, begin)
        parallel = self.ctx.settings_now()['extraction']['parallel']
        count = max(1, min(parallel, len(queue)))
        job['running'] = count
        for i in range(count):
            t = threading.Thread(target=self.worker, args=(sid, job), daemon=True, name=f'normalize-{sid}-{i}')
            job['threads'].append(t)
        for t in job['threads']:
            t.start()
        return self.state(sid)

    def worker(self, sid, job):
        try:
            while True:
                with self.guard:
                    if job['stop'] or not job['queue']:
                        break
                    fid, _index, batch = job['queue'].pop(0)
                field, rule, k, _todo = job['work'][fid]
                self.set_feature(sid, fid, status='normalizing')
                st = self.state(sid)
                sys_n, _text = self.system_prompt()
                try:
                    results, usd = self.call(field, rule, batch, st['model'], st['key_id'], lambda: job['stop'] is not None)
                except models.ModelError as error:
                    with self.guard:
                        job['queue'] = [q for q in job['queue'] if q[0] != fid]
                    self.set_feature(sid, fid, status='failed', error=error.message)
                    continue
                self.write_batch(sid, fid, k, batch, results, st['model'], sys_n)
                self.batch_done(sid, fid, usd)
        finally:
            with self.guard:
                job['running'] -= 1
                last = job['running'] == 0
            if last:
                self.close(sid, job)

    def set_feature(self, sid, fid, **changes):
        self.update(sid, lambda st: st['features'][fid].update(changes))

    def batch_done(self, sid, fid, usd):
        def done(st):
            f = st['features'][fid]
            f['batches_done'] += 1
            f['usd'] = round(f['usd'] + usd, 6)
            st['usd'] = round(st.get('usd', 0) + usd, 6)
            if f['batches_done'] >= f['batches'] and f['status'] != 'failed':
                f['status'] = 'done'
        self.update(sid, done)

    def write_batch(self, sid, fid, k, batch, results, model, sys_n):
        store, at = self.ctx.store(sid), self.ctx.clock()
        with self.ctx.lock('values', sid, fid):
            stored, _problem = store.read_values(fid)
            for v in batch:
                r = results[v['id']]
                stored[v['id']] = {'id': v['id'], 'paper': v['paper'], 'observation_id': v['observation_id'], 'version_n': v['version_n'],
                                   'rule_version': k, 'model': model, 'system_prompt_version': sys_n, 'at': at,
                                   'reviewed': v['value'], 'reviewed_unit': v['unit'], 'record_ids': v['record_ids'],
                                   'record_labels': v['record_labels'], **r, 'status': 'to_validate', 'reason': '', 'by': None,
                                   'validated_at': None}
            storage(store.write_values, fid, stored)

    def close(self, sid, job):
        stop = job['stop']

        def finish(st):
            for f in st['features'].values():
                if f['status'] in ('queued', 'normalizing'):
                    f['status'] = 'cancelled' if stop == 'cancel' else 'queued'
            st['status'] = {'pause': 'paused', 'cancel': 'cancelled'}.get(stop, 'complete')
            st['finished_at'] = None if stop == 'pause' else self.ctx.clock()
        self.update(sid, finish)
        with self.guard:
            self.jobs.pop(sid, None)

    def stop(self, sid, how):
        with self.guard:
            job = self.jobs.get(sid)
            if job is None:
                raise ApiError(409, 'not_running', 'Rules are not being applied now.')
            job['stop'] = how
            threads = list(job['threads'])
        for t in threads:
            t.join(timeout=0.05)
        return self.state(sid)
