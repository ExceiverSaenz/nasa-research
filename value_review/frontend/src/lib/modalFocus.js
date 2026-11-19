// Keyboard focus for every modal dialog (any element with aria-modal="true"), in one place:
// - when a dialog opens, focus moves into it, unless the dialog already put it inside (autoFocus);
// - Tab and Shift+Tab cycle inside the topmost dialog and never reach the page behind it;
// - when the last dialog closes, focus returns to the element that had it before (the button that opened it).

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function topModal(doc = document) {
  const all = doc.querySelectorAll('[aria-modal="true"]');
  return all.length ? all[all.length - 1] : null;
}

export function focusables(modal) {
  return [...modal.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length > 0);
}

// The element to focus next when Tab (or Shift+Tab) is pressed inside ``modal``; null when the browser may move on.
export function wrapTarget(modal, active, backwards) {
  const items = focusables(modal);
  if (!items.length) return modal;
  const first = items[0], last = items[items.length - 1];
  if (!modal.contains(active)) return backwards ? last : first;
  if (backwards && active === first) return last;
  if (!backwards && active === last) return first;
  return null;
}

export function installModalFocus(doc = document) {
  let current = null;
  let opener = null;
  const sync = () => {
    const modal = topModal(doc);
    if (modal && modal !== current) {
      if (!current) opener = doc.activeElement;
      current = modal;
      if (!modal.contains(doc.activeElement)) {
        const target = focusables(modal)[0] || modal;
        if (target === modal && !modal.hasAttribute('tabindex')) modal.setAttribute('tabindex', '-1');
        target.focus();
      }
    } else if (!modal && current) {
      current = null;
      if (opener && doc.contains(opener) && typeof opener.focus === 'function') opener.focus();
      opener = null;
    }
  };
  const observer = new MutationObserver(sync);
  observer.observe(doc.body, { childList: true, subtree: true });
  const onKey = (e) => {
    if (e.key !== 'Tab') return;
    const modal = topModal(doc);
    if (!modal) return;
    const target = wrapTarget(modal, doc.activeElement, e.shiftKey);
    if (target) { e.preventDefault(); target.focus(); }
  };
  doc.addEventListener('keydown', onKey, true);
  return () => { observer.disconnect(); doc.removeEventListener('keydown', onKey, true); };
}
