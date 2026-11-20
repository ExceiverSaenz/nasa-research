import { pageImageUrl } from '../lib/api.js';

// Crop of the page around a box: 3 % of margin at the sides and at least 10 % of the page height, so thin boxes keep
// some context (spec: "Pop-up"). Coordinates are percent of the page, like every other box.
export function cropRegion(box, render) {
  const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
  const x0 = clamp(box.x - 3, 0, 100);
  const x1 = clamp(box.x + box.w + 3, 0, 100);
  const height = Math.max(box.h, 10);
  const mid = box.y + box.h / 2;
  const y0 = clamp(mid - height / 2, 0, 100 - Math.min(height, 100));
  const y1 = Math.min(100, y0 + height);
  const w = x1 - x0;
  const h = y1 - y0;
  return { x: x0, y: y0, w, h, aspect: (w * render.width_px) / (h * render.height_px) };
}

export default function PageCrop({ paper, page, render, box }) {
  if (!box || !render) return <p className="muted small">This box has no position on the page.</p>;
  const crop = cropRegion(box, render);
  return (
    <div className="crop" style={{ aspectRatio: String(crop.aspect) }}>
      <img src={pageImageUrl(paper, page)} alt="Page around the box"
           style={{ width: `${(100 / crop.w) * 100}%`, left: `${-(crop.x / crop.w) * 100}%`, top: `${-(crop.y / crop.h) * 100}%` }} />
      <span className="crop-box" style={{ left: `${((box.x - crop.x) / crop.w) * 100}%`, top: `${((box.y - crop.y) / crop.h) * 100}%`,
                                          width: `${(box.w / crop.w) * 100}%`, height: `${(box.h / crop.h) * 100}%` }} />
    </div>
  );
}
