"""Tests of the .xlsx template (BR-S08, OP-S10, OP-S11; ADR-011): round trip, what is read, what is rejected."""
import base64
import io
import sys
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review import schemas  # noqa: E402
from value_review.domain.schema_rules import check_schema  # noqa: E402
from value_review.ingest.seed_schema import seed_content  # noqa: E402
from value_review.schema_xlsx import TemplateProblems, export_xlsx, parse_xlsx  # noqa: E402
from value_review.tests.test_schemas import ONE, group  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402


def visible(c):
    """Everything the template keeps (ids are minted again on import)."""
    return [(g['name'], [(f['name'], f['type'], f['unit'], f['description'], f['allowed'], f['multiple'], f['formula'],
                          (f['family'] or {}).get('name'), (f['family'] or {}).get('member')) for f in g['fields']]) for g in c['groups']]


def workbook(rows, descriptions=None, merges=(), sheet='Schema'):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    for m in merges:
        ws.merge_cells(m)
    if descriptions is not None:
        ds = wb.create_sheet('Descriptions')
        for r in descriptions:
            ds.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class RoundTrip(unittest.TestCase):   # AC-S10
    def test_every_kept_attribute_survives(self):
        c = seed_content()
        c['groups'][3]['fields'][2].update(type='number', unit='MPa', description='0.2% offset proof stress')
        c['groups'][1]['fields'][2].update(type='category', allowed=['Solution Annealed', 'Stress Relieved'], multiple=True)
        c['groups'][2]['fields'][6].update(type='calculated', formula='Gauge length ÷ Width')
        c['groups'].append(group('g_empty', 'Notes'))
        got, summary, warnings = parse_xlsx(export_xlsx(c), 'seed.xlsx')
        self.assertEqual(visible(got), visible(c))
        self.assertEqual(summary, {'groups': 5, 'fields': 54, 'families': 1})
        self.assertEqual([w['problem'] for w in warnings], ['inputs'])   # the formula's inputs are not in the template
        self.assertEqual(schemas.errors('schema-content', got), [])
        self.assertEqual(check_schema(got), [])   # it can be saved as a version at once

    def test_the_layout_is_the_fixed_template(self):
        wb = load_workbook(io.BytesIO(export_xlsx(ONE)))
        ws = wb['Schema']
        self.assertEqual((ws['A2'].value, ws['B1'].value, ws['B2'].value), ('Reference', 'Tensile properties', 'Yield strength (MPa)'))
        self.assertEqual([c.value for c in wb['Descriptions'][1]][:3], ['Group', 'Field', 'Unit'])

    def test_the_empty_template(self):
        wb = load_workbook(io.BytesIO(export_xlsx()))
        self.assertEqual(wb['Schema']['A2'].value, 'Reference')
        self.assertEqual(parse_xlsx(export_xlsx(), 'schema-template.xlsx')[1], {'groups': 0, 'fields': 0, 'families': 0})


class Reading(unittest.TestCase):   # BR-S08
    def test_a_file_without_descriptions(self):
        data = workbook([['', 'Tensile properties', None, None, 'Composition', None, None],
                         ['Reference', 'Yield strength (MPa)', 'Total elongation (%)', 'Material', 'Cr', 'Ni content', 'Fe'],
                         ['1', '710 ± 25', '12', 'SS316', '17', '12', 'bal.']], merges=['B1:D1', 'E1:G1'])
        got, summary, warnings = parse_xlsx(data, 'mine.xlsx')
        self.assertEqual([(g['name'], [(f['name'], f['type'], f['unit']) for f in g['fields']]) for g in got['groups']], [
            ('Tensile properties', [('Yield strength', 'number', 'MPa'), ('Total elongation', 'number', '%'), ('Material', 'text', '')]),
            ('Composition', [('Cr', 'text', ''), ('Ni content', 'text', ''), ('Fe', 'text', '')])])
        self.assertEqual([f['family']['member'] for f in got['groups'][1]['fields']], ['Cr', 'Ni', 'Fe'])
        self.assertEqual(summary['families'], 1)
        self.assertEqual([w['problem'] for w in warnings], ['data_ignored'])

    def test_an_empty_cell_in_row_1_continues_the_group_on_its_left(self):
        data = workbook([['', 'G1', None, 'G2'], ['Reference', 'A', 'B', 'C']])
        got = parse_xlsx(data, 'x.xlsx')[0]
        self.assertEqual([(g['name'], [f['name'] for f in g['fields']]) for g in got['groups']], [('G1', ['A', 'B']), ('G2', ['C'])])

    def test_ids_are_minted_from_the_names_and_unique(self):
        data = workbook([['', 'G', None, 'H'], ['Reference', 'Yield strength', '2nd value', 'Yield strength']])
        got = parse_xlsx(data, 'x.xlsx')[0]
        self.assertEqual([f['field_id'] for g in got['groups'] for f in g['fields']], ['yield_strength', 'f_2nd_value', 'yield_strength_2'])

    def test_a_unit_on_a_text_field_is_left_out(self):
        data = workbook([['', 'G'], ['Reference', 'Grade (wt%)']], descriptions=[['Group', 'Field', 'Unit', 'Type'], ['G', 'Grade', '', 'Text']])
        got, _, warnings = parse_xlsx(data, 'x.xlsx')
        self.assertEqual((got['groups'][0]['fields'][0]['unit'], [w['problem'] for w in warnings]), ('', ['unit_dropped']))

    def test_another_sheet_name_is_read_with_a_warning(self):
        got, _, warnings = parse_xlsx(workbook([['', 'G'], ['Reference', 'A']], sheet='Sheet1'), 'x.xlsx')
        self.assertEqual(([f['name'] for f in got['groups'][0]['fields']], [w['problem'] for w in warnings]), (['A'], ['sheet_name']))

    def test_description_rows_without_a_group_are_ignored(self):
        data = workbook([['', 'G'], ['Reference', 'A']],
                        descriptions=[['Group', 'Field', 'Description'], [None, 'A', 'lost'], [None, None, None], ['G', 'A', 'kept']])
        got, _, warnings = parse_xlsx(data, 'x.xlsx')
        self.assertEqual(got['groups'][0]['fields'][0]['description'], 'kept')
        self.assertEqual([(w['cell'], w['problem']) for w in warnings], [('A2', 'no_group')])


class Rejected(unittest.TestCase):   # AC-S11
    def problems(self, data, name='x.xlsx'):
        with self.assertRaises(TemplateProblems) as raised:
            parse_xlsx(data, name)
        return [(p['sheet'], p['cell'], p['problem']) for p in raised.exception.problems]

    def test_not_an_xlsx(self):
        self.assertEqual(self.problems(b'a,b\n1,2\n', 'x.csv'), [(None, None, 'not_xlsx')])
        self.assertEqual(self.problems(b'not a zip'), [(None, None, 'not_xlsx')])

    def test_not_the_template(self):
        self.assertEqual(self.problems(workbook([['Name', 'Value'], ['Yield', '710']])), [('Schema', 'A2', 'no_reference')])

    def test_bad_headers(self):
        data = workbook([['', None, 'G'], ['Reference', 'A', None, 'B']])
        self.assertEqual(self.problems(data), [('Schema', 'B1', 'no_group'), ('Schema', 'C2', 'empty_field')])

    def test_too_large(self):
        self.assertEqual(self.problems(b'x' * (5 * 1024 * 1024 + 1)), [(None, None, 'too_large')])

    def test_descriptions_without_their_columns(self):
        data = workbook([['', 'G'], ['Reference', 'A']], descriptions=[['Name', 'Text'], ['A', 'x']])
        self.assertEqual(self.problems(data), [('Descriptions', 'A1', 'bad_descriptions')])

    def test_duplicate_names_in_a_group(self):
        data = workbook([['', 'G', None], ['Reference', 'Width (mm)', 'width (in)']])
        self.assertEqual(self.problems(data), [('Schema', 'C2', 'duplicate_name')])


class Api(Base):   # OP-S10, OP-S11
    def test_export_then_import_as_a_new_schema(self):
        self.client.get('/api/v1/schemas')
        r = self.client.get('/api/v1/schemas/tensile-properties/versions/1/export.xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['content-disposition'], 'attachment; filename="tensile-properties-v1.xlsx"')
        read = self.client.post('/api/v1/schemas/import', json={'filename': 'tensile.xlsx', 'data_base64': base64.b64encode(r.content).decode()})
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json()['summary'], {'groups': 4, 'fields': 54, 'families': 1})
        made = self.client.post('/api/v1/schemas', json={'name': 'Imported', 'content': read.json()['content']}).json()
        saved = self.client.post(f"/api/v1/schemas/{made['schema_id']}/versions", json={'content': made['draft']['content']}, headers={'If-Match': '"0"'})
        self.assertEqual(saved.status_code, 201, saved.text)
        v1 = self.client.get('/api/v1/schemas/tensile-properties/versions/1').json()['content']
        self.assertEqual(visible(made['draft']['content']), visible(v1))

    def test_template_download(self):
        r = self.client.get('/api/v1/schemas/template.xlsx')
        self.assertEqual((r.status_code, r.headers['content-disposition']), (200, 'attachment; filename="schema-template.xlsx"'))
        self.assertEqual(load_workbook(io.BytesIO(r.content))['Schema']['A2'].value, 'Reference')

    def test_rejected_files_create_nothing(self):
        before = self.client.get('/api/v1/schemas').json()
        r = self.client.post('/api/v1/schemas/import', json={'filename': 'x.csv', 'data_base64': base64.b64encode(b'a,b').decode()})
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']['problems'][0]['problem']),
                         (422, 'invalid_template', 'not_xlsx'))
        r = self.client.post('/api/v1/schemas/import', json={'filename': 'x.xlsx', 'data_base64': '***'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get('/api/v1/schemas').json(), before)

    def test_values_longer_than_the_schema_allows(self):
        data = workbook([['', 'G'], ['Reference', 'A' * 121]])
        r = self.client.post('/api/v1/schemas/import', json={'filename': 'x.xlsx', 'data_base64': base64.b64encode(data).decode()})
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']['problems'][0]['problem']),
                         (422, 'invalid_template', 'too_long'))

    def test_export_of_an_unknown_version(self):
        self.client.get('/api/v1/schemas')
        self.assertEqual(self.client.get('/api/v1/schemas/tensile-properties/versions/9/export.xlsx').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/schemas/nope/versions/1/export.xlsx').status_code, 404)


if __name__ == '__main__':
    unittest.main()
