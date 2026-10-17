// Shared rendering helpers: escaped templates, icons, pills, formatters, toasts.

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(s);

function part(v) {
  if (v == null || v === false) return '';
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(part).join('');
  return escape(v);
}

/** Tagged template: interpolations are escaped unless wrapped in raw() or produced by html``. */
export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
  return new Raw(out);
}

export function render(el, view) { el.innerHTML = part(view); }

// ---------- Markdown (document passages) ----------

const mdInline = (s) => escape(s)
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');

const mdCells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

/**
 * Minimal markdown for retrieved document text: headings, lists, pipe tables,
 * paragraphs, bold/italic/code. Text is escaped first, so no source HTML survives.
 */
export function markdown(text) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }

    const h = line.match(/^\s*(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (h) {
      out.push(`<div class="md-h md-h${h[1].length}" role="heading" aria-level="${Math.min(h[1].length + 2, 6)}">${mdInline(h[2])}</div>`);
      i += 1; continue;
    }

    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1] || '')) {
      const head = mdCells(line);
      const rows = [];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(mdCells(lines[i])); i += 1; }
      out.push(`<table class="md-table"><thead><tr>${head.map((c) => `<th>${mdInline(c)}</th>`).join('')}</tr></thead>`
        + `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${mdInline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
      continue;
    }

    const li = line.match(/^\s*([-*+]|\d+[.)])\s+/);
    if (li) {
      const ordered = /\d/.test(li[1]);
      const re = ordered ? /^\s*\d+[.)]\s+(.*)$/ : /^\s*[-*+]\s+(.*)$/;
      const items = [];
      while (i < lines.length && re.test(lines[i])) { items.push(lines[i].match(re)[1]); i += 1; }
      const tag = ordered ? 'ol' : 'ul';
      out.push(`<${tag} class="md-list">${items.map((t) => `<li>${mdInline(t)}</li>`).join('')}</${tag}>`);
      continue;
    }

    const para = [];
    while (i < lines.length && lines[i].trim()
      && !/^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)/.test(lines[i])) { para.push(mdInline(lines[i].trim())); i += 1; }
    if (!para.length) { para.push(mdInline(line.trim())); i += 1; }
    out.push(`<p>${para.join('<br>')}</p>`);
  }
  return raw(`<div class="md">${out.join('')}</div>`);
}

// ---------- Icons (inline stroke SVG from the design) ----------

const P = {
  grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="2.2"></rect><rect x="13.5" y="3" width="7.5" height="7.5" rx="2.2"></rect><rect x="3" y="13.5" width="7.5" height="7.5" rx="2.2"></rect><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2.2"></rect>',
  gauge: '<path d="M5 18a8 8 0 1 1 14 0"></path><path d="M12 14l3-4"></path>',
  matrix: '<rect x="3" y="3" width="18" height="18" rx="4"></rect><path d="M3 9h18M3 15h18M9 3v18M15 3v18"></path>',
  list: '<path d="M9 6h12M9 12h12M9 18h12"></path><path d="M4 6h1M4 12h1M4 18h1"></path>',
  chat: '<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8l-5 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"></path>',
  approve: '<circle cx="12" cy="12" r="9"></circle><path d="M8 12.5l2.7 2.7L16.5 9.5"></path>',
  audit: '<path d="M5 4h14v16H5z"></path><path d="M9 8h6M9 12h6M9 16h3"></path>',
  bolt: '<path d="M13 3L5 13h6l-1 8 8-10h-6z"></path>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"></path>',
  reset: '<path d="M4 12a8 8 0 1 0 2.4-5.7"></path><path d="M4 4v4h4"></path>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"></path><path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z"></path>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"></path><path d="M9 12l2 2 4-4"></path>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"></path>',
  x: '<path d="M6 6l12 12M18 6L6 18"></path>',
  search: '<circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path>',
  send: '<path d="M5 12h14M13 6l6 6-6 6"></path>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path>',
  doc: '<path d="M7 3h7l5 5v13H7z"></path><path d="M14 3v5h5"></path>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"></path><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"></path>',
  play: '<path d="M7 5l12 7-12 7z"></path>',
  logout: '<path d="M15 4h4v16h-4"></path><path d="M10 8l-4 4 4 4M6 12h10"></path>',
  warn: '<path d="M12 4l9 16H3z"></path><path d="M12 10v4M12 17h.01"></path>',
  question: '<circle cx="12" cy="12" r="9"></circle><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.3M12 17h.01"></path>',
};

export function icon(name, { size = 20, stroke = 'currentColor', width = 1.75, label } = {}) {
  const a11y = label ? `role="img" aria-label="${escape(label)}"` : 'aria-hidden="true"';
  return raw(`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" ${a11y}>${P[name] || ''}</svg>`);
}

/** Small filled shapes used for health bands: circle (healthy), triangle (degraded), diamond (critical). */
export function bandShape(band, size = 9) {
  const shapes = {
    healthy: '<circle cx="5" cy="5" r="4.5" fill="#0B7A53"></circle>',
    degraded: '<path d="M5 0.5L9.6 9.2H0.4z" fill="#9A5B00"></path>',
    critical: '<path d="M5 0.3L9.7 5 5 9.7 0.3 5z" fill="#C4281C"></path>',
  };
  const shape = shapes[band] || '<circle cx="5" cy="5" r="4" fill="none" stroke="#5E6878" stroke-width="1.2"></circle>';
  return raw(`<svg width="${size}" height="${size}" viewBox="0 0 10 10" aria-hidden="true">${shape}</svg>`);
}

// ---------- Labels and pills ----------

export const cap = (s) => (s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : '');
export const titleCase = (s) => String(s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export function bandLabel(band) {
  if (!band) return 'No data';
  if (band === 'not_monitored') return 'Not monitored';
  return cap(band);
}

export function healthBand(band) {
  const cls = ['healthy', 'degraded', 'critical'].includes(band) ? band : 'none';
  return html`<span class="band ${cls}">${bandShape(band)}${bandLabel(band)}</span>`;
}

export function riskBand(score) {
  if (score >= 15) return 'extreme';
  if (score >= 10) return 'high';
  if (score >= 5) return 'medium';
  return 'low';
}

export function riskPill(score, band = riskBand(score), { small = false } = {}) {
  return html`<span class="pill ${band}${small ? ' sm' : ''}">${cap(band)} · ${score}</span>`;
}

const STATUS = {
  approved: ['ok', 'Approved'],
  under_review: ['accent', 'Under review'],
  draft: ['neutral', 'Draft'],
  rejected: ['crit', 'Rejected'],
  superseded: ['neutral', 'Superseded'],
  pending: ['accent', 'Pending'],
};
export function statusPill(status) {
  const [cls, label] = STATUS[status] || ['neutral', titleCase(status)];
  return html`<span class="pill sm ${cls}">${label}</span>`;
}

export function checkRow({ passed, label, detail }) {
  return html`<div class="check${passed ? '' : ' fail'}">
    <span class="mark">${icon(passed ? 'check' : 'x', { size: 12, width: 2.6 })}</span>
    <span>${label}</span>
    <span class="detail">${detail ?? (passed ? 'pass' : 'fail')}</span>
  </div>`;
}

// ---------- Formatting ----------

export function clock(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function duration(seconds) {
  if (seconds == null) return '—';
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${Math.round(seconds * 10) / 10} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s ? `${m} m ${s} s` : `${m} m`;
}

export function age(seconds) {
  if (seconds == null) return '';
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} d`;
}

export const num = (v, digits = 0) => (v == null ? '—' : Number(v).toFixed(digits).replace(/\.0+$/, ''));

export function plural(n, word, pluralWord = `${word}s`) {
  return `${n} ${n === 1 ? word : pluralWord}`;
}

export const ROLE_LABEL = {
  process_safety_engineer: 'Process Safety Eng.',
  reliability_engineer: 'Reliability Eng.',
  operator: 'Operator',
  trainee: 'Trainee',
  plant_manager: 'Plant Manager',
  auditor: 'Auditor',
  admin: 'Admin',
};

export const initials = (name) => String(name || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();

// ---------- States ----------

export function loading(height = 280) {
  return html`<div class="skeleton" style="height: ${height}px" aria-label="Loading"></div>`;
}

export function errorState(err, what = 'this view') {
  const unavailable = err?.status === 501;
  return html`<div class="card"><div class="empty">
    <strong>${unavailable ? `${cap(what)} is not available yet` : `Could not load ${what}`}</strong>
    <span>${unavailable ? 'The server endpoint for this is not implemented yet (501).' : err?.message || 'Unknown error'}</span>
  </div></div>`;
}

export function toast(message, { error = false, timeout = 4200 } = {}) {
  const root = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast${error ? ' error' : ''}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), timeout);
}

/** Toast an API failure; explains 501/403/409 in plain words. */
export function toastError(err, action = 'That action') {
  if (err?.status === 501) toast(`${action} is not available yet: the server endpoint returns 501.`, { error: true });
  else toast(err?.message || `${action} failed`, { error: true });
}

/** Event delegation: on(root, 'click', '[data-act="x"]', handler). */
export function on(root, type, selector, handler) {
  root.addEventListener(type, (e) => {
    const target = e.target.closest(selector);
    if (target && root.contains(target)) handler(e, target);
  });
}
