// Where a row's ⋯ menu goes on screen. The menu is fixed to the window, so a table that scrolls sideways never clips it
// (Schema list, schema editor groups). It opens below the button, or above when there is more room there, and is
// right-aligned with the button. `rect` is the button's getBoundingClientRect(); `view` is {width, height} of the window.
export function menuSpot(rect, view, menuHeight) {
  const right = Math.max(8, view.width - rect.right);
  const below = view.height - rect.bottom;
  const above = rect.top;
  if (below < menuHeight + 8 && above > below) {
    return { position: 'fixed', right, bottom: view.height - rect.top + 4, maxHeight: above - 12, overflowY: 'auto' };
  }
  return { position: 'fixed', right, top: rect.bottom + 4, maxHeight: Math.max(120, below - 12), overflowY: 'auto' };
}

// True when a scroll should close an open menu: any scroll except one inside the menu itself.
export const scrollClosesMenu = (e) => !(e.target instanceof Element && e.target.closest('[role="menu"]'));
