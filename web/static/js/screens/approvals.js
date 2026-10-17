// Approvals: the human-in-the-loop queue for Red Team proposals and risk re-scores.

import { api } from '../api.js';
import {
  html, render, icon, riskPill, riskBand, checkRow, clock, age, cap,
  loading, on, toast, toastError, ROLE_LABEL,
} from '../ui.js';

export const title = 'Approvals';
export const subtitle = 'Agent drafts and re-scores wait here for a human decision';

const APPROVER_ROLES = ['process_safety_engineer'];
const TYPE_LABEL = { hazop_change: 'HAZOP proposal', risk_rescore: 'Risk re-score', recommendation: 'Recommendation' };
const CHECK_LABEL = {
  entities_in_asset_model: 'Entities in asset model',
  citations_resolve: 'Citations resolve',
  no_control_action_wording: 'No control-action wording',
};

export async function mount(el, param, shell) {
  const state = { filter: 'pending', items: null, error: null, selected: param, detail: null, detailError: null, deciding: false, result: null };

  const draw = () => {
    const reason = el.querySelector('#reason')?.value ?? '';
    render(el, view(state, shell));
    const box = el.querySelector('#reason');
    if (box) box.value = reason;
  };

  async function loadItems() {
    state.items = null;
    draw();
    try {
      const res = await api.get(`/approval-items${state.filter === 'all' ? '' : `?decision=${state.filter}`}`);
      state.items = (res.data || []).filter((i) => state.filter === 'all' || i.decision === state.filter);
      state.error = null;
    } catch (err) {
      state.items = [];
      state.error = err;
    }
    if (!state.items.some((i) => i.id === state.selected)) state.selected = state.items[0]?.id ?? null;
    await loadDetail();
  }

  async function loadDetail() {
    Object.assign(state, { detail: null, detailError: null, result: null });
    draw();
    if (!state.selected) return;
    const id = state.selected;
    try {
      const res = await api.get(`/approval-items/${encodeURIComponent(id)}`);
      if (id !== state.selected) return;
      state.detail = res.data;
    } catch (err) {
      if (id !== state.selected) return;
      state.detailError = err;
    }
    draw();
  }

  async function decide(decision) {
    const reason = el.querySelector('#reason')?.value.trim() ?? '';
    if (decision === 'rejected' && reason.length < 5) {
      toast('Give a reason (at least 5 characters) to reject.', { error: true });
      el.querySelector('#reason')?.focus();
      return;
    }
    state.deciding = true;
    draw();
    try {
      const res = await api.raw('POST', `/approval-items/${encodeURIComponent(state.selected)}/decision`, {
        body: { decision, reason, edited_body: null },
      });
      state.result = res.data;
      const item = state.items.find((i) => i.id === state.selected);
      if (item) item.decision = decision;
      shell.refresh();
    } catch (err) {
      toastError(err, 'Recording the decision');
    } finally {
      state.deciding = false;
      draw();
    }
  }

  on(el, 'click', '[data-item]', (e, btn) => {
    state.selected = btn.dataset.item;
    history.replaceState(null, '', `#/approvals/${state.selected}`);
    loadDetail();
  });
  on(el, 'click', '[data-filter]', (e, btn) => { state.filter = btn.dataset.filter; loadItems(); });
  on(el, 'click', '[data-decide]', (e, btn) => decide(btn.dataset.decide));

  await loadItems();
}

function view(s, shell) {
  return html`<div class="row collapse-lg">
    <section class="card queue" style="gap: 12px">
      <div class="card-head">
        <h2 class="card-title">${cap(s.filter)}${s.items ? ` · ${s.items.length}` : ''}</h2>
        <div class="seg" role="group" aria-label="Filter">
          ${['pending', 'approved', 'rejected'].map((f) => html`<button type="button" data-filter="${f}" aria-pressed="${s.filter === f}">${cap(f)}</button>`)}
        </div>
      </div>
      ${s.items == null ? loading(260) : s.error ? html`<div class="empty"><strong>Could not load the queue</strong><span>${s.error.message}</span></div>`
        : s.items.length ? s.items.map((i) => queueItem(i, s.selected))
        : html`<div class="empty"><strong>Nothing ${s.filter}</strong><span>${s.filter === 'pending' ? 'New drafts and re-scores land here during a replay.' : 'Decisions appear here once made.'}</span></div>`}
      <p class="muted" style="font-size: 13px; line-height: 1.45">Nothing here takes effect until someone approves it. Blocked proposals never reach this queue.</p>
    </section>
    ${detail(s, shell)}
  </div>`;
}

function queueItem(i, selected) {
  const judge = i.artifact_type === 'risk_rescore'
    ? html`<span class="ink-2" style="font-size: 12px">Computed in code · no Judge needed</span>`
    : i.judge === 'pass' ? html`<span style="font-size: 12px; color: var(--ok-ink); font-weight: 600">✓ Judge passed</span>`
    : i.judge ? html`<span style="font-size: 12px; color: var(--crit-ink); font-weight: 600">Judge: ${i.judge}</span>` : '';
  return html`<button type="button" class="queue-item" data-item="${i.id}" aria-pressed="${i.id === selected}">
    <div class="queue-top"><span class="eyebrow">${TYPE_LABEL[i.artifact_type] || i.artifact_type}</span><span class="eyebrow">${age(i.age_s)}</span></div>
    <span style="font-size: 15px; font-weight: 600">${i.title}</span>
    <span class="ink-2" style="font-size: 13px">${i.source}</span>
    ${judge}
  </button>`;
}

function detail(s, shell) {
  if (!s.selected) {
    return html`<section class="card" style="flex: 1 1 0"><div class="empty"><strong>Select an item</strong><span>Pick a draft from the queue to review it.</span></div></section>`;
  }
  if (s.detailError) {
    return html`<section class="card" style="flex: 1 1 0"><div class="empty"><strong>Could not load this item</strong>
      <span>${s.detailError.status === 501 ? 'The approval endpoint is not implemented yet (501).' : s.detailError.message}</span></div></section>`;
  }
  if (!s.detail) return html`<section class="card" style="flex: 1 1 0">${loading(480)}</section>`;

  const d = s.detail;
  const isRescore = d.artifact_type === 'risk_rescore';
  const decided = s.result || (d.decision !== 'pending' ? { decision: d.decision, decided_by: d.decided_by, audit_id: d.audit_id } : null);
  const canDecide = shell.can(APPROVER_ROLES);
  return html`<section class="card" style="flex: 1 1 0">
    <div class="card-head" style="align-items: flex-start">
      <div style="display: flex; flex-direction: column; gap: 8px; min-width: 0">
        <div class="eyebrow">${TYPE_LABEL[d.artifact_type] || d.artifact_type}${d.draft?.kind === 'new_scenario' ? ' · new row' : ''}</div>
        <h2 class="display" style="font-size: 26px; font-weight: 600; letter-spacing: -0.02em">${headline(d)}</h2>
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">${subhead(d)}</div>
      </div>
      <a class="card-link" href="#/${isRescore ? `matrix/${d.draft?.row_code ?? ''}` : `hazop/${d.draft?.parent_row_code ?? ''}`}">${isRescore ? 'View in matrix' : 'View in register'}</a>
    </div>
    ${decided ? html`<div role="status" class="status-banner${decided.decision === 'rejected' ? ' rejected' : ''}">
      ${icon(decided.decision === 'rejected' ? 'x' : 'check', { size: 18, width: 2.4 })}
      <span>${cap(decided.decision)}${decided.decided_by ? ` by ${decided.decided_by}` : ''}${decided.effect?.hazop_row_code ? `. ${decided.effect.hazop_row_code} v${decided.effect.version} is ${decided.effect.status}` : ''}${decided.audit_id ? `. Logged as ${decided.audit_id}` : ''}.</span>
      <a class="card-link" style="margin-left: auto" href="#/audit">Open audit log</a>
    </div>` : ''}
    ${isRescore ? rescoreBody(d) : proposalBody(d)}
    <div class="row wrap" style="gap: 16px">
      ${isRescore ? '' : html`<div class="panel" style="flex: 1 1 260px; gap: 10px">
        <div class="eyebrow">Judge · rules in code</div>
        ${(d.checks || []).map((c) => checkRow({ passed: c.passed, label: CHECK_LABEL[c.check] || c.check, detail: c.detail }))}
        ${d.citations?.length ? html`<div style="display: flex; gap: 6px; flex-wrap: wrap">${d.citations.map((c) => html`<span class="code accent">${c.index} · ${c.label || c.doc_code}</span>`)}</div>` : ''}
      </div>`}
      ${auditBlock(d.audit)}
    </div>
    ${decided ? '' : html`
      <label class="decision-form">
        <span>Reason <span class="muted" style="font-weight: 400">(required to reject, optional to approve)</span></span>
        <textarea id="reason" rows="2" placeholder="Explain your decision for the audit record"${canDecide ? '' : html` disabled`}></textarea>
      </label>
      <div class="decision-bar">
        <span class="muted">${canDecide
          ? `Signing as ${shell.user?.display_name} · ${ROLE_LABEL[shell.user?.role]} · the record can’t be edited or deleted`
          : `Only a process safety engineer can decide. You are signed in as ${shell.user?.display_name} (${ROLE_LABEL[shell.user?.role] || shell.user?.role}).`}</span>
        <button type="button" class="btn danger" data-decide="rejected"${!canDecide || s.deciding ? html` disabled` : ''}>Reject</button>
        <button type="button" class="btn primary" data-decide="approved"${!canDecide || s.deciding ? html` disabled` : ''}>${s.deciding ? 'Saving…' : 'Approve'}</button>
      </div>`}
  </section>`;
}

function headline(d) {
  const x = d.draft || {};
  if (d.artifact_type === 'risk_rescore') return `${x.row_code} · ${cap(x.band_old)} → ${cap(x.band_new)}`;
  return x.proposed_row_code ? `${x.proposed_row_code} · ${x.title}` : x.title || d.title;
}

function subhead(d) {
  const x = d.draft || {};
  if (d.artifact_type === 'risk_rescore') {
    return html`${riskPill(x.score_old, x.band_old)}${icon('arrow', { size: 16, stroke: '#3F4A5C' })}${riskPill(x.score_new, x.band_new)}<span class="muted" style="font-size: 13px">${d.source}</span>`;
  }
  const score = (x.likelihood ?? 0) * (x.severity ?? 0);
  return html`${score ? html`<span class="pill ${riskBand(score)}">${cap(riskBand(score))} · L${x.likelihood} × S${x.severity}</span>` : ''}
    <span class="muted" style="font-size: 13px">${x.parent_row_code ? `Proposed for ${x.parent_row_code} by the Red Team agent` : d.source}</span>`;
}

function field(label, value) {
  return html`<div class="field"><span>${label}</span><div>${value}</div></div>`;
}

function proposalBody(d) {
  const x = d.draft || {};
  return html`<div class="field-grid">
    ${field('Deviation', x.deviation)}
    ${field('Cause', x.cause)}
    ${field('Consequence', x.consequence)}
    ${field('Safeguards', html`<span style="display: flex; gap: 6px; flex-wrap: wrap">${(x.safeguards || []).map((g) => html`<span class="code">${g}</span>`)}</span>`)}
    ${x.recommendation ? field('Recommendation', x.recommendation) : ''}
  </div>`;
}

function rescoreBody(d) {
  const x = d.draft || {};
  const t = x.trigger;
  return html`<div class="field-grid">
    ${field('Deviation', x.deviation)}
    ${field('Likelihood', html`<span class="mono">L${x.likelihood_old} → <b>L${x.likelihood_new}</b> · S${x.severity}</span>`)}
    ${field('Rules applied', html`<span style="display: flex; gap: 6px; flex-wrap: wrap">${(x.rules_applied || []).map((r) => html`<span class="code accent">${r}</span>`)}${x.rule_set_version ? html`<span class="muted" style="font-size: 13px">rule set ${x.rule_set_version}</span>` : ''}</span>`)}
    ${t ? field('Trigger', `${t.asset_tag} ${cap(t.band)}, health index ${t.health_index} at replay hour ${t.replay_hour}`) : ''}
    ${field('Effect if approved', 'The live likelihood is accepted as the row’s current assessment. Rejecting leaves the row unchanged and logs the reason.')}
  </div>`;
}

function auditBlock(a) {
  if (!a) return '';
  return html`<div class="panel" style="flex: 0 1 300px; min-width: 240px; gap: 8px">
    <div class="eyebrow">Audit record</div>
    <div class="kv"><span>Agent</span><span>${a.agent ?? '—'}</span></div>
    <div class="kv"><span>Model</span><span>${a.model_id ?? 'none · in code'}</span></div>
    <div class="kv"><span>Prompt</span><span>${a.prompt_version ?? '—'}</span></div>
    <div class="kv"><span>Sources</span><span>${a.sources ?? '—'}</span></div>
    <div class="kv"><span>Judge</span><span>${a.judge ?? 'not needed'}</span></div>
    <div class="kv"><span>Drafted</span><span>${clock(a.drafted_at)}</span></div>
  </div>`;
}
