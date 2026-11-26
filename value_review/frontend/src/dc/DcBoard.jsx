import React, { useEffect, useMemo, useReducer, useRef } from 'react';

// Runs a canvas board (src/boards/*: template, styles and logic copied from the Design artifact) inside the app,
// so the screens without a backend stay exactly as drawn (ADR-013). A board's template uses {{path}} bindings,
// <sc-if value> and <sc-for list as>; its logic is a class with state, setState and renderVals().

// The logic base class the boards extend.
export class DCLogic {
  constructor(props) { this.props = props || {}; this.state = {}; this._render = null; }
  setState(patch, callback) {
    const next = typeof patch === 'function' ? patch(this.state, this.props) : patch;
    this.state = { ...this.state, ...next };
    if (this._render) this._render();
    if (callback) setTimeout(callback, 0);
  }
  renderVals() { return {}; }
}

const BOOLEAN = new Set(['disabled', 'checked', 'readonly', 'selected', 'hidden', 'required', 'multiple', 'autofocus', 'open']);
const RENAME = { class: 'className', for: 'htmlFor', tabindex: 'tabIndex', readonly: 'readOnly', maxlength: 'maxLength', minlength: 'minLength',
  autocomplete: 'autoComplete', spellcheck: 'spellCheck', colspan: 'colSpan', rowspan: 'rowSpan', autofocus: 'autoFocus', viewbox: 'viewBox',
  'accept-charset': 'acceptCharset', enterkeyhint: 'enterKeyHint', inputmode: 'inputMode' };
const EVENTS = { onclick: 'onClick', oninput: 'onChange', onchange: 'onChange', ondoubleclick: 'onDoubleClick', ondblclick: 'onDoubleClick',
  onpointerdown: 'onPointerDown', onpointermove: 'onPointerMove', onpointerup: 'onPointerUp', onkeydown: 'onKeyDown', onkeyup: 'onKeyUp',
  onfocus: 'onFocus', onblur: 'onBlur', onmousedown: 'onMouseDown', onmouseup: 'onMouseUp', onsubmit: 'onSubmit', ondragstart: 'onDragStart',
  ondragover: 'onDragOver', ondrop: 'onDrop', ondragend: 'onDragEnd', onwheel: 'onWheel', onscroll: 'onScroll' };
const WHOLE = /^\{\{\s*([A-Za-z_$][\w$.]*)\s*\}\}$/;
const PART = /\{\{\s*([A-Za-z_$][\w$.]*)\s*\}\}/g;
const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

// Parses a template once. <select> is renamed first: the HTML parser drops <sc-for> inside a real <select>.
export function parseTemplate(html) {
  const safe = html.replace(/<select\b/g, '<x-select').replace(/<\/select>/g, '</x-select>');
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${safe}</body></html>`, 'text/html');
  return doc.body;
}

function lookup(path, scopes) {
  const [head, ...rest] = path.split('.');
  let v;
  for (let i = scopes.length - 1; i >= 0; i -= 1) { if (scopes[i] && head in scopes[i]) { v = scopes[i][head]; break; } }
  for (const k of rest) v = v == null ? undefined : v[k];
  return v;
}
const textOf = (v) => (v === undefined || v === null || v === false ? '' : String(v));
const interpolate = (s, scopes) => s.replace(PART, (_, p) => textOf(lookup(p, scopes)));
const truthy = (v) => !!v && v !== 'false';

function styleObject(css) {
  const out = {};
  css.split(';').forEach((decl) => {
    const i = decl.indexOf(':');
    if (i < 0) return;
    const prop = decl.slice(0, i).trim();
    const value = decl.slice(i + 1).trim();
    if (!prop || !value) return;
    const key = prop.startsWith('--') ? prop : camel(prop.startsWith('-webkit-') ? `Webkit-${prop.slice(8)}` : prop.startsWith('-ms-') ? `ms-${prop.slice(4)}` : prop);
    out[key] = value;
  });
  return out;
}

function propsOf(el, scopes, ctx) {
  const props = {};
  const tag = el.tagName.toLowerCase();
  for (const { name, value } of Array.from(el.attributes)) {
    if (name.startsWith('hint-')) continue;
    const whole = value.match(WHOLE);
    const raw = whole ? lookup(whole[1], scopes) : value.includes('{{') ? interpolate(value, scopes) : value;
    if (EVENTS[name]) { if (typeof raw === 'function') props[EVENTS[name]] = raw; continue; }
    if (name === 'style') { props.style = styleObject(textOf(raw)); continue; }
    if (BOOLEAN.has(name)) { props[RENAME[name] || name] = whole ? truthy(raw) : value !== 'false'; continue; }
    if (name === 'href') { props.href = ctx.link(textOf(raw)); continue; }
    if (name.startsWith('aria-') || name.startsWith('data-')) { props[name] = textOf(raw); continue; }
    const key = RENAME[name] || (name.includes('-') ? camel(name) : name);
    props[key] = whole && typeof raw !== 'string' && raw !== undefined && key !== 'value' ? raw : (key === 'value' ? (raw === undefined || raw === null ? '' : raw) : textOf(raw));
  }
  // A bound value or checked with no handler would be read-only in React: let the browser keep it instead.
  const field = tag === 'input' || tag === 'textarea' || tag === 'x-select';
  if (field && 'value' in props && !props.onChange) { props.defaultValue = props.value; delete props.value; }
  if (field && 'checked' in props && !props.onChange) { props.defaultChecked = props.checked; delete props.checked; }
  return props;
}

function render(node, scopes, ctx, key) {
  if (node.nodeType === 3) {
    const t = node.nodeValue;
    if (!t.trim()) return /\n/.test(t) ? (ctx.inSelect ? null : ' ') : t;
    return t.includes('{{') ? interpolate(t, scopes) : t;
  }
  if (node.nodeType !== 1) return null;
  const tag = node.tagName.toLowerCase();
  if (tag === 'script' || tag === 'helmet' || tag === 'link') return null;
  if (ctx.skip && ctx.skip(node)) return null;
  if (tag === 'sc-if') {
    const m = (node.getAttribute('value') || '').match(WHOLE);
    if (!truthy(m ? lookup(m[1], scopes) : node.getAttribute('value'))) return null;
    return <React.Fragment key={key}>{children(node, scopes, ctx)}</React.Fragment>;
  }
  if (tag === 'sc-for') {
    const m = (node.getAttribute('list') || '').match(WHOLE);
    const list = m ? lookup(m[1], scopes) : [];
    const as = node.getAttribute('as') || 'item';
    return <React.Fragment key={key}>{(Array.isArray(list) ? list : []).map((item, i) => (
      <React.Fragment key={i}>{children(node, scopes.concat([{ [as]: item }]), ctx)}</React.Fragment>))}</React.Fragment>;
  }
  const realTag = tag === 'x-select' ? 'select' : tag;
  const props = propsOf(node, scopes, ctx);
  props.key = key;
  if (realTag === 'textarea') return React.createElement('textarea', props);
  const inner = children(node, scopes, tag === 'x-select' ? { ...ctx, inSelect: true } : ctx);
  if (['input', 'img', 'br', 'hr', 'meta'].includes(realTag)) return React.createElement(realTag, props);
  return React.createElement(realTag, props, ...inner);
}
function children(node, scopes, ctx) {
  return Array.from(node.childNodes).map((c, i) => render(c, scopes, ctx, i));
}

// The board's own navy top bar is replaced by the app's (AppHeader), so the profile and links are the real ones.
const isTopBar = (el) => (el.getAttribute('style') || '').includes('background: #071B3F') && el.textContent.includes('TENSILE DATA REVIEW');

export default function DcBoard({ template, css, Logic, links = {} }) {
  const tree = useMemo(() => parseTemplate(template), [template]);
  const [, force] = useReducer((x) => x + 1, 0);
  const inst = useRef(null);
  if (!inst.current) inst.current = new Logic({});
  inst.current._render = force;
  useEffect(() => () => { inst.current._render = null; }, []);
  useEffect(() => {
    const el = document.createElement('style');
    el.textContent = css;
    document.head.appendChild(el);
    return () => el.remove();
  }, [css]);
  const vals = inst.current.renderVals();
  const ctx = {
    link: (href) => (href in links ? links[href] : href),
    skip: (el) => el.tagName === 'DIV' && isTopBar(el),
  };
  return <div className="dc-board">{children(tree, [vals], ctx)}</div>;
}
