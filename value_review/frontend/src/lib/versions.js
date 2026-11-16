// Version history (step 8): compare two versions value by value (AC-12).
// A version's `values` are its materialized rows (schemas/version.schema.json#/$defs/value).

const side = (r) => (r ? { value: r.value, unit: r.unit, status: r.status, featureId: r.feature_id, records: r.record_labels.join(', ') } : null);
const same = (a, b) => a && b && a.value === b.value && a.unit === b.unit && a.status === b.status
  && a.featureId === b.featureId && a.records === b.records;

// Rows that differ between `older` and `newer`, matched by observation id, in `newer`'s order then removed ones.
export function compareVersions(older, newer) {
  const before = new Map(older.values.map((r) => [r.observation_id, r]));
  const after = new Map(newer.values.map((r) => [r.observation_id, r]));
  const out = [];
  newer.values.forEach((r) => {
    const a = side(before.get(r.observation_id));
    const b = side(r);
    if (!same(a, b)) out.push({ id: r.observation_id, featureId: r.feature_id, records: b.records, before: a, after: b });
  });
  older.values.forEach((r) => {
    if (!after.has(r.observation_id)) {
      const a = side(r);
      out.push({ id: r.observation_id, featureId: r.feature_id, records: a.records, before: a, after: null });
    }
  });
  return out;
}

// What changed in one side of a comparison, in words.
export function describeSide(s, label) {
  if (!s) return 'not in this version';
  const v = s.value === null || s.value === undefined ? '—' : `${s.value}${s.unit ? ` ${s.unit}` : ''}`;
  return `${v} · ${label[s.status] || s.status}`;
}

export function downloadName(paper, n, kind) {
  return `paper-${paper}-v${n}.${kind}`;
}
