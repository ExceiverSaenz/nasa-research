// Highlights (AC-15): add a box by dragging, redraw a model box, delete it, restore it. o1 has the model box e1 on page 1.
import { test, expect, dragOnPage } from './fixtures.js';

const near = (got, want) => got.every((v, i) => Math.abs(v - want[i]) < 0.02);

test('add, redraw, delete and restore highlights', async ({ page, server }) => {
  await page.goto('/#/review/default/paper/7');
  await expect(page.locator('[aria-current="true"]').first()).toContainText('710 ± 25');
  const draft = async () => {
    await page.keyboard.press('Control+s');
    await expect(page.locator('header')).toContainText('Draft saved');
    return (await server.api('/papers/7')).draft.state.boxes.o1;
  };

  await page.getByRole('button', { name: '+ Add highlight' }).click();
  await expect(page.getByText(/^Drag on the page to draw/)).toBeVisible();
  await dragOnPage(page, 0.1, 0.45, 0.3, 0.5);   // within the part of the page in view (it scrolls to the value's box)
  let boxes = await draft();
  expect(boxes.added).toHaveLength(1);
  expect(near(boxes.added[0].bbox, [0.1, 0.45, 0.3, 0.5])).toBe(true);

  // the model's box: select it on the page, then redraw it
  await page.locator('.sheet').getByRole('button', { name: /The value/ }).click();
  const tools = page.getByRole('region', { name: 'PDF page' });
  await tools.getByRole('button', { name: 'Redraw' }).click();
  await dragOnPage(page, 0.5, 0.4, 0.6, 0.42);
  boxes = await draft();
  expect(near(boxes.redrawn.e1.bbox, [0.5, 0.4, 0.6, 0.42])).toBe(true);
  await page.locator('.sheet').getByRole('button', { name: /The value/ }).click();
  await expect(tools.getByRole('button', { name: 'Undo redraw' })).toBeVisible();   // the board's mark of a redrawn box

  // delete it, then restore it
  await page.locator('.sheet').getByRole('button', { name: /The value/ }).click();
  await tools.getByRole('button', { name: 'Delete', exact: true }).click();
  boxes = await draft();
  expect(boxes.removed).toEqual(['e1']);
  await expect(page.locator('.sheet').getByRole('button', { name: /The value/ })).toHaveCount(0);
  await tools.getByRole('button', { name: 'Restore removed' }).click();
  boxes = await draft();
  expect(boxes.removed).toEqual([]);
  await expect(page.locator('.sheet').getByRole('button', { name: /The value/ })).toHaveCount(1);
});

test('Escape cancels drawing and nothing is added', async ({ page, server }) => {
  await page.goto('/#/review/default/paper/7');
  await page.getByRole('button', { name: '+ Add highlight' }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByText(/^Drag on the page to draw/)).toHaveCount(0);
  await expect(page.locator('header')).not.toContainText('Unsaved changes');
  expect((await server.api('/papers/7')).draft).toBeNull();
});
