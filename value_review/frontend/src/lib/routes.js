// Hash routes: #/ (papers of the active folder pair), #/source/<pair>/paper/<id> (review of a paper of that pair)
// and #/paper/<id> (a paper of the active pair, links made before there were several pairs). Anything else: Papers.
const REVIEW = /^#\/(?:source\/([a-z0-9][a-z0-9-]{0,39})\/)?paper\/(\d{1,4})$/;

export function parseRoute(hash) {
  const m = (hash || '').match(REVIEW);
  return m ? { view: 'review', source: m[1] || null, paper: m[2] } : { view: 'papers' };
}

export const reviewHash = (source, paper) => (source ? `#/source/${source}/paper/${paper}` : `#/paper/${paper}`);
