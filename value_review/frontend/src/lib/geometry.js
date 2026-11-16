// Boxes stay in the source format [x_min, y_min, x_max, y_max], 0-1, top-left origin (ADR-007).

export function boxStyle(bbox) {
  if (!bbox) return null;
  const [x0, y0, x1, y1] = bbox;
  const pct = (v) => `${(v * 100).toFixed(3)}%`;
  return { left: pct(x0), top: pct(y0), width: pct(x1 - x0), height: pct(y1 - y0) };
}

export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 3;
export const clampZoom = (z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 100) / 100));

// Image width to request for a sheet drawn at `px` CSS pixels: snapped like the service (400-2400, step 200).
export function imageWidth(px, ratio = 1) {
  const w = Math.min(2400, Math.max(400, Math.round((px * ratio) / 200) * 200));
  return w;
}
