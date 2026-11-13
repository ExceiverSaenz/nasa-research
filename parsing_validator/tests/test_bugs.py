"""Bug reports (OP-12, BR-19)."""
import json
import unittest

from parsing_validator.service import bugs
from parsing_validator.tests.test_service import API, Base


class BugReports(Base):
    def setUp(self):
        super().setUp()
        self.store._now = lambda: '2026-11-13T12:00:00Z'
        self.folder = self.tmp / 'annotations' / '_bug_reports'

    def post(self, body):
        return self.client.post(API + '/bug-reports', json=body)

    def files(self):
        return sorted(p.name for p in self.folder.glob('*')) if self.folder.is_dir() else []

    def test_example_without_session_data(self):
        r = self.post({'category': 'saving', 'severity': 'annoying', 'what_happened': 'The save button did nothing',
                       'context': {'included': False, 'paper': '7', 'screen': 'review'}})
        self.assertEqual((r.status_code, r.json()), (201, {'file': 'bug-saving-2026-11-13T12-00-00Z.json'}))
        report = json.loads((self.folder / r.json()['file']).read_text(encoding='utf-8'))
        self.assertEqual(report['context'], {'included': False})            # nothing else, even if the client sent it
        self.assertEqual((report['schema'], report['category'], report['severity']), (bugs.SCHEMA, 'saving', 'annoying'))
        self.assertEqual((report['created_at'], report['expected'], report['category_other']), ('2026-11-13T12:00:00Z', None, None))
        self.assertEqual(self.files(), ['bug-saving-2026-11-13T12-00-00Z.json'])

    def test_no_context_means_no_session_data(self):
        self.post({'category': 'speed', 'severity': 'minor', 'what_happened': 'slow'})
        report = json.loads((self.folder / self.files()[0]).read_text(encoding='utf-8'))
        self.assertEqual(report['context'], {'included': False})

    def test_included_context_is_whitelisted(self):
        r = self.post({'category': 'boxes', 'severity': 'blocks', 'what_happened': 'x', 'expected': 'y', 'context': {
            'included': True, 'screen': 'review', 'paper': '7', 'page': 7, 'box': 'k11', 'tool': 'parsing-validator',
            'tool_version': 'forged', 'browser': 'Chrome 130', 'last_actions': ['Open paper'] * 60,
            'window': {'w': 1280, 'h': 720}, 'text_of_the_paper': 'secret', 'extra': 1}})
        self.assertEqual(r.status_code, 201, r.text)
        report = json.loads((self.folder / r.json()['file']).read_text(encoding='utf-8'))
        context = report['context']
        self.assertEqual(set(context), {'included', 'screen', 'paper', 'page', 'box', 'tool', 'tool_version', 'last_actions',
                                        'browser', 'window'})
        self.assertNotEqual(context['tool_version'], 'forged')
        self.assertEqual(len(context['last_actions']), bugs.MAX_ACTIONS)
        self.assertEqual((context['paper'], context['page'], context['window']), ('7', 7, {'w': 1280, 'h': 720}))
        self.assertEqual(report['expected'], 'y')

    def test_other_needs_a_description_and_is_stored(self):
        self.assertEqual(self.post({'category': 'other', 'severity': 'minor', 'what_happened': 'x'}).status_code, 400)
        self.assertEqual(self.post({'category': 'other', 'category_other': '  ', 'severity': 'minor', 'what_happened': 'x'}).status_code, 400)
        r = self.post({'category': 'other', 'category_other': 'Sound', 'severity': 'minor', 'what_happened': 'x'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(json.loads((self.folder / r.json()['file']).read_text(encoding='utf-8'))['category_other'], 'Sound')
        # a description on another category is not kept
        r = self.post({'category': 'text', 'category_other': 'ignored', 'severity': 'minor', 'what_happened': 'x'})
        self.assertIsNone(json.loads((self.folder / r.json()['file']).read_text(encoding='utf-8'))['category_other'])

    def test_invalid_requests_write_nothing(self):
        good = {'category': 'saving', 'severity': 'minor', 'what_happened': 'x'}
        for change in ({'category': 'weird'}, {'severity': 'huge'}, {'what_happened': ''}, {'what_happened': '   '},
                       {'what_happened': 'x' * (bugs.LONG_TEXT + 1)}, {'expected': 5},
                       {'context': {'included': True, 'paper': '../x'}}, {'context': {'included': True, 'last_actions': [1]}},
                       {'context': {'included': True, 'window': {'w': 'a', 'h': 1}}}, {'context': {'included': True, 'page': -1}}):
            r = self.post({**good, **change})
            self.assertEqual((r.status_code, r.json()['error']['code']), (400, 'invalid_request'), change)
        missing = {k: v for k, v in good.items() if k != 'severity'}
        self.assertEqual(self.post(missing).status_code, 400)
        self.assertEqual(self.client.post(API + '/bug-reports', content='{nope').status_code, 400)
        self.assertEqual(self.client.post(API + '/bug-reports', json=[1]).status_code, 400)
        self.assertEqual(self.files(), [])

    def test_oversized_body(self):
        r = self.client.post(API + '/bug-reports', content=json.dumps({'category': 'saving', 'severity': 'minor',
                                                                       'what_happened': 'x', 'junk': 'y' * bugs.MAX_BODY}))
        self.assertEqual(r.status_code, 400)

    def test_same_second_never_overwrites(self):
        body = {'category': 'saving', 'severity': 'minor', 'what_happened': 'one'}
        names = [self.post({**body, 'what_happened': f'report {i}'}).json()['file'] for i in range(3)]
        self.assertEqual(names, ['bug-saving-2026-11-13T12-00-00Z.json', 'bug-saving-2026-11-13T12-00-00Z-2.json',
                                 'bug-saving-2026-11-13T12-00-00Z-3.json'])
        texts = [json.loads((self.folder / n).read_text(encoding='utf-8'))['what_happened'] for n in names]
        self.assertEqual(texts, ['report 0', 'report 1', 'report 2'])
        self.assertEqual(len(self.files()), 3, 'no temporary file is left behind')

    def test_unwritable_folder_is_a_storage_error(self):
        self.store.folder.mkdir(parents=True, exist_ok=True)
        self.folder.write_text('a file where the folder should be', encoding='utf-8')
        r = self.post({'category': 'saving', 'severity': 'minor', 'what_happened': 'x'})
        self.assertEqual((r.status_code, r.json()['error']['code']), (500, 'storage_error'))
        self.assertNotIn(str(self.tmp), r.text)                              # no absolute path in the message

    def test_control_characters_and_unicode_are_kept(self):
        r = self.post({'category': 'text', 'severity': 'minor', 'what_happened': 'σ ≥ 5\x01 — ok'})
        report = json.loads((self.folder / r.json()['file']).read_text(encoding='utf-8'))
        self.assertEqual(report['what_happened'], 'σ ≥ 5\x01 — ok')


if __name__ == '__main__':
    unittest.main()
