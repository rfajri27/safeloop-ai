// API client for /api/v1: JWT auth, the {status, data, metadata, message} envelope,
// AG-UI SSE parsing, and a fixture fallback for endpoints that still return 501.

const BASE = '/api/v1';
const TOKEN_KEY = 'safeloop.token';
const USER_KEY = 'safeloop.user';

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function store(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* storage blocked: session lives in memory only */ }
}
function load(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

let token = load(TOKEN_KEY);
let user = (() => { try { return JSON.parse(load(USER_KEY) || 'null'); } catch { return null; } })();
let onUnauthorized = () => {};

export const auth = {
  get user() { return user; },
  get token() { return token; },
  set onUnauthorized(fn) { onUnauthorized = fn; },
  async login(handle) {
    const { data } = await request('POST', '/auth/demo-login', { body: { user: handle }, anonymous: true });
    token = data.access_token;
    user = data.user;
    store(TOKEN_KEY, token);
    store(USER_KEY, JSON.stringify(user));
    return user;
  },
  logout() {
    token = null;
    user = null;
    store(TOKEN_KEY, null);
    store(USER_KEY, null);
  },
};

async function request(method, path, { body, anonymous = false, headers = {} } = {}) {
  const init = { method, headers: { Accept: 'application/json', ...headers } };
  if (token && !anonymous) init.headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, 'Cannot reach the SafeLoop API');
  }
  let payload = null;
  try { payload = await res.json(); } catch { /* non-JSON error body */ }
  if (res.status === 401 && !anonymous) {
    auth.logout();
    onUnauthorized();
  }
  if (!res.ok || (payload && payload.status === 0)) {
    throw new ApiError(res.status, payload?.message || `Request failed (${res.status})`, payload?.data);
  }
  return { data: payload?.data, metadata: payload?.metadata, message: payload?.message };
}

// ---------- Fixture fallback ----------
// Endpoints still stubbed on the server answer 501. For those, the UI shows the
// demo fixtures from data/fixtures (same shapes as the API) and labels them as sample data.

const FIXTURES = [
  [/^\/units\/U100\/overview$/, 'units_U100_overview.json'],
  [/^\/assets\/P-101$/, 'assets_P-101.json'],
  [/^\/assets\/P-101\/trend\?sensor_tag=P101_DE_VIB_RMS/, 'assets_P-101_trend.json'],
  [/^\/assets\/P-101\/health-history$/, 'assets_P-101_health-history.json'],
  [/^\/hazop-rows$/, 'hazop-rows.json'],
  [/^\/hazop-rows\/matrix$/, 'hazop-rows_matrix.json'],
  [/^\/hazop-rows\/HZ-N1-003\/why$/, 'hazop-rows_HZ-N1-003_why.json'],
  [/^\/hazop-rows\/HZ-N1-003\/red-team$/, 'red-team-run_HZ-N1-003.json'],
  [/^\/risk-rule-sets\/active$/, 'risk-rule-sets_active.json'],
  [/^\/approval-items(\?.*)?$/, 'approval-items.json'],
  [/^\/approval-items\/(fixture-[\w-]+)$/, (m) => `approval-items_${m[1]}.json`],
  [/^\/audit-events(\?.*)?$/, 'audit-events.json'],
  [/^\/audit-events\/summary(\?.*)?$/, 'audit-events_summary.json'],
  [/^\/eval-runs\/latest(\?.*)?$/, 'eval-runs_latest.json'],
  [/^\/documents(\?.*)?$/, 'documents.json'],
];

function fixtureFor(path) {
  for (const [re, file] of FIXTURES) {
    const m = path.match(re);
    if (m) return typeof file === 'function' ? file(m) : file;
  }
  return null;
}

async function loadFixture(file) {
  const res = await fetch(`/static/fixtures/${file}`);
  if (!res.ok) return null;
  const payload = await res.json();
  return { data: payload.data, metadata: payload.metadata, message: payload.message };
}

/** Is this error "the server has not built this endpoint yet"? */
export const isNotImplemented = (err) => err instanceof ApiError && err.status === 501;

/**
 * Call an endpoint; on 501 fall back to its fixture when one exists.
 * Resolves to { data, metadata, sample } where `sample` marks fixture data.
 */
export async function call(method, path, body) {
  try {
    const out = await request(method, path, { body });
    return { ...out, sample: false };
  } catch (err) {
    if (isNotImplemented(err)) {
      const file = fixtureFor(path);
      const fx = file && await loadFixture(file);
      if (fx) return { ...fx, sample: true };
    }
    throw err;
  }
}

export const api = {
  get: (path) => call('GET', path),
  post: (path, body) => call('POST', path, body ?? {}),
  raw: request,
};

// ---------- AG-UI SSE over fetch (POST streams) ----------

/** Parse an AG-UI text/event-stream body; calls onEvent(payload) per frame. */
export async function readEventStream(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.search(/\r?\n\r?\n/)) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx).replace(/^\r?\n\r?\n/, '');
      const data = frame.split(/\r?\n/).filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n');
      if (!data) continue;
      try { onEvent(JSON.parse(data)); } catch { /* skip malformed frame */ }
    }
    if (done) break;
  }
}

/**
 * POST to a streaming endpoint. Resolves to { sample } once the stream ends.
 * On 501 it replays `fixtureStream` (an SSE text file) so the UI still demonstrates the flow.
 */
export async function postStream(path, body, onEvent, { fixtureStream, signal } = {}) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  }).catch(() => { throw new ApiError(0, 'Cannot reach the SafeLoop API'); });

  if (res.status === 501 && fixtureStream) {
    const fx = await fetch(`/static/fixtures/${fixtureStream}`);
    await readEventStream(slowStream(await fx.text()), onEvent);
    return { sample: true };
  }
  if (!res.ok) {
    let payload = null;
    try { payload = await res.json(); } catch { /* ignore */ }
    if (res.status === 401) { auth.logout(); onUnauthorized(); }
    throw new ApiError(res.status, payload?.message || `Request failed (${res.status})`, payload?.data);
  }
  await readEventStream(res.body, onEvent);
  return { sample: false };
}

/** Turn fixture SSE text into a stream that yields one frame at a time, so playback looks live. */
function slowStream(text) {
  const frames = text.split(/\n\n/).filter((f) => f.trim() && !f.trim().startsWith('#'));
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    async pull(controller) {
      if (i >= frames.length) { controller.close(); return; }
      await new Promise((r) => setTimeout(r, 90));
      controller.enqueue(encoder.encode(frames[i++] + '\n\n'));
    },
  });
}
