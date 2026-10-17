// Minimal SVG line charts for the asset screen (sensor trend, health index history).

import { raw, escape } from './ui.js';

const GRID = '#E2E7EF';
const AXIS = '#5E6878';

function niceStep(range, ticks) {
  const rough = range / ticks;
  const mag = 10 ** Math.floor(Math.log10(rough));
  const norm = rough / mag;
  return (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
}

/**
 * points: [{x, y}], sorted by x.
 * opts: { width, height, yMin, yMax, label, color, bands: [{from, to, fill, text, textColor}],
 *         thresholds: [{y, text, color, dash}], marker: {x, text}, xLabel, yFormat }
 */
export function lineChart(points, opts) {
  const {
    width = 760, height = 260, label = 'Chart', color = '#3448F0',
    bands = [], thresholds = [], marker = null, xLabel = 'replay hour', fill = true,
  } = opts;
  const pad = { l: 44, r: 16, t: 16, b: 30 };
  const w = width - pad.l - pad.r;
  const h = height - pad.t - pad.b;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs, xMin + 1);
  let yMin = opts.yMin ?? Math.min(...ys, ...thresholds.map((t) => t.y));
  let yMax = opts.yMax ?? Math.max(...ys, ...thresholds.map((t) => t.y));
  if (opts.yMin == null || opts.yMax == null) {
    const step = niceStep((yMax - yMin) || 1, 5);
    if (opts.yMin == null) yMin = Math.max(0, Math.floor(yMin / step) * step);
    if (opts.yMax == null) yMax = Math.ceil((yMax * 1.05) / step) * step;
  }
  const sx = (x) => pad.l + ((x - xMin) / (xMax - xMin)) * w;
  const sy = (y) => pad.t + h - ((y - yMin) / ((yMax - yMin) || 1)) * h;

  let svg = '';
  bands.forEach((b) => {
    const top = sy(Math.min(b.to, yMax));
    const bottom = sy(Math.max(b.from, yMin));
    svg += `<rect x="${pad.l}" y="${top}" width="${w}" height="${Math.max(0, bottom - top)}" fill="${b.fill}" opacity="0.8"></rect>`;
    if (b.text) svg += `<text x="${pad.l + 8}" y="${top + 16}" font-size="12" fill="${b.textColor}" font-weight="600">${escape(b.text)}</text>`;
  });

  const yStep = niceStep(yMax - yMin || 1, 5);
  for (let y = Math.ceil(yMin / yStep) * yStep; y <= yMax + 1e-9; y += yStep) {
    const py = sy(y);
    svg += `<line x1="${pad.l}" x2="${pad.l + w}" y1="${py}" y2="${py}" stroke="${GRID}" stroke-width="1"></line>`;
    svg += `<text x="${pad.l - 10}" y="${py + 4}" text-anchor="end" font-size="12" fill="${AXIS}" font-family="IBM Plex Mono, monospace">${+y.toFixed(2)}</text>`;
  }
  const xStep = niceStep(xMax - xMin, 6);
  for (let x = Math.ceil(xMin / xStep) * xStep; x <= xMax; x += xStep) {
    svg += `<text x="${sx(x)}" y="${height - 8}" text-anchor="middle" font-size="12" fill="${AXIS}" font-family="IBM Plex Mono, monospace">${x}</text>`;
  }

  thresholds.forEach((t) => {
    const py = sy(t.y);
    svg += `<line x1="${pad.l}" x2="${pad.l + w}" y1="${py}" y2="${py}" stroke="${t.color}" stroke-width="1.5" stroke-dasharray="${t.dash || '6 5'}"></line>`;
    svg += `<text x="${pad.l + 8}" y="${py - 6}" font-size="12" fill="${t.color}" font-weight="600" stroke="#FFFFFF" stroke-width="3" paint-order="stroke">${escape(t.text)}</text>`;
  });

  if (marker && marker.x >= xMin && marker.x <= xMax) {
    const px = sx(marker.x);
    svg += `<line x1="${px}" x2="${px}" y1="${pad.t}" y2="${pad.t + h}" stroke="#0D1526" stroke-width="1" stroke-dasharray="3 4"></line>`;
    if (marker.text) svg += `<text x="${px - 6}" y="${pad.t + 12}" text-anchor="end" font-size="12" fill="#0D1526" font-weight="600">${escape(marker.text)}</text>`;
  }

  if (points.length) {
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(' ');
    const gid = `g${Math.random().toString(36).slice(2, 8)}`;
    if (fill) {
      svg += `<defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="0.14"></stop><stop offset="1" stop-color="${color}" stop-opacity="0"></stop></linearGradient></defs>`;
      svg += `<path d="${d} L${sx(xMax).toFixed(1)} ${sy(yMin)} L${sx(xMin).toFixed(1)} ${sy(yMin)} Z" fill="url(#${gid})"></path>`;
    }
    svg += `<path d="${d}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"></path>`;
    const last = points[points.length - 1];
    svg += `<circle cx="${sx(last.x)}" cy="${sy(last.y)}" r="5" fill="${color}" stroke="#FFFFFF" stroke-width="2"></circle>`;
  }

  return raw(`<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(`${label} (x axis: ${xLabel})`)}">${svg}</svg>`);
}

/** Circular gauge (0–100) used for the asset health index. */
export function gauge(value, color, size = 120) {
  const r = 46;
  const c = 2 * Math.PI * r;
  const filled = value == null ? 0 : (Math.max(0, Math.min(100, value)) / 100) * c;
  return raw(`<svg width="${size}" height="${size}" viewBox="0 0 120 120" role="img" aria-label="Health index ${value ?? 'not available'} of 100">
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="#F6F8FB" stroke-width="10"></circle>
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${filled.toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 60 60)"></circle>
  </svg>`);
}
