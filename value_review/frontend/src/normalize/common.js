// Shared text of the Normalize boards (90-normalize-specification.md): labels, statuses and short summaries.

export const TYPE = { number: 'Number + unit', category: 'Category', text: 'Text', calculated: 'Calculated' };
export const DEC_LABEL = { norm: 'Normalize', keep: 'Keep as is', calc: 'Calculated', none: '—' };

// feature status -> [label, dot colour]
export const STATUS = {
  none: ['Not defined', '#9AA3B2'],
  draft: ['Draft', '#B7791F'],
  ready: ['Ready to run', '#0B3D91'],
  queued: ['Queued', '#9AA3B2'],
  normalizing: ['Normalizing', '#0B3D91'],
  failed: ['Failed', '#B42318'],
  validating: ['Normalized · validating', '#0B3D91'],
  done: ['Validated', '#17703A'],
  outdated: ['Outdated', '#B42318'],
  kept: ['Kept as is', '#4A5568'],
  calc: ['Calculated', '#4A5568'],
  archived: ['Archived', '#8A94A6'],
  cancelled: ['Cancelled', '#9AA3B2'],
};

export const WHEN = (iso) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '');

// One line for the table: "MPa 52 · ksi 6 · …" for numbers, "a, b, c…" for text and categories.
export function formatsSummary(f) {
  const list = f.formats || [];
  if (!list.length) return '—';
  if (f.type === 'number') return list.slice(0, 4).map((x) => `${x.name} ${x.n}`).join(' · ') + (list.length > 4 ? ' · …' : '');
  if (list.length > 6) return `${list.length} different values`;
  return list.slice(0, 3).map((x) => x.name).join(', ') + (list.length > 3 ? '…' : '');
}

// The status shown for a feature, with its counts: {text, dot}.
export function statusOf(f) {
  const [label, dot] = STATUS[f.status] || STATUS.none;
  const c = f.counts || {};
  const note = {
    ready: c.normalized ? `${c.to_normalize} to normalize` : '',
    validating: `${c.validated} of ${c.values} validated`,
    done: `${c.validated} of ${c.values}`,
    outdated: `${c.outdated} outdated`,
    failed: f.error || '',
  }[f.status];
  return { text: note ? `${label} · ${note}` : label, dot };
}
