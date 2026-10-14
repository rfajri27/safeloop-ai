// App shell: login, hash router, sidebar, replay strip and the shared live state.

import { api, auth } from './api.js';
import { html, render, icon, on, toast, toastError, initials, ROLE_LABEL } from './ui.js';
import * as overview from './screens/overview.js';
import * as assets from './screens/assets.js';
import * as matrix from './screens/matrix.js';
import * as hazop from './screens/hazop.js';
import * as assistant from './screens/assistant.js';
import * as approvals from './screens/approvals.js';
import * as audit from './screens/audit.js';
import * as evaluation from './screens/eval.js';

const UNIT = 'U100';
const REFRESH_MS = 10000;
const REPLAY_ROLES = ['reliability_engineer', 'process_safety_engineer', 'admin'];

const ROUTES = {
  overview: { screen: overview, label: 'Overview', icon: 'grid', group: 'main' },
  assets: { screen: assets, label: 'Asset health', icon: 'gauge', group: 'main' },
  matrix: { screen: matrix, label: 'Risk matrix', icon: 'matrix', group: 'main', badge: 'moved' },
  hazop: { screen: hazop, label: 'HAZOP register', icon: 'list', group: 'main' },
  assistant: { screen: assistant, label: 'Assistant', icon: 'chat', group: 'main' },
  approvals: { screen: approvals, label: 'Approvals', icon: 'approve', group: 'main', badge: 'pending' },
  audit: { screen: audit, label: 'Audit log', icon: 'audit', group: 'gov' },
  eval: { screen: evaluation, label: 'Evaluation', icon: 'bolt', group: 'gov' },
};

const PERSONAS = [
  { handle: 'rina', name: 'Rina', role: 'process_safety_engineer', can: 'Approves drafts, runs the Red Team' },
  { handle: 'dimas', name: 'Dimas', role: 'reliability_engineer', can: 'Runs the scenario replay' },
  { handle: 'agus', name: 'Agus', role: 'operator', can: 'Asks the assistant' },
  { handle: 'auditor', name: 'Auditor', role: 'auditor', can: 'Reads everything, asks nothing' },
  { handle: 'admin', name: 'Admin', role: 'admin', can: 'Replay, Red Team, evaluation' },
];

/** Shared state every screen can read. `shell.overview` is refreshed in the background. */
export const shell = {
  overview: null,
  health: null,
  get user() { return auth.user; },
  can(roles) { return roles.includes(auth.user?.role); },
  navigate(path) { location.hash = `#/${path}`; },
  refresh: () => refreshShell(),
};

const $ = (id) => document.getElementById(id);
let cleanup = null;
let timer = null;

// ---------- Login ----------

function showLogin() {
  $('app').hidden = true;
  const root = $('login-root');
  root.hidden = false;
  render(root, html`<div class="login-wrap"><div class="login">
    <div class="brand">
      <svg width="40" height="40" viewBox="0 0 34 34" aria-hidden="true"><rect width="34" height="34" rx="11" fill="#3448F0"></rect><circle cx="17" cy="17" r="8" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-dasharray="38 12.3" transform="rotate(-50 17 17)"></circle><circle cx="23.1" cy="11.9" r="2.4" fill="#FFFFFF"></circle></svg>
      <span style="display: flex; flex-direction: column"><span class="brand-name" style="font-size: 22px">SafeLoop <span>AI</span></span><span class="brand-sub">MVP · Unit 100 · demo login</span></span>
    </div>
    <div style="display: flex; flex-direction: column; gap: 6px">
      <h1 class="display" style="font-size: 24px; font-weight: 600">Choose a demo user</h1>
      <p class="ink-2" style="font-size: 14px">Each persona has a different role. What you can do on each screen follows the role.</p>
    </div>
    <div class="persona-list">
      ${PERSONAS.map((p) => html`<button type="button" class="persona" data-handle="${p.handle}">
        <span class="avatar">${initials(p.name)}</span>
        <span><span class="user-name">${p.name}</span><span class="user-role">${ROLE_LABEL[p.role]}</span></span>
        <span class="persona-can">${p.can}</span>
      </button>`)}
    </div>
    <p class="muted" style="font-size: 12px">Demonstration system. Public and synthetic data only. Advisory only.</p>
  </div></div>`);
}

on($('login-root'), 'click', '.persona', async (e, btn) => {
  btn.disabled = true;
  try {
    await auth.login(btn.dataset.handle);
    $('login-root').hidden = true;
    start();
  } catch (err) {
    btn.disabled = false;
    toastError(err, 'Login');
  }
});

// ---------- Sidebar ----------

function renderNav(active) {
  const item = (key, r) => {
    const current = key === active;
    return html`<a href="#/${key}" class="nav"${current ? html` aria-current="page"` : ''} title="${r.label}">
      ${icon(r.icon)}<span class="label-text">${r.label}</span>
      ${r.badge ? html`<span class="nav-badge" data-badge="${r.badge}" hidden></span>` : ''}
    </a>`;
  };
  const entries = Object.entries(ROUTES);
  render($('nav-main'), entries.filter(([, r]) => r.group === 'main').map(([k, r]) => item(k, r)));
  render($('nav-gov'), html`<span class="nav-label">Governance</span>${entries.filter(([, r]) => r.group === 'gov').map(([k, r]) => item(k, r))}`);
  updateBadges();
}

function updateBadges() {
  const ov = shell.overview;
  const counts = {
    moved: ov?.matrix_summary?.moved ?? 0,
    pending: ov?.loop?.find((s) => s.stage === 'approve')?.pending ?? 0,
  };
  document.querySelectorAll('[data-badge]').forEach((el) => {
    const n = counts[el.dataset.badge];
    el.textContent = n;
    el.hidden = !n;
  });
}

function renderUser() {
  const u = auth.user;
  $('user-avatar').textContent = initials(u?.display_name);
  $('user-name').textContent = u?.display_name || '—';
  $('user-role').textContent = ROLE_LABEL[u?.role] || u?.role || '';
}

$('user-chip').addEventListener('click', () => {
  if (confirm(`Signed in as ${auth.user?.display_name}. Switch to another demo user?`)) {
    auth.logout();
    stop();
    showLogin();
  }
});

function renderHealth() {
  const el = $('llm-status');
  const h = shell.health;
  if (!h) {
    el.innerHTML = '<span class="dot crit"></span>API unreachable';
  } else if (h.db !== 'ok' || h.redis !== 'ok') {
    el.innerHTML = '<span class="dot warn"></span>Some services down';
    el.title = `db ${h.db} · redis ${h.redis} · qdrant ${h.qdrant}`;
  } else {
    el.innerHTML = h.llm_enabled ? '<span class="dot ok"></span>LLM gateway online' : '<span class="dot"></span>LLM gateway off';
    el.title = `db ${h.db} · redis ${h.redis} · qdrant ${h.qdrant}`;
  }
}

// ---------- Replay strip ----------

const SCENARIOS = [
  { code: 'S1', label: 'S1 · P-101 bearing' },
  { code: 'S2', label: 'S2 · TV-301 cooling' },
];
const SPEEDS = [1, 3, 8];

function renderReplay() {
  const run = shell.overview?.replay;
  const allowed = shell.can(REPLAY_ROLES);
  const dis = allowed ? '' : html` disabled title="Your role cannot control the replay"`;
  const running = run?.state === 'running';
  render($('replay-root'), html`<div role="group" aria-label="Scenario replay" class="replay">
    <span class="replay-dot${running ? ' live' : ''}"></span>
    <span class="replay-clock">${run ? `${run.state === 'paused' ? 'PAUSED' : 'REPLAY'} · HOUR ${run.replay_hour}` : 'NO REPLAY'}</span>
    <span class="seg">${SCENARIOS.map((s) => html`<button type="button" data-act="scenario" data-code="${s.code}" aria-pressed="${run?.scenario === s.code}"${dis}>${s.label}</button>`)}</span>
    <span class="seg">${SPEEDS.map((sp) => html`<button type="button" data-act="speed" data-speed="${sp}" aria-pressed="${(run?.speed ?? 8) === sp}"${dis}>${sp}×</button>`)}</span>
    ${run
      ? html`<button type="button" class="icon-btn dark" data-act="${running ? 'pause' : 'resume'}" aria-label="${running ? 'Pause replay' : 'Resume replay'}"${dis}>
          ${running ? html`<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="3" y="2" width="3" height="10" rx="1" fill="#FFFFFF"></rect><rect x="8" y="2" width="3" height="10" rx="1" fill="#FFFFFF"></rect></svg>` : icon('play', { size: 14, stroke: '#FFFFFF' })}
        </button>
        <button type="button" class="icon-btn" data-act="reset" aria-label="Reset scenario"${dis}>${icon('reset', { size: 16 })}</button>`
      : ''}
  </div>`);
}

on($('replay-root'), 'click', 'button[data-act]', async (e, btn) => {
  const run = shell.overview?.replay;
  const act = btn.dataset.act;
  try {
    if (act === 'scenario') {
      if (run && run.scenario !== btn.dataset.code) {
        toast(`Scenario ${run.scenario} is running. Reset it before starting ${btn.dataset.code}.`);
        return;
      }
      if (run) return;
      await api.raw('POST', '/replay-runs', { body: { scenario: btn.dataset.code, speed: run?.speed ?? 8, from_reset: true } });
      toast(`Scenario ${btn.dataset.code} started.`);
    } else if (act === 'speed') {
      if (!run) return;
      await api.raw('POST', `/replay-runs/${run.run_id}/actions`, { body: { action: 'set_speed', speed: Number(btn.dataset.speed) } });
    } else if (run) {
      await api.raw('POST', `/replay-runs/${run.run_id}/actions`, { body: { action: act } });
      if (act === 'reset') toast('Scenario reset. HAZOP rows are back at design-basis risk.');
    }
    refreshShell();
  } catch (err) {
    toastError(err, 'Replay control');
  }
});

// ---------- Live state ----------

async function refreshShell() {
  const [ov, health] = await Promise.allSettled([
    api.get(`/units/${UNIT}/overview`),
    api.raw('GET', '/health', { anonymous: true }),
  ]);
  if (ov.status === 'fulfilled') {
    shell.overview = ov.value.data;
  }
  shell.health = health.status === 'fulfilled' ? health.value.data : health.reason?.data ?? null;
  renderReplay();
  renderHealth();
  updateBadges();
  window.dispatchEvent(new CustomEvent('shell:update'));
}

// ---------- Router ----------

function parseHash() {
  const [key, ...rest] = location.hash.replace(/^#\/?/, '').split('/');
  return { key: ROUTES[key] ? key : 'overview', param: rest.length ? decodeURIComponent(rest.join('/')) : null };
}

async function route() {
  if (!auth.token) return;
  const { key, param } = parseHash();
  const { screen } = ROUTES[key];
  if (typeof cleanup === 'function') cleanup();
  cleanup = null;
  renderNav(key);
  $('page-title').textContent = screen.title;
  $('page-subtitle').textContent = typeof screen.subtitle === 'function' ? screen.subtitle(shell) : screen.subtitle || '';
  document.title = `${screen.title} · SafeLoop AI`;
  // Each mount gets a fresh host, so late async renders from the previous screen land in a detached node.
  const host = document.createElement('div');
  host.className = 'stack';
  $('view').replaceChildren(host);
  window.scrollTo(0, 0);
  const done = await screen.mount(host, param, shell);
  if (host.isConnected) cleanup = done;
  else if (typeof done === 'function') done();
}

window.addEventListener('shell:update', () => {
  const { key } = parseHash();
  const { screen } = ROUTES[key];
  if (typeof screen.subtitle === 'function') $('page-subtitle').textContent = screen.subtitle(shell);
});

function start() {
  $('app').hidden = false;
  renderUser();
  refreshShell().then(route);
  clearInterval(timer);
  timer = setInterval(refreshShell, REFRESH_MS);
}

function stop() {
  clearInterval(timer);
  if (typeof cleanup === 'function') cleanup();
  cleanup = null;
}

auth.onUnauthorized = () => {
  stop();
  toast('Your session expired. Choose a demo user to continue.');
  showLogin();
};

window.addEventListener('hashchange', route);

if (auth.token) start();
else showLogin();
