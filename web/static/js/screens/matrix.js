// Live risk matrix: 5×5 grid in design-basis or live view, plus the "Why it moved" drawer.

import { api } from '../api.js';
import {
  html, render, icon, riskPill, riskBand, clock, duration, cap, num,
  loading, errorState, on, plural, bandLabel,
} from '../ui.js';

export const title = 'Live risk matrix';
export function subtitle(shell) {
  const n = shell.overview?.unit?.hazop_rows;
  return `Design-basis and live positions for ${n ? plural(n, 'row') : 'all rows'} · select a row to see why it moved`;
}

const SEVERITY = ['Minor', 'Moderate', 'Serious', 'Major', 'Catastrophic'];

export async function mount(el, param, shell) {
  const state = { rows: [], mode: 'live', selected: param, why: null, whyError: null, ruleSet: null };
  render(el, loading(620));

  try {
    const [register, ruleSet] = await Promise.all([
      api.get('/hazop-rows'),
      api.get('/risk-rule-sets/active').catch(() => null),
    ]);
    state.rows = (register.data?.nodes || []).flatMap((n) => n.rows.map((r) => ({ ...r, node: n })));
    state.ruleSet = ruleSet?.data ?? null;
  } catch (err) {
    render(el, errorState(err, 'the risk matrix'));
    return;
  }
  if (!state.rows.some((r) => r.row_code === state.selected)) {
    state.selected = state.rows.find((r) => r.likelihood_live !== r.likelihood_base)?.row_code ?? null;
  }

  const draw = () => render(el, view(state));

  async function loadWhy() {
    state.why = null;
    state.whyError = null;
    draw();
    if (!state.selected) return;
    const code = state.selected;
    try {
      const res = await api.get(`/hazop-rows/${encodeURIComponent(code)}/why`);
      if (code !== state.selected) return;
      state.why = res.data;
    } catch (err) {
      if (code !== state.selected) return;
      state.whyError = err;
    }
    draw();
  }

  on(el, 'click', '[data-row]', (e, btn) => {
    state.selected = btn.dataset.row;
    history.replaceState(null, '', `#/matrix/${state.selected}`);
    loadWhy();
  });
  on(el, 'click', '[data-mode]', (e, btn) => { state.mode = btn.dataset.mode; draw(); });
  on(el, 'click', '[data-act="close"]', () => {
    state.selected = null;
    history.replaceState(null, '', '#/matrix');
    draw();
  });

  await loadWhy();
}

function view(s) {
  const moved = s.rows.filter((r) => r.likelihood_live !== r.likelihood_base);
  const cells = {};
  s.rows.forEach((r) => {
    const l = s.mode === 'live' ? r.likelihood_live : r.likelihood_base;
    (cells[`${l}-${r.severity}`] ||= []).push(r);
  });
  // Ghost markers: in live view show where moved rows came from; in design view where they went.
  const ghosts = {};
  moved.forEach((r) => {
    const l = s.mode === 'live' ? r.likelihood_base : r.likelihood_live;
    (ghosts[`${l}-${r.severity}`] ||= []).push(r);
  });

  const grid = [];
  for (let l = 5; l >= 1; l--) {
    grid.push(html`<div class="axis-x" style="display: flex; align-items: center; justify-content: center">${l}</div>`);
    for (let sv = 1; sv <= 5; sv++) {
      const score = l * sv;
      const band = riskBand(score);
      const k = `${l}-${sv}`;
      grid.push(html`<div class="matrix-cell cell-${band}${band === 'extreme' ? ' hatch' : ''}">
        <span class="matrix-cell-label">${cap(band)} · ${score}</span>
        <div class="matrix-chips">
          ${(cells[k] || []).map((r) => {
            const isMoved = r.likelihood_live !== r.likelihood_base;
            return html`<button type="button" class="row-chip${isMoved && s.mode === 'live' ? ' moved' : ''}" data-row="${r.row_code}" aria-pressed="${r.row_code === s.selected}" title="${r.deviation}">${r.row_code}</button>`;
          })}
          ${(ghosts[k] || []).map((r) => html`<span class="ghost-chip" title="${s.mode === 'live' ? 'Design-basis cell' : 'Live cell'}">${s.mode === 'live' ? '↑ was' : '→ now'} ${r.row_code.replace(/^HZ-/, '')}</span>`)}
        </div>
      </div>`);
    }
  }

  const summary = moved.length
    ? `${plural(moved.length, 'row')} moved in this run. ${moved.map((r) => `${r.row_code} went from ${cap(riskBand(r.likelihood_base * r.severity))} (${r.likelihood_base * r.severity}) to ${cap(r.band_live)} (${r.score_live})`).join('; ')}.`
    : 'No rows have moved. Every row sits at its design-basis cell until a replay degrades a linked asset.';

  return html`<div class="row collapse-lg">
    <section class="card" style="flex: 1 1 0">
      <div class="card-head">
        <div style="display: flex; flex-direction: column; gap: 2px">
          <h2 class="card-title">Likelihood × Severity</h2>
          <span class="muted" style="font-size: 13px">Scored in code by the Risk Engine${s.ruleSet ? ` · rules ${s.ruleSet.version}` : ''}</span>
        </div>
        <div role="group" aria-label="Matrix view" class="seg">
          <button type="button" data-mode="basis" aria-pressed="${s.mode === 'basis'}">Design basis</button>
          <button type="button" data-mode="live" aria-pressed="${s.mode === 'live'}">Live</button>
        </div>
      </div>
      <div class="matrix">
        <div class="axis-y" style="font-size: 13px">Likelihood</div>
        <div style="flex-grow: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0">
          <div class="matrix-grid">${grid}</div>
          <div class="matrix-grid"><div></div>${[1, 2, 3, 4, 5].map((n) => html`<div class="axis-x">${n}</div>`)}</div>
          <div class="matrix-grid"><div></div>${SEVERITY.map((t) => html`<div class="axis-x-label">${t}</div>`)}</div>
        </div>
      </div>
      <div class="legend">
        <span><span style="width: 26px; height: 16px; border-radius: 999px; background: var(--accent)"></span>Selected</span>
        <span><span style="width: 26px; height: 16px; border-radius: 999px; border: 1.5px solid var(--ink)"></span>Re-scored</span>
        <span><span style="width: 26px; height: 16px; border-radius: 999px; border: 1.5px dashed var(--ink-2)"></span>${s.mode === 'live' ? 'Design-basis cell' : 'Live cell'}</span>
        <span><span class="hatch" style="width: 26px; height: 16px; border-radius: 6px; background-color: var(--risk-extreme-bg)"></span>Extreme (hatched)</span>
      </div>
      <p class="note">${summary}</p>
    </section>
    ${drawer(s)}
  </div>`;
}

function drawer(s) {
  const row = s.rows.find((r) => r.row_code === s.selected);
  if (!row) {
    return html`<aside aria-label="Why it moved" class="card drawer">
      <div class="eyebrow">Why it moved</div>
      <div class="empty"><strong>Select a row</strong><span>Pick any row chip in the matrix to see its trigger, the rules that fired, its safeguards and the evidence.</span></div>
    </aside>`;
  }
  const w = s.why;
  const head = html`<div class="drawer-head">
    <div style="display: flex; flex-direction: column; gap: 4px; min-width: 0">
      <div class="eyebrow">Why it moved</div>
      <h2 class="drawer-title">${row.row_code} · ${row.deviation}</h2>
      <span class="ink-2" style="font-size: 14px">${row.node?.name ? `Node ${row.node.code.replace(/^N/, '')} · ` : ''}cause: ${row.cause}</span>
    </div>
    <button type="button" class="icon-btn soft" data-act="close" aria-label="Close panel">${icon('x', { size: 16 })}</button>
  </div>`;
  if (!w) {
    return html`<aside aria-label="Why it moved" class="card drawer">${head}${s.whyError ? html`<div class="empty"><strong>Could not load the explanation</strong><span>${s.whyError.message}</span></div>` : loading(360)}</aside>`;
  }
  const moved = w.live.likelihood !== w.design_basis.likelihood || w.live.severity !== w.design_basis.severity;
  return html`<aside aria-label="Why it moved" class="card drawer">
    ${head}
    <div class="compare">
      <div><span class="muted" style="font-size: 12px">Design basis</span>${riskPill(w.design_basis.score, w.design_basis.band)}<span class="mono ink-2" style="font-size: 12px">L${w.design_basis.likelihood} × S${w.design_basis.severity}</span></div>
      ${icon('arrow', { size: 20, stroke: moved ? '#3448F0' : '#C9D0DC' })}
      <div><span class="muted" style="font-size: 12px">Live</span>${riskPill(w.live.score, w.live.band)}<span class="mono ink-2" style="font-size: 12px">L${w.live.likelihood} × S${w.live.severity}</span></div>
    </div>
    <div class="section">
      <div class="eyebrow">Trigger</div>
      ${w.trigger ? html`
        <div class="line-item"><span class="code">${w.trigger.sensor_tag}</span><span style="color: var(--ink)">${num(w.trigger.value, 2)} ${w.trigger.eng_unit} · ${clock(w.trigger.at)} · hour ${w.trigger.replay_hour}</span></div>
        <div class="line-item"><span>${w.trigger.asset_tag} health index</span><span>${num(w.trigger.health_index_old)} → <b style="color: var(--ink)">${num(w.trigger.health_index_new)}</b></span>
          <span class="pill sm ${w.trigger.band === 'critical' ? 'crit' : 'warn'}">${cap(w.trigger.band)}</span></div>`
        : html`<span class="ink-2" style="font-size: 14px">${moved ? 'Trigger detail is not available yet.' : 'No trigger. This row has not moved in the current run.'}</span>`}
    </div>
    ${w.rules?.length ? html`<div class="section">
      <div class="eyebrow">Rules${w.rule_set_version ? ` · version ${w.rule_set_version}` : ''}</div>
      ${w.rules.map((r) => html`<div class="line-item" style="flex-wrap: nowrap; align-items: flex-start"><span class="code${r.applied ? ' accent' : ''}">${r.rule_id}</span><span style="padding-top: 2px">${r.text}${r.applied ? '' : html` <span class="muted">· not triggered</span>`}</span></div>`)}
    </div>` : ''}
    <div class="section">
      <div class="eyebrow">Safeguards · ${w.safeguards.every((g) => g.credited) ? 'full credit' : 'credit reduced'}</div>
      ${w.safeguards.length ? w.safeguards.map((g) => html`<div class="line-item" style="color: var(--ink)">
        ${icon(g.credited ? 'shield' : 'x', { size: 16, stroke: g.credited ? '#0B7A53' : '#A3211A' })}
        <span class="mono" style="font-size: 13px">${g.ref_code}</span>
        <span class="ink-2" style="font-size: 13px">${dependsText(g)}</span>
      </div>`) : html`<span class="ink-2" style="font-size: 14px">No safeguards linked.</span>`}
    </div>
    ${w.citations?.length ? html`<div class="section">
      <div class="eyebrow">Citations</div>
      ${w.citations.map((c) => citation(c))}
    </div>` : ''}
    <div class="section">
      ${w.audit_id ? html`<span class="eyebrow">Re-scored ${duration(w.latency_s)} after trigger · logged as ${w.audit_id}</span>` : ''}
      <div style="display: flex; gap: 8px; flex-wrap: wrap">
        <a class="btn" href="#/hazop/${row.row_code}">${icon('sparkle', { size: 18 })}Ask Red Team</a>
        <a class="btn primary" style="flex: 1 1 auto" href="#/approvals">${icon('arrow', { size: 18 })}Review in approvals</a>
      </div>
    </div>
  </aside>`;
}

function dependsText(g) {
  const deps = g.depends_on || [];
  if (!g.credited) return 'credit removed';
  const monitored = deps.filter((d) => d.band && d.band !== 'not_monitored');
  if (!monitored.length) return 'no degradation';
  return monitored.map((d) => `${d.tag} ${bandLabel(d.band)}, ${num(d.health_index)}`).join(' · ');
}

function citation(c) {
  let titleText;
  let sub;
  let href = '#/assistant';
  if (c.target_type === 'chunk') {
    titleText = `${c.doc_code}${c.section ? ` §${c.section}` : ''}`;
    sub = c.title;
    href = `#/assistant/${encodeURIComponent(c.doc_code)}`;
  } else if (c.target_type === 'tag_window') {
    titleText = `${c.sensor_tag}`;
    sub = `Sensor window, hours ${c.hour_from}–${c.hour_to}`;
    href = '#/assets';
  } else {
    titleText = c.label || c.doc_code || 'Asset model';
    sub = c.title || '';
  }
  return html`<a class="cite" href="${href}">
    <span class="cite-n">${c.index}</span>
    <span class="cite-body"><span style="font-size: 14px">${titleText}</span>${sub ? html`<span class="muted" style="font-size: 12px">${sub}</span>` : ''}</span>
    ${c.is_synthetic ? html`<span class="tag">Synthetic</span>` : ''}
  </a>`;
}
