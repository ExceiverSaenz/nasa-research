// Hash routes: #/ (papers of the active folder pair), #/source/<pair>/paper/<id> (review of a paper of that pair)
// and #/paper/<id> (a paper of the active pair, links made before there were several pairs); #/schemas and
// #/schemas/<id> the Schema section. Anything else: Papers.
const REVIEW = /^#\/(?:source\/([a-z0-9][a-z0-9-]{0,39})\/)?paper\/(\d{1,4})$/;

// The Schema section: #/schemas (list) and #/schemas/<id> (editor), 22-schema-interface-contract.md.
const SCHEMA = /^#\/schemas(?:\/([a-z0-9][a-z0-9-]{0,63}))?\/?$/;

export function parseRoute(hash) {
  const m = (hash || '').match(REVIEW);
  if (m) return { view: 'review', source: m[1] || null, paper: m[2] };
  const s = (hash || '').match(SCHEMA);
  if (s) return s[1] ? { view: 'schema', schema: s[1] } : { view: 'schemas' };
  return { view: 'papers' };
}

export const SCHEMAS_HASH = '#/schemas';
export const schemaHash = (id) => `#/schemas/${id}`;

export const reviewHash = (source, paper) => (source ? `#/source/${source}/paper/${paper}` : `#/paper/${paper}`);

// How many history steps undo a navigation, from the stamps of the entry reached (``arrived``; null for an entry a link
// has just added) and of the entry left (``left``): a new entry or a step forward is undone by going back, a step back
// by going forward. The history itself is never rewritten.
export function stepBack(arrived, left) {
  if (arrived === null || arrived === undefined) return -1;
  return arrived < left ? 1 : -1;
}
