// Audit log: append-only record, newest first, with summary tiles and filters.

import { api } from '../api.js';
import { html, render, icon, clock, titleCase, loading, errorState, on } from '../ui.js';

export const title = 'Audit log';
export const subtitle = 'Every draft, re-score, refusal and decision, newest first';

const PAGE = 50;
const TYPES = ['replay', 'health', 're_score', 'proposal', 'approval', 'answer', 'guardrail'];
const typeLabel = (t) => (t === 're_score' ? 'Re-score' : titleCase(t));
const OUTCOME = {
  approved: ['ok', 'Approved'],
  queued: ['accent', 'Queued'],
  refused: ['crit', 'Refused'],
  rejected: ['crit', 'Rejected'],
  not_queued: ['neutral', 'Not queued'],
  answered: ['neutral', 'Answered'],
  logged: ['neutral', 'Logged'],
};

export async function mount(el) {
  const state = { events: null, total: 0, summary: null, error: null, q: '', type: '', actor: '', loadingMore: false };

  const query = (skip) => {
    const p = new URLSearchParams({ skip: String(skip), limit: String(PAGE) });
    if (state.type) p.set('type', state.type);
    if (state.actor) p.set('actor', state.actor);
    return `/audit-events?${p}`;
  };

  const draw = () => {
    const active = document.activeElement;
    const focus = el.contains(active) ? active.id : null;
    const caret = focus ? active.selectionStart : null;
    render(el, view(state));
    const next = focus && document.getElementById(focus);
    if (next) { next.focus(); if (caret != null) try { next.setSelectionRange(caret, caret); } catch { /* select */ } }
  };

  async function load() {
    state.events = null;
    draw();
    try {
      const res = await api.get(query(0));
      state.events = res.data || [];
      state.total = res.metadata?.total ?? state.events.length;
      state.error = null;
    } catch (err) {
      state.events = [];
      state.error = err;
    }
    draw();
  }

  api.get('/audit-events/summary').then((res) => { state.summary = res.data; draw(); }).catch(() => {});

  on(el, 'input', '#audit-search', (e) => { state.q = e.target.value; draw(); });
  on(el, 'change', '#audit-type', (e) => { state.type = e.target.value; load(); });
  on(el, 'change', '#audit-actor', (e) => { state.actor = e.target.value; load(); });
  on(el, 'click', '[data-act="more"]', async () => {
    state.loadingMore = true;
    draw();
    try {
      const res = await api.get(query(state.events.length));
      state.events.push(...(res.data || []));
    } finally {
      state.loadingMore = false;
      draw();
    }
  });

  await load();
}

function visible(s) {
  // Type and actor are filtered server-side; the search box filters the loaded page.
  return (s.events || []).filter((e) => {
    if (s.type && e.type !== s.type) return false;
    if (s.actor && !String(e.actor).toLowerCase().includes(s.actor.toLowerCase())) return false;
    if (!s.q) return true;
    const hay = [e.audit_id, e.event, e.actor, e.model, e.prompt_version, e.rule_set_version, JSON.stringify(e.detail || {})].join(' ').toLowerCase();
    return hay.includes(s.q.toLowerCase());
  });
}

function view(s) {
  const sum = s.summary;
  const rows = visible(s);
  const actors = [...new Set((s.events || []).map((e) => e.actor).filter(Boolean))];
  if (s.actor && !actors.includes(s.actor)) actors.push(s.actor);
  return html`
    <section class="card stat-strip">
      <span class="badge-icon" style="width: 44px; height: 44px; border-radius: 14px; background: var(--accent-soft)">${icon('lock', { size: 20, stroke: '#3448F0' })}</span>
      <div style="display: flex; flex-direction: column; gap: 2px; flex: 1 1 220px">
        <span style="font-size: 15px; font-weight: 600">Append-only record</span>
        <span class="ink-2" style="font-size: 14px">There is no edit or delete path, in the UI or the API.</span>
      </div>
      ${[
        [sum ? `${sum.complete_records_pct}%` : '—', 'complete records'],
        [sum?.events ?? '—', 'events'],
        [sum?.blocked_by_judge ?? '—', 'blocked by Judge'],
        [sum?.refused ?? '—', 'refused'],
      ].map(([v, l]) => html`<div class="stat"><span class="stat-value">${v}</span><span class="stat-label">${l}</span></div>`)}
    </section>
    <section class="card">
      <div class="toolbar">
        <label class="search">${icon('search', { size: 16 })}<input id="audit-search" type="search" placeholder="Search records" aria-label="Search records" value="${s.q}"></label>
        <label class="chip"><select id="audit-type" aria-label="Type">
          <option value="">All types</option>
          ${TYPES.map((t) => html`<option value="${t}"${s.type === t ? html` selected` : ''}>${typeLabel(t)}</option>`)}
        </select></label>
        <label class="chip"><select id="audit-actor" aria-label="Actor">
          <option value="">All actors</option>
          ${actors.map((a) => html`<option value="${a}"${s.actor === a ? html` selected` : ''}>${a}</option>`)}
        </select></label>
      </div>
      ${s.events == null ? loading(360) : s.error ? errorState(s.error, 'the audit log') : html`<div class="table-scroll">
        <div class="audit-grid hz-head" style="padding: 0 14px 4px"><span>Time</span><span>Type</span><span>Event</span><span>Actor</span><span>Model · prompt</span><span>Sources</span><span>Outcome</span></div>
        ${rows.length ? html`<div>${rows.map(rowView)}</div>` : html`<div class="empty" style="margin-top: 8px"><strong>No records match</strong><span>${s.events.length ? 'Clear the search or filters.' : 'Events are written as soon as a replay, answer or decision happens.'}</span></div>`}
      </div>
      ${s.events.length < s.total ? html`<button type="button" class="btn" data-act="more"${s.loadingMore ? html` disabled` : ''}>${s.loadingMore ? 'Loading…' : `Load more (${s.total - s.events.length} older)`}</button>` : ''}`}
    </section>`;
}

function rowView(e) {
  const [cls, label] = OUTCOME[e.outcome] || ['neutral', titleCase(e.outcome || '—')];
  const judge = e.detail?.judge;
  const mp = e.model || e.prompt_version || e.rule_set_version
    ? [e.model, e.prompt_version, e.rule_set_version].filter(Boolean).join(' · ')
    : e.type === 'guardrail' ? 'no model call' : '—';
  return html`<div class="audit-grid audit-row">
    <div style="display: flex; flex-direction: column; gap: 2px"><span class="mono" style="font-size: 13px">${clock(e.at)}</span><span class="mono muted" style="font-size: 11px">${e.audit_id}</span></div>
    <span class="ink-2" style="font-size: 13px">${typeLabel(e.type)}</span>
    <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0">
      <span style="font-size: 14px">${e.event}</span>
      ${judge ? html`<span style="font-size: 12px; color: ${e.outcome === 'not_queued' ? 'var(--crit-ink)' : 'var(--ok-ink)'}">Judge ${e.outcome === 'not_queued' ? '✕' : '✓'} ${judge}</span>` : ''}
      ${e.replay_hour != null ? html`<span class="mono muted" style="font-size: 11px">replay hour ${e.replay_hour}</span>` : ''}
    </div>
    <span style="font-size: 13px">${e.actor}</span>
    <span class="mono ink-2" style="font-size: 12px">${mp}</span>
    <span class="mono ink-2" style="font-size: 13px">${e.sources || '—'}</span>
    <span><span class="pill sm ${cls}">${label}</span></span>
  </div>`;
}
