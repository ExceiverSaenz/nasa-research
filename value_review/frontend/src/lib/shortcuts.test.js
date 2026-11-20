import test from 'node:test';
import assert from 'node:assert/strict';
import { actionFor, SHORTCUTS } from './shortcuts.js';

const key = (code, extra = {}) => ({ code, key: extra.key || code.replace(/^Key|^Digit/, '').toLowerCase(), ctrlKey: false, metaKey: false,
  shiftKey: false, altKey: false, target: { tagName: 'DIV' }, ...extra });

test('decision keys follow the button order S D F', () => {
  assert.deepEqual(['KeyS', 'KeyD', 'KeyF'].map((c) => actionFor(key(c))), ['reject', 'unsure', 'accept']);
  assert.equal(actionFor(key('KeyJ')), 'next');
  assert.equal(actionFor(key('KeyK')), 'prev');
  assert.equal(actionFor(key('KeyJ', { shiftKey: true })), 'nextScope');
  assert.equal(actionFor(key('Comma', { key: ',' })), 'prevPage');
  assert.equal(actionFor(key('Digit0')), 'fit');
});

test('physical keys: the same place on other layouts', () => {
  // On an AZERTY keyboard the key at the position of Q prints "a"; the code is still KeyQ, which has no action.
  assert.equal(actionFor(key('KeyQ', { key: 'a' })), null);
  assert.equal(actionFor(key('KeyF', { key: 'f' })), 'accept');
});

test('typing in a field, dialogs and modifiers', () => {
  assert.equal(actionFor(key('KeyF', { target: { tagName: 'TEXTAREA' } })), null);
  assert.equal(actionFor(key('KeyF', { target: { tagName: 'DIV', isContentEditable: true } })), null);
  assert.equal(actionFor(key('KeyF'), { dialog: true }), null);
  assert.equal(actionFor(key('Escape', { key: 'Escape' }), { dialog: true }), 'escape');
  assert.equal(actionFor(key('KeyS', { ctrlKey: true, target: { tagName: 'INPUT' } })), 'save');
  assert.equal(actionFor(key('Enter', { key: 'Enter', ctrlKey: true }), { editing: true }), 'saveEdit');
  assert.equal(actionFor(key('Enter', { key: 'Enter', ctrlKey: true, shiftKey: true })), 'finish');
  assert.equal(actionFor(key('KeyZ', { ctrlKey: true })), 'undo');
  assert.equal(actionFor(key('KeyF', { altKey: true })), null);
  assert.equal(actionFor(key('Slash', { key: '?', shiftKey: true })), 'help');
  assert.equal(actionFor(key('Slash', { key: '/', shiftKey: true })), 'help');   // US position, whatever character it reports
  assert.equal(actionFor(key('Minus', { key: '?', shiftKey: true })), 'help');   // Spanish layout
});

test('every listed shortcut has a unique action', () => {
  const ids = SHORTCUTS.flatMap((g) => g.items.map(([id]) => id));
  assert.equal(new Set(ids).size, ids.length);
});
