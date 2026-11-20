// Hash routes: "#/" (collection) and "#/papers/<n>/pages/<index>" (review; index is 0-based like the API).
export function parseRoute(hash) {
  const match = /^#\/papers\/(\d+)\/pages\/(\d+)$/.exec(hash || '');
  if (match) return { name: 'review', paper: match[1], page: Number(match[2]) };
  return { name: 'collection' };
}

export const reviewHash = (paper, page) => `#/papers/${paper}/pages/${page}`;
