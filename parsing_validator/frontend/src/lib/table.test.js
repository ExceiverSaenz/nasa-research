import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as t from './table.js';

const text = (cells) => cells.map((row) => row.map((c) => (c.hidden ? '·' : c.v)));
const SIMPLE = '<table><tr><th>Property</th><th>CG</th><th>UFG</th></tr><tr><td>Hardness</td><td>130</td><td>140</td></tr></table>';
const MERGED =
  '<table><tr><th rowspan="2">Property</th><th colspan="2">Steel</th></tr><tr><th>CG</th><th>UFG</th></tr>' +
  '<tr><td>Hardness</td><td>130</td><td>140</td></tr></table>';

test('a simple table becomes a rectangular matrix and goes back to the same HTML', () => {
  const cells = t.parseHtmlTable(SIMPLE);
  assert.deepEqual(text(cells), [['Property', 'CG', 'UFG'], ['Hardness', '130', '140']]);
  assert.deepEqual(cells[0][0], { v: 'Property', rs: 1, cs: 1, hidden: false });
  assert.equal(t.gridToHtml(cells), SIMPLE);
});

test('positions respect the rowspan and colspan of the cells before, and covered cells are hidden', () => {
  const cells = t.parseHtmlTable(MERGED);
  assert.deepEqual(text(cells), [['Property', 'Steel', '·'], ['·', 'CG', 'UFG'], ['Hardness', '130', '140']]);
  assert.deepEqual([cells[0][0].rs, cells[0][1].cs], [2, 2]);
  assert.ok(cells.every((row) => row.length === 3), 'every row has the same length');
  // only the first row is a header in the generated HTML (spec), whatever MinerU used
  assert.equal(
    t.gridToHtml(cells),
    '<table><tr><th rowspan="2">Property</th><th colspan="2">Steel</th></tr><tr><td>CG</td><td>UFG</td></tr>' +
      '<tr><td>Hardness</td><td>130</td><td>140</td></tr></table>',
  );
});

test('text is decoded when read and escaped when written; inner markup and breaks are flattened', () => {
  const cells = t.parseHtmlTable('<table><tr><td>a &amp; b &lt; c<br/>d <sub>2</sub></td><td>&nbsp;x&#39;y</td></tr></table>');
  assert.deepEqual(text(cells), [['a & b < c d 2', "x'y"]]);
  assert.equal(t.gridToHtml(t.setCell(cells, 0, 0, '<b> & "q"')), '<table><tr><th>&lt;b&gt; &amp; &quot;q&quot;</th><th>x\'y</th></tr></table>');
});

test('a table without rows gives one empty cell, and a rowspan past the end is clamped', () => {
  assert.deepEqual(text(t.parseHtmlTable('')), [['']]);
  assert.deepEqual(text(t.parseHtmlTable('<p>no table</p>')), [['']]);
  const cells = t.parseHtmlTable('<table><tr><td rowspan="5">a</td><td>b</td></tr></table>');
  assert.equal(cells.length, 1);
  assert.equal(cells[0][0].rs, 1);
});

test('rows and columns are added at the end and removed keeping at least one', () => {
  const cells = t.parseHtmlTable(SIMPLE);
  assert.deepEqual(t.size(t.addRow(cells)), { rows: 3, cols: 3 });
  assert.deepEqual(t.size(t.addColumn(cells)), { rows: 2, cols: 4 });
  assert.deepEqual(text(t.deleteRow(cells, 0)), [['Hardness', '130', '140']]);
  assert.deepEqual(text(t.deleteColumn(cells, 1)), [['Property', 'UFG'], ['Hardness', '140']]);
  const one = [[{ v: 'x', rs: 1, cs: 1, hidden: false }]];
  assert.equal(t.deleteRow(one, 0), one);
  assert.equal(t.deleteColumn(one, 0), one);
  assert.equal(cells[0][0].v, 'Property', 'the input is never modified');
});

test('merging joins the texts with a space and widens the range to keep merged cells whole', () => {
  const cells = t.parseHtmlTable(SIMPLE);
  const merged = t.mergeRange(cells, { r: 0, c: 1 }, { r: 0, c: 2 });
  assert.deepEqual(text(merged), [['Property', 'CG UFG', '·'], ['Hardness', '130', '140']]);
  assert.deepEqual([merged[0][1].rs, merged[0][1].cs], [1, 2]);
  assert.equal(t.mergeRange(cells, { r: 0, c: 0 }, { r: 0, c: 0 }), cells);
  // a range that cuts the merged cell is widened to include all of it
  const widened = t.mergeRange(merged, { r: 0, c: 0 }, { r: 1, c: 1 });
  assert.deepEqual(t.expandRange(merged, { r: 0, c: 0 }, { r: 1, c: 1 }), { r1: 0, c1: 0, r2: 1, c2: 2 });
  assert.deepEqual([widened[0][0].rs, widened[0][0].cs], [2, 3]);
  assert.equal(widened[0][0].v, 'Property CG UFG Hardness 130 140');
});

test('splitting undoes a merge, the covered cells come back empty', () => {
  const merged = t.mergeRange(t.parseHtmlTable(SIMPLE), { r: 0, c: 1 }, { r: 0, c: 2 });
  const split = t.splitCell(merged, 0, 2); // any covered position finds its anchor
  assert.deepEqual(text(split), [['Property', 'CG UFG', ''], ['Hardness', '130', '140']]);
  assert.deepEqual([split[0][1].rs, split[0][1].cs, split[0][2].hidden], [1, 1, false]);
  const plain = t.parseHtmlTable(SIMPLE);
  assert.equal(t.splitCell(plain, 0, 0), plain);
});

test('deleting a row or column that crosses a merged cell splits it first', () => {
  const cells = t.parseHtmlTable(MERGED);
  const withoutRow = t.deleteRow(cells, 1); // the row under the rowspan of Property
  assert.deepEqual(text(withoutRow).map((r) => r.length), [3, 3]);
  assert.deepEqual([withoutRow[0][0].rs, withoutRow[0][1].cs], [1, 2]); // the rowspan was split; the colspan does not cross the row
  assert.equal(withoutRow.flat().filter((c) => c.hidden).length, 1, 'only the cell still covered by Steel stays hidden');
  const withoutColumn = t.deleteColumn(cells, 2); // the right half of the colspan
  assert.deepEqual(withoutColumn[0].map((c) => c.cs), [1, 1]);
  assert.deepEqual(t.size(withoutColumn), { rows: 3, cols: 2 });
});

test('the matrix always satisfies the service shape', () => {
  for (const html of [SIMPLE, MERGED]) {
    const cells = t.mergeRange(t.addRow(t.parseHtmlTable(html)), { r: 0, c: 0 }, { r: 0, c: 1 });
    assert.ok(cells.length > 0 && new Set(cells.map((r) => r.length)).size === 1);
    for (const cell of cells.flat()) {
      assert.equal(typeof cell.v, 'string');
      assert.ok(Number.isInteger(cell.rs) && cell.rs >= 1 && Number.isInteger(cell.cs) && cell.cs >= 1);
    }
    assert.equal(typeof t.gridToHtml(cells), 'string');
  }
});
