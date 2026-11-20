// Temporary versions (BR-05): each edit remembers the state it started from. The draft save sends the ones
// created since the last save; repeating the same kind of edit on the same box replaces the last version.
export function recordVersion(pending, previousState, { label, key }, at) {
  const last = pending[pending.length - 1];
  if (last && key && last.key === key) return pending; // same kind of edit on the same box: keep the older state
  return [...pending, { label, at, state: previousState, key }];
}

export const forServer = (pending) => pending.map(({ label, at, state }) => ({ label, at, state }));
