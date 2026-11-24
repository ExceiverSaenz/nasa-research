// Editing a schema's content (20-schema-specification.md, 22-schema-interface-contract.md). Pure functions: each
// returns a new content and never changes the one it gets. Ids are minted here and never reused (BR-S02).

export const FORMAT = 'value-review-schema/1';
export const TYPES = [['number', 'Number'], ['category', 'Category'], ['text', 'Text'], ['calculated', 'Calculated']];
export const TYPE_LABEL = Object.fromEntries(TYPES);

export const emptyContent = () => ({ schema: FORMAT, description: '', groups: [] });

export const blankField = (fieldId, name) => ({
  field_id: fieldId, name, description: '', type: 'text', unit: '', allowed: [], multiple: false, formula: '', inputs: [], family: null,
});

// Same comparison as the service (domain/schema_rules.py): case and repeated spaces do not count.
export const sameName = (name) => name.split(/\s+/).filter(Boolean).join(' ').toLowerCase();

export const signature = (content) => JSON.stringify(content);

export function counts(content) {
  return { groups: content.groups.length, fields: content.groups.reduce((a, g) => a + g.fields.length, 0) };
}

// Every id a content uses, to mint new ones above them.
export function idsOf(...contents) {
  const out = new Set();
  for (const c of contents) {
    if (!c) continue;
    for (const g of c.groups) {
      out.add(g.group_id);
      for (const f of g.fields) out.add(f.field_id);
    }
  }
  return out;
}

// The next "<prefix>_<n>" above every id already known (from the content, the draft and the versions loaded).
export function nextId(prefix, known) {
  let max = 0;
  const re = new RegExp(`^${prefix}_(\\d+)$`);
  for (const id of known) {
    const m = re.exec(id);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return `${prefix}_${max + 1}`;
}

// A name that no item of the list has yet: "Field", "Field 2", … (and "Yield strength (copy)" for duplicates).
export function freeName(base, taken) {
  const used = new Set([...taken].map(sameName));
  if (!used.has(sameName(base))) return base;
  for (let k = 2; ; k += 1) if (!used.has(sameName(`${base} ${k}`))) return `${base} ${k}`;
}

export function findField(content, fieldId) {
  for (let gi = 0; gi < content.groups.length; gi += 1) {
    const fi = content.groups[gi].fields.findIndex((f) => f.field_id === fieldId);
    if (fi >= 0) return { gi, fi, group: content.groups[gi], field: content.groups[gi].fields[fi] };
  }
  return null;
}

const mapGroups = (content, fn) => ({ ...content, groups: content.groups.map(fn) });

export function addGroup(content, groupId, name) {
  return { ...content, groups: [...content.groups, { group_id: groupId, name, fields: [] }] };
}

export function renameGroup(content, groupId, name) {
  return mapGroups(content, (g) => (g.group_id === groupId ? { ...g, name } : g));
}

export function removeGroup(content, groupId) {
  return { ...content, groups: content.groups.filter((g) => g.group_id !== groupId) };
}

export function moveGroup(content, groupId, step) {
  const i = content.groups.findIndex((g) => g.group_id === groupId);
  const j = i + step;
  if (i < 0 || j < 0 || j >= content.groups.length) return content;
  const groups = [...content.groups];
  [groups[i], groups[j]] = [groups[j], groups[i]];
  return { ...content, groups };
}

export function addField(content, groupId, field) {
  return mapGroups(content, (g) => (g.group_id === groupId ? { ...g, fields: [...g.fields, field] } : g));
}

// A change of type clears what only the old type uses, so a saved field never breaks BR-S04.
export function updateField(content, fieldId, patch) {
  return mapGroups(content, (g) => ({
    ...g,
    fields: g.fields.map((f) => {
      if (f.field_id !== fieldId) return f;
      const next = { ...f, ...patch };
      if (next.type !== 'number') next.unit = '';
      if (next.type !== 'category') { next.allowed = []; next.multiple = false; }
      if (next.type !== 'calculated') { next.formula = ''; next.inputs = []; }
      return next;
    }),
  }));
}

export function removeField(content, fieldId) {
  const content2 = mapGroups(content, (g) => ({ ...g, fields: g.fields.filter((f) => f.field_id !== fieldId) }));
  return content2;
}

export function duplicateField(content, fieldId, newId) {
  const at = findField(content, fieldId);
  if (!at) return content;
  const copy = { ...at.field, field_id: newId, name: freeName(`${at.field.name} (copy)`, at.group.fields.map((f) => f.name)), family: null };
  return mapGroups(content, (g, gi) => (gi === at.gi ? { ...g, fields: [...g.fields.slice(0, at.fi + 1), copy, ...g.fields.slice(at.fi + 1)] } : g));
}

// Move a field to a group at a position (another group too). The id never changes (BR-S02).
export function moveFieldTo(content, fieldId, groupId, index) {
  const at = findField(content, fieldId);
  if (!at) return content;
  const without = mapGroups(content, (g, gi) => (gi === at.gi ? { ...g, fields: g.fields.filter((f) => f.field_id !== fieldId) } : g));
  return mapGroups(without, (g) => {
    if (g.group_id !== groupId) return g;
    const k = Math.max(0, Math.min(index, g.fields.length));
    return { ...g, fields: [...g.fields.slice(0, k), at.field, ...g.fields.slice(k)] };
  });
}

// Up or down by one place; past the edge of its group it goes to the end of the group above or the start of the one
// below, so the buttons alone can bring a field anywhere (AC-S15).
export function moveField(content, fieldId, step) {
  const at = findField(content, fieldId);
  if (!at) return content;
  const target = at.fi + step;
  if (target >= 0 && target < at.group.fields.length) return moveFieldTo(content, fieldId, at.group.group_id, target);
  const other = content.groups[at.gi + step];
  if (!other) return content;
  return moveFieldTo(content, fieldId, other.group_id, step < 0 ? other.fields.length : 0);
}

// The item a rule problem (a JSON pointer such as /groups/0/fields/1/name) points to.
export function targetOf(content, ref) {
  const m = /^\/groups\/(\d+)(?:\/fields\/(\d+))?(?:\/([a-z_]+))?/.exec(ref || '');
  if (!m) return null;
  const group = content.groups[Number(m[1])];
  if (!group) return null;
  const field = m[2] !== undefined ? group.fields[Number(m[2])] : null;
  return { groupId: group.group_id, fieldId: field ? field.field_id : null, key: m[3] || null };
}

export const RULE_TEXT = {
  empty_name: 'Type a name.',
  too_long: 'The name is too long (120 characters at most).',
  duplicate_name: 'Another one in the same group has this name.',
  duplicate_id: 'Two items share an internal id.',
  bad_id: 'The internal id is not valid.',
  unit_not_allowed: 'Only a Number has a unit.',
  allowed_not_allowed: 'Only a Category has allowed values.',
  inputs_not_allowed: 'Only a Calculated field reads other fields.',
  formula_required: 'Write the formula.',
  unknown_input: 'The formula reads a field that is no longer in the schema.',
  self_reference: 'The formula cannot read its own field.',
};

// The rule problems of a failed Save version, as {groupId or fieldId: [messages]} for the editor.
export function problemsByItem(content, items) {
  const out = {};
  for (const { ref, rule } of items || []) {
    const t = targetOf(content, ref);
    const key = t ? (t.fieldId || t.groupId) : 'schema';
    (out[key] = out[key] || []).push(RULE_TEXT[rule] || rule);
  }
  return out;
}

// The line the model will read for a field (canvas: "What the model will read").
export function modelText(field) {
  const parts = [`${field.name}${field.type === 'number' && field.unit ? ` (${field.unit})` : ''}`];
  if (field.description) parts.push(field.description);
  if (field.type === 'category' && field.allowed.length) {
    parts.push(`${field.multiple ? 'One or several of' : 'One of'}: ${field.allowed.join(', ')}. Another value may be reported if none fits.`);
  }
  if (field.type === 'calculated') parts.push(`Calculated from ${field.formula || 'a formula'}; not read from the paper.`);
  return parts.join(' — ');
}

// "Saved · v1 · 54 fields in 4 groups", "Draft · changes since v1" or "New · not saved".
export function statusLine(version, dirtyOrDraft, content) {
  const { groups, fields } = counts(content);
  const size = `${fields} ${fields === 1 ? 'field' : 'fields'} in ${groups} ${groups === 1 ? 'group' : 'groups'}`;
  if (version === 0) return `New · not saved · ${size}`;
  if (dirtyOrDraft) return `Draft · changes since v${version} · ${size}`;
  return `Saved · v${version} · ${size}`;
}

// Differences between two versions, matched by id (BR-S02): a renamed field is one change, not a removal and an
// addition. Rows are {id, item, what, before, after}; positions are reported as one "order" row per group, so adding
// a field does not show every field after it as moved.
const show = {
  type: (v) => TYPE_LABEL[v] || v,
  allowed: (v) => (v.length ? v.join(', ') : '—'),
  multiple: (v) => (v ? 'Several values' : 'One value'),
  text: (v) => (v === '' || v === null || v === undefined ? '—' : String(v)),
};
const FIELD_KEYS = [['name', 'Name', show.text], ['description', 'Description', show.text], ['type', 'Type', show.type],
  ['unit', 'Unit', show.text], ['allowed', 'Allowed values', show.allowed], ['multiple', 'Values', show.multiple],
  ['formula', 'Formula', show.text]];

export function compareSchemas(older, newer) {
  const rows = [];
  const index = (content) => {
    const groups = new Map(content.groups.map((g) => [g.group_id, g]));
    const fields = new Map();
    for (const g of content.groups) for (const f of g.fields) fields.set(f.field_id, { f, g });
    return { groups, fields };
  };
  const a = index(older), b = index(newer);
  const name = (map, id) => (map.fields.get(id) ? map.fields.get(id).f.name : id);
  const sameOrder = (x, y) => x.length === y.length && x.every((v, i) => v === y[i]);

  const commonGroups = (c, other) => c.groups.map((g) => g.group_id).filter((id) => other.groups.has(id));
  if (!sameOrder(commonGroups(older, b), commonGroups(newer, a))) {
    rows.push({ id: 'groups-order', item: 'Groups', what: 'Order',
      before: commonGroups(older, b).map((id) => a.groups.get(id).name).join(', '), after: commonGroups(newer, a).map((id) => b.groups.get(id).name).join(', ') });
  }
  for (const g of newer.groups) {
    const old = a.groups.get(g.group_id);
    if (!old) { rows.push({ id: `g+${g.group_id}`, item: g.name, what: 'Group added', before: '—', after: `${g.fields.length} fields` }); continue; }
    if (old.name !== g.name) rows.push({ id: `g~${g.group_id}`, item: g.name, what: 'Group name', before: old.name, after: g.name });
    const inBoth = (list, other) => list.map((f) => f.field_id).filter((id) => other.fields.has(id) && other.fields.get(id).g.group_id === g.group_id);
    const before = inBoth(old.fields, b), after = inBoth(g.fields, a);
    if (!sameOrder(before, after)) {
      rows.push({ id: `o${g.group_id}`, item: g.name, what: 'Order of fields', before: before.map((id) => name(a, id)).join(', '), after: after.map((id) => name(b, id)).join(', ') });
    }
  }
  for (const g of older.groups) {
    if (!b.groups.has(g.group_id)) rows.push({ id: `g-${g.group_id}`, item: g.name, what: 'Group deleted', before: `${g.fields.length} fields`, after: '—' });
  }
  for (const [id, { f, g }] of b.fields) {
    const old = a.fields.get(id);
    if (!old) { rows.push({ id: `f+${id}`, item: f.name, what: 'Field added', before: '—', after: `in ${g.name}` }); continue; }
    if (old.g.group_id !== g.group_id) rows.push({ id: `f>${id}`, item: f.name, what: 'Group', before: old.g.name, after: g.name });
    for (const [key, label, fmt] of FIELD_KEYS) {
      const x = fmt(old.f[key]), y = fmt(f[key]);
      if (x !== y) rows.push({ id: `f~${id}~${key}`, item: f.name, what: label, before: x, after: y });
    }
    const inputs = (m, list) => (list.length ? list.map((i) => name(m, i)).join(', ') : '—');
    if (inputs(a, old.f.inputs) !== inputs(b, f.inputs)) rows.push({ id: `f~${id}~inputs`, item: f.name, what: 'Reads', before: inputs(a, old.f.inputs), after: inputs(b, f.inputs) });
  }
  for (const [id, { f, g }] of a.fields) {
    if (!b.fields.has(id) && b.groups.has(g.group_id)) rows.push({ id: `f-${id}`, item: f.name, what: 'Field deleted', before: `in ${g.name}`, after: '—' });
  }
  return rows;
}

// Filling the current draft from an imported file: groups and fields with the same names keep their ids, so their
// history continues; the others get new ids above every id known (BR-S02).
export function adoptIds(imported, current, known) {
  const used = new Set(known);
  const mint = (prefix) => { const id = nextId(prefix, used); used.add(id); return id; };
  const groups = new Map(current.groups.map((g) => [sameName(g.name), g]));
  return {
    ...imported,
    groups: imported.groups.map((g) => {
      const old = groups.get(sameName(g.name));
      const fields = old ? new Map(old.fields.map((f) => [sameName(f.name), f])) : new Map();
      return {
        ...g,
        group_id: old ? old.group_id : mint('g'),
        fields: g.fields.map((f) => ({ ...f, field_id: fields.has(sameName(f.name)) ? fields.get(sameName(f.name)).field_id : mint('f') })),
      };
    }),
  };
}

// A File as base64, for OP-S11 (no multipart upload, ADR-011).
export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

// Dragging (AC-S07): put a group just before another one (or at the end with beforeId null).
export function moveGroupBefore(content, groupId, beforeId) {
  const moving = content.groups.find((g) => g.group_id === groupId);
  if (!moving || groupId === beforeId) return content;
  const rest = content.groups.filter((g) => g.group_id !== groupId);
  const k = beforeId ? rest.findIndex((g) => g.group_id === beforeId) : rest.length;
  if (k < 0) return content;
  return { ...content, groups: [...rest.slice(0, k), moving, ...rest.slice(k)] };
}

// Dragging a field onto another field puts it just before that field, in that field's group.
export function moveFieldBefore(content, fieldId, beforeId) {
  if (fieldId === beforeId) return content;
  const target = findField(content, beforeId);
  if (!target) return content;
  const at = findField(content, fieldId);
  const sameGroupEarlier = at && at.group.group_id === target.group.group_id && at.fi < target.fi;
  return moveFieldTo(content, fieldId, target.group.group_id, sameGroupEarlier ? target.fi - 1 : target.fi);
}
