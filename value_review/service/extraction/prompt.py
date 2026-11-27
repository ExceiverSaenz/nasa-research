"""A run's prompt: the template and the saved versions, OP-X03 (72-extraction-interface-contract.md; BR-X02).

The template is the extraction System prompt followed by every field of the run's schema version, in schema order, as
Markdown: the text the model receives (canvas Extraction rule 3). No model is called. The expert edits it and saves
versions; a run keeps the version it was launched with. A saved prompt written for another schema version is flagged
(``stale_schema``) and nothing is rewritten by itself.
"""
from fastapi import Request, Response
from fastapi.responses import Response as RawResponse
from pydantic import BaseModel, ConfigDict, Field

from ...storage import StorageError
from ...storage.prompts import KEEP, PromptStore
from ..errors import ApiError

TYPE_TEXT = {'number': 'number', 'category': 'category', 'text': 'text', 'calculated': 'calculated'}


class PromptIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=200000)
    note: str = Field(default='', max_length=200)
    system_prompt_version: int | None = Field(default=None, ge=1)


def field_line(f):
    """One field as the model reads it: name, id, type details and description."""
    bits = [TYPE_TEXT.get(f['type'], f['type'])]
    if f.get('unit'):
        bits.append(f'unit {f["unit"]}')
    if f.get('allowed'):
        bits.append(('one or more of: ' if f.get('multiple') else 'one of: ') + ', '.join(f['allowed']))
    line = f'- **{f["name"]}** (`{f["field_id"]}`) · {"; ".join(bits)}'
    return line + (f'. {f["description"].strip()}' if f.get('description', '').strip() else '')


def template(system_text, schema_name, version, content):
    """The prompt the run starts from (AC-X03)."""
    out = [system_text.strip(), '', '# Task', '',
           f'Extract from the attached paper the values of the schema "{schema_name}" (version {version}). '
           'Return one record per specimen or test condition, and for each value the record(s) it belongs to.']
    if content.get('description', '').strip():
        out += ['', content['description'].strip()]
    out += ['', '## Fields']
    skipped = []
    for g in content['groups']:
        fields = [f for f in g['fields'] if f['type'] != 'calculated']
        skipped += [f['name'] for f in g['fields'] if f['type'] == 'calculated']
        if fields:
            out += ['', f'### {g["name"]}', ''] + [field_line(f) for f in fields]
    if skipped:
        out += ['', f'Do not extract these calculated fields; they are computed later: {", ".join(skipped)}.']
    out += ['', '## How to answer', '',
            '- Use the field ids above (`field_id`) for each value.',
            '- Give each value exactly as written in the paper, with its symbols (for example `710 ± 25`), and its unit as written.',
            '- For each value give the page number (1 is the first page of the PDF) and a short quote copied exactly from that page.',
            '- If the paper does not give a value, leave it out. Never guess.',
            '- Say in `completion` whether you read the whole paper.']
    return '\n'.join(out) + '\n'


def if_match(request):
    raw = request.headers.get('if-match')
    if raw is None:
        raise ApiError(428, 'precondition_required', 'If-Match with the current version is required')
    text = raw.strip()
    text = text[2:] if text.startswith('W/') else text
    try:
        return int(text.strip('"'))
    except ValueError:
        raise ApiError(400, 'invalid_request', 'If-Match must be a version number') from None


def install_prompt(app, ctx, api, read_run, schema_version):
    def store(rid):
        return PromptStore(ctx.runs.run_dir(rid))

    def system_prompt():
        if not ctx.system_prompts.exists('extraction'):
            ctx.system_prompts.seed('extraction', ctx.clock())
        k, latest, _n, _problems = ctx.system_prompts.current('extraction')
        return (k, latest['text']) if latest else (None, '')

    def unlocked(run):
        if run['status'] != 'draft':
            raise ApiError(409, 'run_locked', 'This run has results, so its prompt is read only. Make a copy to change it.')

    def current_view(run, response=None):
        k, latest, _n, problems = store(run['id']).current()
        if response is not None:
            response.headers['ETag'] = f'"{k}"'
        out = {'n': k, 'problems': problems, 'keep': KEEP, 'stale_schema': False}
        if latest:
            out.update({key: latest[key] for key in ('text', 'saved_at', 'saved_by', 'note', 'system_prompt_version', 'schema_ref')})
            out['stale_schema'] = latest['schema_ref'] != run['schema_ref']
        return out

    @app.post(f'{api}/runs/{{rid}}/prompt/template')
    def make_template(rid: str):
        run = read_run(rid)
        content, meta = schema_version(run['schema_ref']['id'], run['schema_ref']['version'])
        if content is None:
            raise ApiError(422, 'schema_not_found', 'This schema version cannot be read. Choose another saved version.')
        n, text = system_prompt()
        return {'text': template(text, meta['name'], run['schema_ref']['version'], content['content']),
                'system_prompt_version': n, 'schema_ref': run['schema_ref']}

    @app.get(f'{api}/runs/{{rid}}/prompt')
    def get_prompt(rid: str, response: Response):
        return current_view(read_run(rid), response)

    @app.get(f'{api}/runs/{{rid}}/prompt/versions')
    def list_versions(rid: str):
        read_run(rid)
        s, out, problems = store(rid), [], []
        for n in s.version_numbers():
            data, problem = s.read_version(n)
            if data is None:
                problems.append(problem)
                continue
            out.append({key: data[key] for key in ('n', 'saved_at', 'saved_by', 'note', 'system_prompt_version', 'schema_ref')}
                       | ({'restored_from': data['restored_from']} if 'restored_from' in data else {}))
        return {'versions': out, 'keep': KEEP, 'problems': problems}

    def read_version(rid, n):
        data, problem = store(rid).read_version(n) if n >= 1 else (None, None)
        if data is None:
            if problem:
                raise ApiError(500, 'storage_error', f'Version {n} cannot be read', {'problem': problem})
            raise ApiError(404, 'version_not_found', f'The prompt has no version {n}')
        return data

    @app.get(f'{api}/runs/{{rid}}/prompt/versions/{{n}}')
    def get_version(rid: str, n: int):
        read_run(rid)
        return read_version(rid, n)

    def new_version(rid, request, response, text_for):
        expected = if_match(request)
        with ctx.lock:
            run = read_run(rid)
            unlocked(run)
            s = store(rid)
            k, latest, n, _problems = s.current()
            if expected != k:
                raise ApiError(409, 'version_conflict', f'The prompt is at version {k}', {'current': k}, headers={'ETag': f'"{k}"'})
            text, note, system_version, restored_from = text_for(latest)
            version = {'schema': 'value-review-prompt-version/1', 'run_id': rid, 'n': n, 'saved_at': ctx.clock(),
                       'saved_by': ctx.settings_now()['reviewer_name'], 'note': note, 'text': text,
                       'system_prompt_version': system_version, 'schema_ref': run['schema_ref']}
            if restored_from is not None:
                version['restored_from'] = restored_from
            try:
                s.write_version(version)
            except StorageError as error:
                raise ApiError(500, 'storage_error', str(error)) from None
            try:
                s.prune()
            except StorageError:
                pass   # tried again on the next save
        response.headers['ETag'] = f'"{n}"'
        return {key: version[key] for key in ('n', 'saved_at', 'saved_by', 'note', 'system_prompt_version')}

    @app.post(f'{api}/runs/{{rid}}/prompt/versions', status_code=201)
    def save_version(rid: str, payload: PromptIn, request: Request, response: Response):
        if not payload.text.strip():
            raise ApiError(400, 'invalid_request', 'The prompt is empty', {'pointers': [{'pointer': '/body/text', 'message': 'Type the prompt.'}]})

        def text_for(latest):
            system_version = payload.system_prompt_version or (latest['system_prompt_version'] if latest else system_prompt()[0])
            return payload.text, payload.note.strip(), system_version, None
        return new_version(rid, request, response, text_for)

    @app.post(f'{api}/runs/{{rid}}/prompt/versions/{{n}}/restore', status_code=201)
    def restore_version(rid: str, n: int, request: Request, response: Response):
        def text_for(_latest):
            old = read_version(rid, n)
            return old['text'], f'Restored from v{n}', old['system_prompt_version'], n
        return new_version(rid, request, response, text_for)

    @app.get(f'{api}/runs/{{rid}}/prompt.md')
    def export_prompt(rid: str):
        run = read_run(rid)
        view = current_view(run)
        if not view['n']:
            raise ApiError(404, 'no_prompt', 'This run has no saved prompt yet')
        return RawResponse(view['text'].encode('utf-8'), media_type='text/markdown; charset=utf-8',
                           headers={'Content-Disposition': f'attachment; filename="{run["folder"]}-prompt.md"'})
