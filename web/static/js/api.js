// API client for /api/v1: JWT auth, the {status, data, metadata, message} envelope,
// and AG-UI SSE parsing. The UI shows only what the API returns.

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

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, { body: body ?? {} }),
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

/** POST to a streaming endpoint. Resolves once the stream ends. */
export async function postStream(path, body, onEvent, { signal } = {}) {
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

  if (!res.ok) {
    let payload = null;
    try { payload = await res.json(); } catch { /* ignore */ }
    if (res.status === 401) { auth.logout(); onUnauthorized(); }
    throw new ApiError(res.status, payload?.message || `Request failed (${res.status})`, payload?.data);
  }
  await readEventStream(res.body, onEvent);
}
