import test from 'node:test';
import assert from 'node:assert/strict';
import { menuSpot } from './menuSpot.js';

const view = { width: 1200, height: 700 };

test('a menu with room below opens below the button, right-aligned', () => {
  const s = menuSpot({ top: 300, bottom: 344, right: 1140 }, view, 300);
  assert.equal(s.position, 'fixed');
  assert.equal(s.top, 348);
  assert.equal(s.right, 60);
  assert.equal(s.bottom, undefined);
});

test('a menu near the bottom of the window opens above the button', () => {
  const s = menuSpot({ top: 600, bottom: 644, right: 1140 }, view, 300);
  assert.equal(s.top, undefined);
  assert.equal(s.bottom, 104);
  assert.equal(s.maxHeight, 588);
});

test('a button at the window edge keeps the menu inside it', () => {
  assert.equal(menuSpot({ top: 100, bottom: 144, right: 1300 }, view, 300).right, 8);
});
