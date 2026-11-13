"""The empty decision state built from an original (``source = original`` of OP-03, AC-02)."""


def blank_block(block):
    """Decisions of one MinerU block before the user has touched it."""
    return {
        'status': 'pending',
        'tag': {'value': block['type'], 'predicted': block['type'], 'other_label': None},
        'content': {'status': None, 'error_types': [], 'error_other': None, 'text': None, 'latex': [], 'table': None},
        'parts': {'order': [p['key'] for p in block.get('parts', [])], 'state': {}, 'detached': []},
        'delete_reasons': [], 'delete_other': None,
        'origin': None, 'adjusted': False, 'note': '', 'layer_issues': [],
    }


def blank_state(original):
    """Every block pending, reading order equal to MinerU's ``index`` order, no content edits."""
    pages = {}
    for page in original['pages']:
        ordered = sorted(page['blocks'], key=lambda b: b['index'])
        pages[str(page['index'])] = {
            'reading_order': [b['id'] for b in ordered],
            'blocks': {b['id']: blank_block(b) for b in ordered},
        }
    return {'reviewed': {'marked': False, 'marked_at': None}, 'next_new_id': 1, 'pages': pages}
