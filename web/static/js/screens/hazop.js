// HAZOP register grouped by node, with filters and the Red Team + Judge drawer.

import { api } from '../api.js';
import {
  html, render, icon, riskPill, statusPill, checkRow, titleCase,
  loading, errorState, on, plural, toastError,
} from '../ui.js';

export const title = 'HAZOP register';
export function subtitle(shell) {
  const n = shell.overview?.unit?.hazop_rows;
  return `Unit 100 · Nodes 1 and 2 · ${n ? plural(n, 'row') : 'all rows'} with safeguards linked to assets`;
}

const RED_TEAM_ROLES = ['process_safety_engineer', 'admin'];
const CHECK_LABEL = {
  entities_in_asset_model: 'Entities in asset model',
  citations_resolve: 'Citations resolve',
  no_control_action_wording: 'No control-action wording',
};
const KIND_LABEL = { new_scenario: 'new scenario', worsened: 'worsened', missed_safeguard: 'missed safeguard' };

export async function mount(el, param, shell) {
  const state = {
    nodes: [], selected: param, q: '', node: '', band: '', rescored: false,
    runs: {}, running: false,
  };
  render(el, loading(620));
  try {
    state.nodes = (await api.get('/hazop-rows')).data?.nodes || [];
  } catch (err) {
    render(el, errorState(err, 'the HAZOP register'));
    return;
  }
  const all = state.nodes.flatMap((n) => n.rows);
  if (!all.some((r) => r.row_code === state.selected)) {
    state.selected = all.find((r) => r.rescored_this_run)?.row_code ?? all[0]?.row_code ?? null;
  }

  const draw = () => {
    const active = document.activeElement;
    const focus = el.contains(active) ? active.id : null;
    const caret = focus ? active.selectionStart : null;
    render(el, view(state, shell));
    const next = focus && document.getElementById(focus);
    if (next) {
      next.focus();
      if (caret != null) try { next.setSelectionRange(caret, caret); } catch { /* not a text input */ }
    }
  };

  on(el, 'click', '[data-row]', (e, btn) => {
    state.selected = btn.dataset.row;
    history.replaceState(null, '', `#/hazop/${state.selected}`);
    draw();
  });
  on(el, 'input', '#hz-search', (e) => { state.q = e.target.value; draw(); });
  on(el, 'change', '#hz-node', (e) => { state.node = e.target.value; draw(); });
  on(el, 'change', '#hz-band', (e) => { state.band = e.target.value; draw(); });
  on(el, 'click', '[data-act="rescored"]', () => { state.rescored = !state.rescored; draw(); });
  on(el, 'click', '[data-act="close"]', () => {
    state.selected = null;
    history.replaceState(null, '', '#/hazop');
    draw();
  });
  on(el, 'click', '[data-act="red-team"]', async () => {
    const code = state.selected;
    state.running = true;
    draw();
    try {
      const res = await api.post(`/hazop-rows/${encodeURIComponent(code)}/red-team`, { max_proposals: 2 });
      state.runs[code] = res.data;
      shell.refresh();
    } catch (err) {
      toastError(err, 'The Red Team');
    } finally {
      state.running = false;
      draw();
    }
  });

  draw();
}

function matches(row, s) {
  if (s.band && row.band_live !== s.band) return false;
  if (s.rescored && !row.rescored_this_run) return false;
  if (!s.q) return true;
  const hay = [row.row_code, row.deviation, row.cause, row.consequence, ...row.safeguards.map((g) => g.ref_code)].join(' ').toLowerCase();
  return hay.includes(s.q.toLowerCase());
}

function view(s, shell) {
  const nodes = s.nodes
    .filter((n) => !s.node || n.code === s.node)
    .map((n) => ({ ...n, shown: n.rows.filter((r) => matches(r, s)) }));
  const shownCount = nodes.reduce((acc, n) => acc + n.shown.length, 0);
  return html`<div class="row collapse-lg">
    <section class="card" style="flex: 1 1 0">
      <div class="toolbar">
        <label class="search">${icon('search', { size: 16 })}<input id="hz-search" type="search" placeholder="Search rows, tags" aria-label="Search rows" value="${s.q}"></label>
        <label class="chip"><span class="sr-only">Node</span><select id="hz-node" aria-label="Node">
          <option value="">All nodes</option>
          ${s.nodes.map((n) => html`<option value="${n.code}"${s.node === n.code ? html` selected` : ''}>Node ${n.code.replace(/^N/, '')}</option>`)}
        </select></label>
        <label class="chip"><span class="sr-only">Risk band</span><select id="hz-band" aria-label="Risk band">
          <option value="">Any risk band</option>
          ${['low', 'medium', 'high', 'extreme'].map((b) => html`<option value="${b}"${s.band === b ? html` selected` : ''}>${titleCase(b)}</option>`)}
        </select></label>
        <button type="button" class="chip" data-act="rescored" aria-pressed="${s.rescored}">Re-scored this run</button>
      </div>
      <div class="table-scroll">
        <div class="hz-grid hz-head" style="padding-bottom: 4px"><span>ID</span><span>Deviation</span><span>S · L</span><span>Safeguards</span><span>Live risk</span></div>
        ${shownCount ? nodes.filter((n) => n.shown.length).map((n) => html`
          <div class="hz-node"><span style="font-size: 14px; font-weight: 600">Node ${n.code.replace(/^N/, '')} · ${n.name}</span><span class="muted" style="font-size: 13px">${plural(n.shown.length, 'row')}</span></div>
          ${n.shown.map((r) => rowView(r, s.selected))}
        `) : html`<div class="empty" style="margin-top: 8px"><strong>No rows match</strong><span>Clear the search or filters to see the full register.</span></div>`}
      </div>
      <p class="muted" style="font-size: 13px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap">Loaded from hazop_unit100.json · every safeguard names an asset in the model</p>
    </section>
    ${drawer(s, shell)}
  </div>`;
}

function rowView(r, selected) {
  const moved = r.likelihood_live !== r.likelihood_base;
  return html`<button type="button" class="hz-row hz-grid" data-row="${r.row_code}" aria-pressed="${r.row_code === selected}">
    <span class="hz-id">${r.rescored_this_run ? html`<span class="dot accent" title="Re-scored this run"></span>` : ''}${r.row_code}</span>
    <span class="hz-dev">
      <span style="font-weight: 600">${r.deviation}</span>
      <span class="ink-2" style="font-size: 13px">Cause: ${r.cause}</span>
      <span class="muted" style="font-size: 13px">${r.consequence}</span>
      <span style="margin-top: 2px">${statusPill(r.status)}</span>
    </span>
    <span class="hz-sl"><span>S${r.severity}</span><span>L${r.likelihood_base}${moved ? html` → <b style="color: var(--ink)">L${r.likelihood_live}</b>` : ''}</span></span>
    <span class="hz-sg">${r.safeguards.map((g) => html`<span class="sg${g.credited ? '' : ' lost'}" title="${g.type?.toUpperCase()}${g.credited ? '' : ' · credit removed'}">${icon('shield', { size: 12 })}${g.ref_code}</span>`)}</span>
    <span>${riskPill(r.score_live, r.band_live)}</span>
  </button>`;
}

function drawer(s, shell) {
  const row = s.nodes.flatMap((n) => n.rows).find((r) => r.row_code === s.selected);
  if (!row) {
    return html`<aside aria-label="Red Team on selected row" class="card drawer" style="width: 400px">
      <div class="eyebrow">Red Team · selected row</div>
      <div class="empty"><strong>Select a row</strong><span>The Red Team looks for scenarios the original study missed, and the Judge checks each one in code.</span></div>
    </aside>`;
  }
  const run = s.runs[row.row_code];
  const allowed = shell.can(RED_TEAM_ROLES);
  const runBtn = (label) => html`<button type="button" class="btn${run ? '' : ' primary'}" data-act="red-team"${s.running || !allowed ? html` disabled` : ''}${allowed ? '' : html` title="Only a process safety engineer or admin can run the Red Team"`}>
    ${icon(run ? 'reset' : 'sparkle', { size: 18 })}${s.running ? 'Running…' : label}</button>`;

  return html`<aside aria-label="Red Team on selected row" class="card drawer" style="width: 400px">
    <div class="drawer-head">
      <div style="display: flex; flex-direction: column; gap: 4px; min-width: 0">
        <div class="eyebrow">Red Team · selected row</div>
        <h2 class="drawer-title">${row.row_code} · ${row.deviation}</h2>
        ${run ? html`<span class="eyebrow">${run.prompt_version} · ${run.schema_valid ? 'schema valid' : 'schema invalid'} · ${run.proposals.length} of max 2</span>` : ''}
      </div>
      <button type="button" class="icon-btn soft" data-act="close" aria-label="Close drawer">${icon('x', { size: 16 })}</button>
    </div>
    ${s.running && !run ? loading(260) : run ? run.proposals.map(proposal) : html`<div class="panel">
      <span style="font-size: 14px; font-weight: 600">Look for what the study missed</span>
      <span class="ink-2" style="font-size: 13px; line-height: 1.5">The Red Team agent proposes up to 2 new or worsened scenarios for this row. The Judge then checks, in code, that every entity is in the asset model, every citation resolves and nothing reads like a control action. Only passed proposals reach the approval queue.</span>
      ${allowed ? '' : html`<span class="muted" style="font-size: 13px">Signed in as ${shell.user?.display_name}: only a process safety engineer or admin can start a run.</span>`}
    </div>`}
    <p class="muted" style="font-size: 13px">The Judge runs in code, not in the model. Blocked proposals stay in the audit log with their reason.</p>
    <div style="display: flex; gap: 8px; flex-wrap: wrap">
      ${runBtn(run ? 'Run again' : 'Run Red Team')}
      ${run ? html`<a class="btn primary" style="flex: 1 1 auto" href="#/approvals">${icon('arrow', { size: 18 })}Open in approvals</a>` : ''}
    </div>
  </aside>`;
}

function proposal(p) {
  const passed = p.verdict?.verdict === 'pass';
  const refs = (p.citations || []).map((c) => String(c.ref || '').replace(/^asset_model:/, 'asset model · ').replace(/^doc:/, '').replace('#', ' §'));
  return html`<div class="proposal${passed ? '' : ' blocked'}">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
      <div class="eyebrow">Proposal ${p.index} · ${KIND_LABEL[p.kind] || p.kind}</div>
      <span class="pill sm ${passed ? 'ok' : 'crit'}">${passed ? 'Passed · to approvals' : 'Blocked'}</span>
    </div>
    <span style="font-size: 15px; font-weight: 600">${p.proposed_row_code ? `${p.proposed_row_code} · ` : ''}${p.title}</span>
    <span class="ink-2" style="font-size: 13px; line-height: 1.5">${p.recommendation ? `${p.cause}. ${p.recommendation}` : p.cause}</span>
    ${refs.length ? html`<div style="display: flex; gap: 6px; flex-wrap: wrap">${refs.map((r) => html`<span class="code accent">${r}</span>`)}</div>` : ''}
    <div class="panel" style="gap: 10px">${(p.verdict?.checks || []).map((c) => checkRow({ passed: c.passed, label: CHECK_LABEL[c.check] || c.check, detail: c.detail ?? '' }))}</div>
    ${!passed && p.verdict?.reason ? html`<span style="font-size: 13px; color: var(--crit-ink)">Judge: ${p.verdict.reason}${p.audit_id ? ` · ${p.audit_id}` : ''}</span>` : ''}
  </div>`;
}
