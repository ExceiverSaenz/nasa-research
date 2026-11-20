"""Default catalogs (the editable lists of Settings) and the fixed marker ``Other``.

The 13 tag names are the final MinerU types found in the 23 papers (coverage audit, finding on the tag
catalog); ``kind`` says what content a tag can carry: ``text`` (text, LaTeX), ``figure`` (none) or ``table``.
"""
OTHER = 'Other'  # fixed in every list; the front end may display it differently, the stored value is this one

LAYERS = ('layout', 'ocr', 'cells', 'missing', 'other')
BLOCK_STATUSES = ('pending', 'accepted', 'rejected', 'deleted')
CONTENT_STATUSES = ('correct', 'wrong', None)

DEFAULT_SETTINGS = {
    'tags': [
        {'name': 'doc_title', 'kind': 'text'}, {'name': 'paragraph_title', 'kind': 'text'},
        {'name': 'text', 'kind': 'text'}, {'name': 'ref_text', 'kind': 'text'},
        {'name': 'equation', 'kind': 'text'}, {'name': 'aside_text', 'kind': 'text'},
        {'name': 'header', 'kind': 'text'}, {'name': 'footer', 'kind': 'text'},
        {'name': 'page_number', 'kind': 'text'}, {'name': 'page_footnote', 'kind': 'text'},
        {'name': 'image', 'kind': 'figure'}, {'name': 'chart', 'kind': 'figure'},
        {'name': 'table', 'kind': 'table'},
    ],
    'error_types': ['Punctuation', 'Missing content', 'Extra content', 'Wrong characters', 'Math / LaTeX',
                    'Formatting', 'Missing rows or columns', 'Merged cells'],
    'delete_reasons': ['False detection', 'Duplicate box', 'Page decoration', 'Scan noise', 'Overlaps another box'],
}
