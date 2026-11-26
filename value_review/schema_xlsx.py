"""The fixed .xlsx template of a schema (BR-S08, OP-S10, OP-S11; ADR-011).

Sheet "Schema": A2 is "Reference"; from column B, row 1 holds the group name over its fields (merged cells) and row 2
each field's name with the unit in parentheses ("Yield strength (MPa)"). Data rows below are allowed and ignored.
Sheet "Descriptions" (optional): one row per field with Group, Field, Unit, Description, Type, Allowed values ("; "),
Multiple (yes/no), Formula, Family and Member; a group without fields has a row with an empty Field.

Uploaded workbooks are opened with ``data_only=True``: formulas are read as their cached text and never evaluated, and
macros are never run. Only .xlsx is accepted.
"""
import io
import re
import zipfile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from .domain.schema_rules import same_name
from .storage.schemas import empty_content

SCHEMA_SHEET, DESC_SHEET = 'Schema', 'Descriptions'
DESC_COLUMNS = ['Group', 'Field', 'Unit', 'Description', 'Type', 'Allowed values', 'Multiple', 'Formula', 'Family', 'Member']
TYPE_NAMES = {'number': 'Number', 'category': 'Category', 'text': 'Text', 'calculated': 'Calculated'}
TYPE_IDS = {v.lower(): k for k, v in TYPE_NAMES.items()} | {k: k for k in TYPE_NAMES}
ELEMENTS = set('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr '
               'Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt '
               'Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr'.split())
UNIT = re.compile(r'^(.*?)\s*\(([^()]*)\)\s*$')
MAX_BYTES = 5 * 1024 * 1024
NAVY, SOFT = '0B3D91', 'E6EEFB'


class TemplateProblems(Exception):
    """The file is not the template: a list of {sheet, cell, problem, message}."""
    def __init__(self, problems):
        super().__init__(problems[0]['message'] if problems else 'Not the template')
        self.problems = problems


def _problem(sheet, cell, code, message):
    return {'sheet': sheet, 'cell': cell, 'problem': code, 'message': message}


# --- export ------------------------------------------------------------------------------------
def export_xlsx(content=None):
    """The workbook of a schema content as bytes; with no content, the empty template."""
    content = content or empty_content()
    wb = Workbook()
    ws = wb.active
    ws.title = SCHEMA_SHEET
    head = Font(bold=True, color='FFFFFF')
    ws['A2'] = 'Reference'
    ws['A2'].font = Font(bold=True)
    ws.column_dimensions['A'].width = 16
    col = 2
    for group in content['groups']:
        if not group['fields']:
            continue
        first = col
        for field in group['fields']:
            unit = field['unit'] if field['type'] == 'number' and field['unit'] else ''
            cell = ws.cell(row=2, column=col, value=f"{field['name']} ({unit})" if unit else field['name'])
            cell.font = Font(bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            ws.column_dimensions[get_column_letter(col)].width = max(14, min(40, len(cell.value) + 2))
            col += 1
        top = ws.cell(row=1, column=first, value=group['name'])
        top.font, top.fill = head, PatternFill('solid', fgColor=NAVY)
        if col - 1 > first:
            ws.merge_cells(start_row=1, start_column=first, end_row=1, end_column=col - 1)
    ws.freeze_panes = 'B3'

    ds = wb.create_sheet(DESC_SHEET)
    ds.append(DESC_COLUMNS)
    for c in ds[1]:
        c.font, c.fill = Font(bold=True), PatternFill('solid', fgColor=SOFT)
    for group in content['groups']:
        if not group['fields']:
            ds.append([group['name']] + [''] * (len(DESC_COLUMNS) - 1))
        for f in group['fields']:
            fam = f['family'] or {}
            ds.append([group['name'], f['name'], f['unit'] if f['type'] == 'number' else '', f['description'], TYPE_NAMES[f['type']],
                       '; '.join(f['allowed']), 'yes' if f['multiple'] else 'no', f['formula'], fam.get('name', ''), fam.get('member', '')])
    for letter, width in zip('ABCDEFGHIJ', (28, 28, 10, 60, 12, 30, 10, 30, 22, 10), strict=True):
        ds.column_dimensions[letter].width = width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# --- import ------------------------------------------------------------------------------------
def _text(value):
    return '' if value is None else ' '.join(str(value).split())


def _slug(name, prefix, taken):
    base = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:56] or prefix
    if not base[0].isalpha():
        base = f'{prefix}_{base}'[:56]
    sid, k = base, 2
    while sid in taken:
        sid, k = f'{base[:52]}_{k}', k + 1
    taken.add(sid)
    return sid


def _open(data, filename):
    if not filename.lower().endswith('.xlsx'):
        raise TemplateProblems([_problem(None, None, 'not_xlsx', 'Only .xlsx files made from the template can be imported.')])
    if len(data) > MAX_BYTES:
        raise TemplateProblems([_problem(None, None, 'too_large', 'The file is larger than 5 MB.')])
    try:
        return load_workbook(io.BytesIO(data), data_only=True)   # merged cells need the full reader; formulas stay unevaluated
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError, ValueError):
        raise TemplateProblems([_problem(None, None, 'not_xlsx', 'The file is not a readable .xlsx workbook.')]) from None


def _descriptions(wb, problems, warnings):
    """{(group, field): row dict} from the Descriptions sheet, and the groups it lists, in order."""
    if DESC_SHEET not in wb.sheetnames:
        return {}, []
    ds = wb[DESC_SHEET]
    rows = list(ds.iter_rows(values_only=True))
    if not rows:
        return {}, []
    header = [_text(v).lower() for v in rows[0]]
    if 'group' not in header or 'field' not in header:
        problems.append(_problem(DESC_SHEET, 'A1', 'bad_descriptions', 'The Descriptions sheet needs the columns Group and Field in row 1.'))
        return {}, []
    at = {name.lower(): header.index(name.lower()) for name in DESC_COLUMNS if name.lower() in header}
    out, groups = {}, []
    for i, row in enumerate(rows[1:], start=2):
        cells = {key: _text(row[i]) if i < len(row) else '' for key, i in at.items()}
        get = cells.get
        group, field = get('group', ''), get('field', '')
        if not group and not field:
            continue
        if not group:
            warnings.append(_problem(DESC_SHEET, f'A{i}', 'no_group', 'A row without a group was ignored.'))
            continue
        if same_name(group) not in [same_name(g) for g in groups]:
            groups.append(group)
        if field:
            out[(same_name(group), same_name(field))] = cells
    return out, groups


def parse_xlsx(data, filename):
    """(content, summary, warnings) of a template file; raises TemplateProblems when it is not the template."""
    wb = _open(data, filename)
    problems, warnings = [], []
    if SCHEMA_SHEET not in wb.sheetnames:
        ws = wb.worksheets[0]
        warnings.append(_problem(ws.title, None, 'sheet_name', f'No sheet named "{SCHEMA_SHEET}"; the first sheet, "{ws.title}", was read.'))
    else:
        ws = wb[SCHEMA_SHEET]
    if same_name(_text(ws['A2'].value)) != 'reference':
        problems.append(_problem(ws.title, 'A2', 'no_reference', 'Cell A2 must say "Reference": this is not the schema template.'))
    merged = {}
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= 1 <= rng.max_row:
            for c in range(rng.min_col, rng.max_col + 1):
                merged[c] = ws.cell(row=rng.min_row, column=rng.min_col).value
    last = max((c.column for c in ws[2] if _text(c.value)), default=1)
    descs, desc_groups = _descriptions(wb, problems, warnings)

    columns, group = [], ''
    for col in range(2, last + 1):
        letter = get_column_letter(col)
        top = _text(merged.get(col, ws.cell(row=1, column=col).value))
        group = top or group
        header = _text(ws.cell(row=2, column=col).value)
        if not group:
            problems.append(_problem(ws.title, f'{letter}1', 'no_group', 'The first field has no group above it in row 1.'))
            group = '?'
        if not header:
            problems.append(_problem(ws.title, f'{letter}2', 'empty_field', 'A field has no name in row 2.'))
            continue
        columns.append((group, header, letter))
    if problems:
        raise TemplateProblems(problems)

    # groups in the order they appear: the Schema sheet first, then groups listed only in Descriptions
    order = []
    for g, _, _ in columns:
        if same_name(g) not in [same_name(x) for x in order]:
            order.append(g)
    for g in desc_groups:
        if same_name(g) not in [same_name(x) for x in order]:
            order.append(g)
    taken = set()
    groups = {same_name(g): {'group_id': _slug(g, 'g', taken), 'name': g, 'fields': []} for g in order}
    for g, header, letter in columns:
        d = descs.get((same_name(g), same_name(header)))
        if d is not None:
            name, unit = header, d.get('unit', '')
        else:
            m = UNIT.match(header)
            name, unit = (m.group(1), m.group(2).strip()) if m and m.group(1) else (header, '')
            d = descs.get((same_name(g), same_name(name)), {})
        target = groups[same_name(g)]
        if same_name(name) in [same_name(f['name']) for f in target['fields']]:
            problems.append(_problem(ws.title, f'{letter}2', 'duplicate_name', f'"{name}" appears twice in the group "{g}".'))
            continue
        kind = TYPE_IDS.get(d.get('type', '').lower(), 'number' if unit else 'text')
        if unit and kind != 'number':
            warnings.append(_problem(ws.title, f'{letter}2', 'unit_dropped', f'"{name}" is {TYPE_NAMES[kind]}, so its unit "{unit}" was left out.'))
            unit = ''
        allowed = [a for a in dict.fromkeys(x.strip() for x in d.get('allowed values', '').split(';')) if a] if kind == 'category' else []
        formula = d.get('formula', '') if kind == 'calculated' else ''
        if kind == 'calculated':
            warnings.append(_problem(ws.title, f'{letter}2', 'inputs', f'Choose which fields the formula of "{name}" reads.'))
        family = None
        if d.get('family') and d.get('member'):
            family = {'family_id': _slug(d['family'], 'family', set()), 'name': d['family'], 'member': d['member']}
        target['fields'].append({
            'field_id': _slug(name, 'f', taken), 'name': name, 'description': d.get('description', ''), 'type': kind,
            'unit': unit[:40], 'allowed': allowed[:200], 'multiple': kind == 'category' and d.get('multiple', '').lower() in ('yes', 'true', '1'),
            'formula': formula[:500], 'inputs': [], 'family': family,
        })
    if problems:
        raise TemplateProblems(problems)
    content = {'schema': 'value-review-schema/1', 'description': '', 'groups': [groups[same_name(g)] for g in order]}
    _families(content)
    rows = sum(1 for r in ws.iter_rows(min_row=3, values_only=True) if any(v not in (None, '') for v in r))
    if rows:
        warnings.append(_problem(ws.title, 'A3', 'data_ignored', f'{rows} data rows below the header were ignored.'))
    families = {f['family']['family_id'] for g in content['groups'] for f in g['fields'] if f['family']}
    summary = {'groups': len(content['groups']), 'fields': sum(len(g['fields']) for g in content['groups']), 'families': len(families)}
    return content, summary, warnings


def _families(content):
    """Fields of a group named by chemical-element symbols (alone or with " content") form a family named after the
    group, when the file did not say so and there are at least three of them (BR-S08)."""
    for group in content['groups']:
        loose = [f for f in group['fields'] if f['family'] is None and _element(f['name'])]
        if len(loose) >= 3:
            fid = _slug(group['name'], 'family', set())
            for f in loose:
                f['family'] = {'family_id': fid, 'name': group['name'], 'member': _element(f['name'])}


def _element(name):
    word = name.split(' ')[0] if name else ''
    rest = name[len(word):].strip().lower()
    return word if word in ELEMENTS and rest in ('', 'content', 'wt%', 'wt.%', 'at%') else ''
