"""Exports (OP-09 to OP-11): built from saved reviews only, never from drafts (BR-11). Nothing here writes to disk.

Pure functions over a review (and its original) so they can be tested without the service.
"""
import copy
import csv
import io
import json
import re
import zipfile
from bisect import bisect_left

from ..domain.catalogs import LAYERS, OTHER

REASONS = ('rejected', 'deleted', 'wrong tag', 'content wrong', 'reading order changed', 'part moved out', 'layer issue', 'note')
COLUMNS = ('paper', 'page', 'box', 'reason', 'tag_predicted', 'tag_final', 'error_types', 'delete_reasons', 'layer_issue',
           'note', 'auto_accepted')
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
FORMULA_START = ('=', '+', '-', '@')
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def symbols(text):
    """BR-21: control characters (except tab, line feed, carriage return) become U+2400 plus their code."""
    return CONTROL.sub(lambda m: chr(0x2400 + ord(m.group())), text)


# --- OP-09 -----------------------------------------------------------------------------
def auto_accept(review):
    """The export copy of a review: every ``pending`` block becomes ``accepted`` with ``auto_accepted: true`` (BR-10)."""
    out = copy.deepcopy(review)
    for page in out['pages'].values():
        for block in page['blocks'].values():
            if block['status'] == 'pending':
                block['status'] = 'accepted'
                block['auto_accepted'] = True
    return out


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False).encode('utf-8') + b'\n'


def build_zip(items):
    """``items``: ``[(paper, original_bytes, review_dict)]`` in paper order. Deterministic bytes for the same input."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for paper, original, review in items:
            for name, data in ((f'{paper}.original.json', original), (f'{paper}.review.json', dumps(auto_accept(review)))):
                info = zipfile.ZipInfo(name, ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
    return buffer.getvalue()


# --- OP-10 -----------------------------------------------------------------------------
def _label(value, other):
    return f'{OTHER}: {other}' if value == OTHER and other else value


def _moved(page, original_page):
    """Blocks whose place in the reading order differs from MinerU's: those outside the longest run that keeps it."""
    rank = {b['id']: i for i, b in enumerate(sorted(original_page['blocks'], key=lambda b: b['index']))}
    actual = [b for b in page['reading_order'] if b in rank]
    tails, links, tail_at = [], [-1] * len(actual), []
    for i, bid in enumerate(actual):
        pos = bisect_left(tails, rank[bid])
        if pos == len(tails):
            tails.append(rank[bid])
            tail_at.append(i)
        else:
            tails[pos], tail_at[pos] = rank[bid], i
        links[i] = tail_at[pos - 1] if pos else -1
    keep, at = set(), tail_at[-1] if tail_at else -1
    while at != -1:
        keep.add(actual[at])
        at = links[at]
    return [b for b in actual if b not in keep]


def _sort_key(entry):
    page, bid, reason = entry
    return (page, 0 if bid.startswith('k') else 1, int(re.sub(r'\D', '', bid) or 0), bid, REASONS.index(reason))


def rows(review, original):
    """One row per decision that is not clean (OP-10); a block with several decisions yields several rows."""
    paper = review['paper']
    pages = {str(p['index']): p for p in original['pages']}
    found = {}   # (page index, block id, reason) -> block
    for key, page in review['pages'].items():
        blocks = page['blocks']
        for bid, block in blocks.items():
            origin, status, tag = block.get('origin'), block['status'], block['tag']
            for reason, present in (
                    ('rejected', status == 'rejected'),
                    ('deleted', status == 'deleted'),
                    ('wrong tag', origin is None and status != 'deleted' and tag['value'] != tag['predicted']),
                    ('content wrong', block['content']['status'] == 'wrong'),
                    ('layer issue', bool(block.get('layer_issues'))),
                    ('note', bool((block.get('note') or '').strip()))):
                if present:
                    found[(int(key), bid, reason)] = block
            if origin and origin.get('kind') == 'detached' and origin.get('from_block') in blocks:
                found[(int(key), origin['from_block'], 'part moved out')] = blocks[origin['from_block']]
        if key in pages:
            for bid in _moved(page, pages[key]):
                found[(int(key), bid, 'reading order changed')] = blocks[bid]
    out = []
    for (page, bid, reason) in sorted(found, key=_sort_key):
        block = found[(page, bid, reason)]
        tag, content = block['tag'], block['content']
        out.append({
            'paper': paper, 'page': str(page + 1), 'box': bid, 'reason': reason,
            'tag_predicted': tag.get('predicted') or '', 'tag_final': _label(tag['value'], tag.get('other_label')),
            'error_types': '; '.join(_label(t, content.get('error_other')) for t in content.get('error_types') or []),
            'delete_reasons': '; '.join(_label(t, block.get('delete_other')) for t in block.get('delete_reasons') or []),
            'layer_issue': '; '.join(f"{i['layer']}: " + ', '.join(_label(k, i.get('other')) for k in i['kinds'])
                                     for i in block.get('layer_issues') or []),
            'note': (block.get('note') or '').strip(),
            'auto_accepted': 'true' if block['status'] == 'pending' else 'false',
            '_page_index': page})
    return out


def _cell(value):
    text = symbols(str(value))
    return "'" + text if text.startswith(FORMULA_START + ('\t', '\r')) else text


def _csv(header, body):
    out = io.StringIO(newline='')
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(header)
    for row in body:
        writer.writerow([_cell(v) for v in row])
    return b'\xef\xbb\xbf' + out.getvalue().encode('utf-8')


def summary_csv(all_rows):
    return _csv(COLUMNS, [[r[c] for c in COLUMNS] for r in all_rows])


def _md(value):
    return symbols(str(value)).replace('\\', '\\\\').replace('|', '\\|').replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')


def summary_markdown(papers):
    """``papers``: ``[(paper, title, rows)]``. One table per paper; the page cell links to that page (route to be fixed
    with the front end: ``/#/papers/<n>/pages/<index>``)."""
    lines = ['# Parsing Validator summary', '']
    for paper, title, body in papers:
        lines += [f'## Paper {paper}' + (f' · {_md(title)}' if title else ''), '']
        if not body:
            lines += ['No decisions to report.', '']
            continue
        lines += ['| ' + ' | '.join(COLUMNS) + ' |', '|' + '---|' * len(COLUMNS)]
        for r in body:
            cells = [f"[{r['page']}](/#/papers/{r['paper']}/pages/{r['_page_index']})" if c == 'page' else _md(r[c])
                     for c in COLUMNS]
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines.append('')
    return ('\n'.join(lines)).encode('utf-8')


# --- OP-11 -----------------------------------------------------------------------------
def _counted(counter, catalog=()):
    labels = {**{c: 0 for c in catalog}, **counter}
    return [{'label': k, 'count': v} for k, v in sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))]


def stats(reviews, settings):
    """Counts over saved reviews (drafts are never counted)."""
    kpi = {'wrong_or_deleted': 0, 'tags_corrected': 0, 'boxes_drawn': 0, 'tables_edited': 0, 'layer_issues': 0}
    errors, reasons, layers, corrections, other = {}, {}, {}, {}, {}

    def bump(counter, key, step=1):
        counter[key] = counter.get(key, 0) + step

    def free(kind, label):
        if label and label.strip():
            bump(other, (kind, label.strip()))

    for review in reviews:
        for page in review['pages'].values():
            for block in page['blocks'].values():
                content, tag = block['content'], block['tag']
                kpi['wrong_or_deleted'] += content['status'] == 'wrong' or block['status'] == 'deleted'
                kpi['boxes_drawn'] += bool(block.get('origin') and block['origin'].get('kind') == 'drawn')
                kpi['tables_edited'] += content.get('table') is not None
                if block.get('origin') is None and block['status'] != 'deleted' and tag['value'] != tag['predicted']:
                    kpi['tags_corrected'] += 1
                    bump(corrections, (tag['predicted'], tag['value']))
                    if tag['value'] == OTHER:
                        free('tag', tag.get('other_label'))
                for t in content.get('error_types') or []:
                    bump(errors, t)
                    if t == OTHER:
                        free('error_type', content.get('error_other'))
                for t in block.get('delete_reasons') or []:
                    bump(reasons, t)
                    if t == OTHER:
                        free('delete_reason', block.get('delete_other'))
                for issue in block.get('layer_issues') or []:
                    kpi['layer_issues'] += 1
                    bump(layers, issue['layer'])
                    if OTHER in issue['kinds']:
                        free('layer_issue', issue.get('other'))
    return {
        'reviews_counted': len(reviews), 'kpis': kpi,
        'error_types': _counted(errors, list(settings['error_types']) + [OTHER]),
        'tag_corrections': [{'from': a, 'to': b, 'count': n}
                            for (a, b), n in sorted(corrections.items(), key=lambda kv: (-kv[1], kv[0]))],
        'delete_reasons': _counted(reasons, list(settings['delete_reasons']) + [OTHER]),
        'layer_issues_by_layer': _counted(layers, LAYERS),
        'other_classifications': [{'kind': k, 'label': label, 'count': n}
                                  for (k, label), n in sorted(other.items(), key=lambda kv: (-kv[1], kv[0]))],
    }


def stats_csv(result):
    body = [['kpi', name, '', '', n] for name, n in result['kpis'].items()]
    for section in ('error_types', 'delete_reasons', 'layer_issues_by_layer'):
        body += [[section, item['label'], '', '', item['count']] for item in result[section]]
    body += [['tag_correction', '', item['from'], item['to'], item['count']] for item in result['tag_corrections']]
    body += [['other_' + item['kind'], item['label'], '', '', item['count']] for item in result['other_classifications']]
    return _csv(('section', 'label', 'from', 'to', 'count'), body)
