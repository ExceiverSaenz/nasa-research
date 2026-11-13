"""The decision rules a "Save changes" must satisfy (contract OP-07), plus the structural checks they rest on.

``validate_state`` returns every violation (they are listed together, never one at a time). Drafts are not
validated against these rules (OP-06): a user may save a draft in the middle of an edit.

Each violation is ``{rule, code, page, block, message}``. ``rule`` is the OP-07 number (1 to 8) or ``0`` for a
structural check the rules rely on (types, enumerations, table shape). A rejected block with no replacement is
allowed (open product decision).
"""
import re

from .catalogs import BLOCK_STATUSES, CONTENT_STATUSES, LAYERS, OTHER

NEW_ID = re.compile(r'^n([0-9]+)$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


class DecisionRulesViolation(Exception):
    def __init__(self, violations):
        super().__init__(f'{len(violations)} decision rule violation(s)')
        self.violations = violations


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


class _Checker:
    def __init__(self, original, settings):
        self.pages = {str(p['index']): p for p in original['pages']}
        self.kinds = {t['name']: t['kind'] for t in settings['tags']}
        self.errors = set(settings['error_types'])
        self.reasons = set(settings['delete_reasons'])
        self.violations = []

    def add(self, rule, code, message, page=None, block=None):
        self.violations.append({'rule': rule, 'code': code, 'page': page, 'block': block, 'message': message})

    # --- whole state -----------------------------------------------------------
    def run(self, state):
        counter = state.get('next_new_id')
        for key in state['pages']:
            if key not in self.pages:
                self.add(1, 'page_unknown', f'Page {key} does not exist in the original', page=key)
        for key in self.pages:
            if key not in state['pages']:
                self.add(1, 'page_missing', f'Page {key} has no decisions', page=key)
        for key, page in state['pages'].items():
            if key in self.pages:
                self.page(key, page, self.pages[key], counter)
        self.violations.sort(key=lambda v: (int(v['page']) if v['page'] and str(v['page']).isdigit() else -1,
                                            v['block'] or '', v['rule'], v['code']))
        return self.violations

    # --- one page --------------------------------------------------------------
    def page(self, key, page, original, counter):
        originals = {b['id']: b for b in original['blocks']}
        blocks = page.get('blocks', {})
        for bid in originals:
            if bid not in blocks:
                self.add(1, 'block_missing', f'Block {bid} of the original has no decisions', key, bid)
        for bid, block in blocks.items():
            if bid in originals:
                if block.get('origin') is not None:
                    self.add(1, 'origin_on_original_block', 'A MinerU block cannot declare an origin', key, bid)
            else:
                self.new_block(key, bid, block, blocks, counter)
            self.block(key, bid, block, originals.get(bid))
        self.order(key, page, blocks)

    def new_block(self, key, bid, block, blocks, counter):
        origin = block.get('origin')
        match = NEW_ID.match(bid)
        if not isinstance(origin, dict):
            self.add(1, 'block_unknown', f'Block {bid} is not in the original and declares no origin', key, bid)
            return
        if not match:
            self.add(1, 'new_id_malformed', f'Block {bid}: ids of new blocks are n<number>', key, bid)
        elif not isinstance(counter, int) or int(match.group(1)) >= counter:
            self.add(1, 'new_id_not_counted', f'Block {bid}: next_new_id ({counter}) must be greater than every n<number>', key, bid)
        if origin.get('kind') not in ('drawn', 'detached'):
            self.add(1, 'origin_kind', f'Block {bid}: origin.kind must be drawn or detached', key, bid)
        box = origin.get('bbox_pct')
        if not (isinstance(box, dict) and all(isinstance(box.get(k), (int, float)) and not isinstance(box.get(k), bool) for k in 'xywh')
                and 0 <= box['x'] <= 100 and 0 <= box['y'] <= 100 and box['w'] > 0 and box['h'] > 0
                and box['x'] + box['w'] <= 100.001 and box['y'] + box['h'] <= 100.001):
            self.add(1, 'origin_box', f'Block {bid}: origin.bbox_pct must be a box inside the page', key, bid)
        for field in ('replaces', 'from_block'):
            target = origin.get(field)
            if target is not None and target not in blocks:
                self.add(1, 'origin_reference', f'Block {bid}: origin.{field} points to {target}, which is not on the page', key, bid)
        if origin.get('kind') == 'detached' and (_blank(origin.get('from_block')) or _blank(origin.get('part_key'))):
            self.add(1, 'origin_detached', f'Block {bid}: a detached block needs from_block and part_key', key, bid)

    def order(self, key, page, blocks):
        order = page.get('reading_order')
        if not isinstance(order, list) or not all(isinstance(i, str) for i in order):
            self.add(1, 'reading_order_shape', 'reading_order must be a list of block ids', key)
            return
        expected = {bid for bid, b in blocks.items() if b.get('status') != 'deleted'}
        seen = set()
        for bid in order:
            if bid in seen:
                self.add(1, 'reading_order_duplicate', f'Block {bid} appears twice in the reading order', key, bid)
            seen.add(bid)
            if bid not in blocks:
                self.add(1, 'reading_order_unknown', f'Block {bid} in the reading order does not exist', key, bid)
            elif bid not in expected:
                self.add(1, 'reading_order_deleted', f'Deleted block {bid} must not be in the reading order', key, bid)
        for bid in sorted(expected - seen):
            self.add(1, 'reading_order_missing', f'Block {bid} is missing from the reading order', key, bid)

    # --- one block -------------------------------------------------------------
    def block(self, key, bid, block, original):
        add = lambda rule, code, message: self.add(rule, code, message, key, bid)  # noqa: E731
        status = block.get('status')
        if status not in BLOCK_STATUSES:
            add(0, 'status_invalid', f'status must be one of {", ".join(BLOCK_STATUSES)}')
        tag = block.get('tag') or {}
        value = tag.get('value')
        if value == OTHER:
            if _blank(tag.get('other_label')):
                add(2, 'tag_other_label', 'Tag Other needs a non-empty other_label')
        elif value not in self.kinds:
            add(2, 'tag_unknown', f'Tag {value!r} is not in the settings catalog')
        if original is not None and tag.get('predicted') != original['type']:
            add(2, 'tag_predicted', f"predicted must be the MinerU type ({original['type']})")
        kind = 'text' if value == OTHER else self.kinds.get(value)
        content = block.get('content') or {}
        self.content(add, content, status, kind)
        self.delete(add, block, status)
        self.layers(add, block.get('layer_issues'))
        parts = block.get('parts') or {}
        known = {p['key'] for p in (original or {}).get('parts', [])}
        order = parts.get('order', [])
        if original is not None and (len(set(order)) != len(order) or not set(order) <= known):
            add(0, 'parts_order', 'parts.order must list each part of the block at most once')
        if not isinstance(block.get('note', ''), str):
            add(0, 'note_type', 'note must be text')

    def content(self, add, content, status, kind):
        cstatus = content.get('status')
        if cstatus not in CONTENT_STATUSES:
            add(0, 'content_status_invalid', 'content.status must be correct, wrong or null')
        types = content.get('error_types') or []
        for t in types:
            if t != OTHER and t not in self.errors:
                add(3, 'error_type_unknown', f'Error type {t!r} is not in the settings catalog')
        if cstatus == 'wrong':
            if not types:
                add(3, 'error_type_required', 'content.status wrong requires at least one error type')
            if OTHER in types and _blank(content.get('error_other')):
                add(3, 'error_other_required', 'Error type Other requires error_other')
        text, latex, table = content.get('text'), content.get('latex') or [], content.get('table')
        if (text is not None or latex) and kind != 'text':
            add(5, 'text_not_allowed', 'Text and LaTeX edits are only for text-capable tags')
        if table is not None and kind != 'table':
            add(5, 'table_not_allowed', 'Table edits are only for the table tag')
        if status in ('deleted', 'rejected') and (text is not None or latex or table is not None):
            add(6, 'content_on_dead_block', f'A {status} block carries no text, table or LaTeX edits')
        if cstatus == 'correct' and (text is not None or types or table is not None):
            add(8, 'content_correct_with_edits', 'content.status correct carries no text, error types or table')
        for i, item in enumerate(latex):
            if not (isinstance(item, dict) and isinstance(item.get('source'), str)):
                add(0, 'latex_shape', f'latex[{i}] needs a text source')
        if table is not None:
            self.table(add, table)

    @staticmethod
    def table(add, table):
        cells = table.get('cells') if isinstance(table, dict) else None
        ok = isinstance(cells, list) and cells and all(isinstance(r, list) and r for r in cells) and isinstance(table.get('html'), str)
        if ok:
            ok = len({len(r) for r in cells}) == 1 and all(
                isinstance(c, dict) and isinstance(c.get('v'), str) and isinstance(c.get('rs'), int) and isinstance(c.get('cs'), int)
                and c['rs'] >= 1 and c['cs'] >= 1 for r in cells for c in r)
        if not ok:
            add(0, 'table_shape', 'content.table needs a rectangular grid of cells {v, rs, cs, hidden} and an html string')

    def delete(self, add, block, status):
        reasons = block.get('delete_reasons') or []
        for r in reasons:
            if r != OTHER and r not in self.reasons:
                add(4, 'delete_reason_unknown', f'Delete reason {r!r} is not in the settings catalog')
        if status == 'deleted':
            if not reasons:
                add(4, 'delete_reason_required', 'A deleted block requires at least one delete reason')
            if OTHER in reasons and _blank(block.get('delete_other')):
                add(4, 'delete_other_required', 'Delete reason Other requires delete_other')

    def layers(self, add, issues):
        for i, issue in enumerate(issues or []):
            where = f'layer_issues[{i}]'
            layer = issue.get('layer')
            if layer not in LAYERS:
                add(7, 'layer_invalid', f'{where}: layer must be one of {", ".join(LAYERS)}')
            kinds = issue.get('kinds') or []
            if not kinds:
                add(7, 'layer_kinds_required', f'{where}: kinds must not be empty')
            if OTHER in kinds and _blank(issue.get('other')):
                add(7, 'layer_other_required', f'{where}: kind Other requires other')
            ref = issue.get('ref')
            if ref is None:
                if layer not in ('missing', 'other'):
                    add(7, 'layer_ref_required', f'{where}: a {layer} issue needs the sealed reference of its element')
            elif not (isinstance(ref, dict) and SHA256.match(str(ref.get('sha256', ''))) and isinstance(ref.get('pointer'), str)):
                add(7, 'layer_ref_invalid', f'{where}: ref needs a sha256 and a pointer')


def validate_state(state, original, settings):
    """All violations of ``state`` against the original and the settings catalogs (empty list when valid)."""
    return _Checker(original, settings).run(state)


def check_state(state, original, settings):
    violations = validate_state(state, original, settings)
    if violations:
        raise DecisionRulesViolation(violations)
