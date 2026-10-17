// Overview: headline alert, health tiles, live risk summary, the loop and recent activity.

import { api } from '../api.js';
import {
  html, render, icon, bandShape, healthBand, riskPill, riskBand, clock, duration,
  loading, errorState, plural, num,
} from '../ui.js';

export const title = 'Unit 100 overview';
export function subtitle(shell) {
  const u = shell.overview?.unit;
  return u ? `${u.name} · Nodes 1 and 2 · ${plural(u.assets, 'asset')} · ${plural(u.hazop_rows, 'HAZOP row')}` : '';
}

export async function mount(el, _param, shell) {
  let register = null;

  const draw = () => {
    if (!shell.overview) { render(el, loading(520)); return; }
    render(el, view(shell.overview, register));
  };

  const loadRegister = async () => {
    try { register = (await api.get('/hazop-rows')).data; } catch { register = null; }
    draw();
  };

  const onUpdate = () => loadRegister();
  window.addEventListener('shell:update', onUpdate);
  draw();
  loadRegister();
  if (!shell.overview) {
    await shell.refresh();
    if (!shell.overview) render(el, errorState({ message: 'The unit overview did not load.' }, 'the overview'));
  }
  return () => window.removeEventListener('shell:update', onUpdate);
}

function view(ov, register) {
  const nodes = register?.nodes ?? [];
  const rows = nodes.flatMap((n) => n.rows);
  const nodeNames = Object.fromEntries(nodes.map((n) => [n.code, n.name]));
  return html`
    ${headline(ov.headline)}
    <div class="row collapse-lg">
      ${healthCard(ov.health_tiles, nodeNames)}
      ${riskNowCard(rows, ov.matrix_summary)}
      ${rescoredCard(ov.rescored_rows, ov.red_team_summary)}
    </div>
    <div class="row collapse-lg">
      ${loopCard(ov)}
      ${activityCard(ov.activity)}
    </div>`;
}

function headline(h) {
  if (!h) return '';
  const tone = { warning: 'warning', critical: 'critical' }[h.tone] || '';
  const glyph = tone === 'critical' ? bandShape('critical', 16) : tone === 'warning' ? bandShape('degraded', 16) : icon('shield', { size: 18, stroke: '#3448F0' });
  return html`<section aria-label="Advisory alert" class="alert ${tone}">
    <span class="alert-icon">${glyph}</span>
    <div class="alert-body">
      <div class="alert-title">${h.title}</div>
      <div class="alert-detail">${h.detail}</div>
    </div>
    ${h.latency_s != null ? html`<span class="mono muted" style="font-size: 12px">${duration(h.latency_s)} after trigger</span>` : ''}
    ${h.link?.row_code ? html`<a class="btn primary" href="#/matrix/${h.link.row_code}">${icon('arrow', { size: 18 })}See why</a>` : ''}
  </section>`;
}

const DATASET_SHORT = [[/tennessee eastman/i, 'TEP'], [/nasa ims/i, 'NASA IMS']];
function provenance(tile) {
  if (!tile) return '';
  if (tile.origin === 'synthetic') return '';
  const ds = tile.source_dataset || '';
  return DATASET_SHORT.find(([re]) => re.test(ds))?.[1] || ds;
}

function nodeProvenance(tiles) {
  const sources = [...new Set(tiles.map(provenance).filter(Boolean))];
  const proxy = tiles.some((t) => t.origin === 'public_proxy');
  return `${proxy ? 'Proxy · ' : ''}${sources.join(' + ')}`;
}

function healthCard(tiles = [], nodeNames) {
  const byNode = {};
  tiles.forEach((t) => { (byNode[t.node || '—'] ||= []).push(t); });
  return html`<section class="card grow" style="flex: 1 1 0">
    <div class="card-head"><h2 class="card-title">Unit 100 health</h2><span class="muted" style="font-size: 13px">Health index 0–100</span></div>
    ${Object.keys(byNode).length ? Object.entries(byNode).map(([code, list]) => html`<div class="node-block">
      <div class="node-head">
        <span class="node-code">NODE ${code.replace(/^N/, '')}</span>
        <span class="node-name">${nodeNames[code] || ''}</span>
        <span style="margin-left: auto"><span class="tag">${nodeProvenance(list)}</span></span>
      </div>
      <div class="tiles">${list.map((t) => html`<a class="tile ${t.band || ''}" href="#/assets/${t.tag}">
        <div class="tile-line"><span class="tile-tag">${t.tag}</span><span class="tile-hi">${num(t.health_index)}</span></div>
        <div class="tile-line"><span class="tile-name">${t.name}</span>${healthBand(t.band)}</div>
      </a>`)}</div>
    </div>`) : html`<div class="empty"><strong>No monitored assets</strong><span>The Unit 100 asset model has not been loaded yet.</span></div>`}
    <div class="legend">
      <span>${bandShape('healthy', 10)}Healthy ≥ 80</span>
      <span>${bandShape('degraded', 10)}Degraded 50–79</span>
      <span>${bandShape('critical', 10)}Critical &lt; 50</span>
      ${tiles.some((t) => t.health_index == null) ? html`<span>${bandShape(null, 10)}No data until a replay runs</span>` : ''}
    </div>
  </section>`;
}

function riskNowCard(rows, summary = {}) {
  const live = {};
  const moved = new Set();
  rows.forEach((r) => {
    const k = `${r.likelihood_live}-${r.severity}`;
    live[k] = (live[k] || 0) + 1;
    if (r.likelihood_live !== r.likelihood_base) moved.add(k);
  });
  const cells = [];
  for (let l = 5; l >= 1; l--) {
    cells.push(html`<div class="axis-n">${l}</div>`);
    for (let s = 1; s <= 5; s++) {
      const band = riskBand(l * s);
      const k = `${l}-${s}`;
      cells.push(html`<div class="mini-cell cell-${band}${band === 'extreme' ? ' hatch' : ''}${moved.has(k) ? ' moved' : ''}" title="L${l} × S${s} = ${l * s}">${live[k] || ''}</div>`);
    }
  }
  const total = rows.length;
  return html`<section class="card" style="width: 312px; flex-shrink: 0; gap: 14px">
    <div class="card-head"><h2 class="card-title">Risk now</h2><a class="card-link" href="#/matrix">Open</a></div>
    <div class="mini-matrix" role="img" aria-label="Live risk matrix: ${summary.low ?? 0} low, ${summary.medium ?? 0} medium, ${summary.high ?? 0} high, ${summary.extreme ?? 0} extreme">
      <div class="axis-y">Likelihood</div>
      <div style="flex-grow: 1; display: flex; flex-direction: column; gap: 6px">
        <div class="mini-grid">${cells}</div>
        <div class="mini-grid"><div></div>${[1, 2, 3, 4, 5].map((s) => html`<div class="axis-n">${s}</div>`)}</div>
        <div class="muted" style="text-align: center; font-size: 12px">Severity</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 16px; background: var(--accent-soft)">
      <span style="width: 18px; height: 18px; border-radius: 6px; box-shadow: inset 0 0 0 2px var(--accent); flex-shrink: 0"></span>
      <span style="font-size: 13px"><b>${plural(summary.moved ?? 0, 'row')}</b> moved cell this run</span>
    </div>
    <p class="muted" style="font-size: 13px; line-height: 1.45">${total || '—'} rows: ${summary.low ?? 0} Low, ${summary.medium ?? 0} Medium, ${summary.high ?? 0} High, ${summary.extreme ?? 0} Extreme.</p>
  </section>`;
}

function rescoredCard(rescored = [], redTeam) {
  return html`<section class="card" style="width: 360px; flex-shrink: 0; gap: 12px">
    <div class="card-head"><h2 class="card-title">Re-scored rows</h2></div>
    ${rescored.length ? rescored.map((r) => html`<a class="link-card" href="#/matrix/${r.row_code}">
      <div class="link-card-top">
        <span class="mono muted" style="font-size: 13px">${r.row_code}</span>
        <span class="mono ink-2" style="margin-left: auto; font-size: 12px">L${r.likelihood_old} → L${r.likelihood_new} · S${r.severity}</span>
      </div>
      <span style="font-size: 15px; font-weight: 600">${r.deviation}</span>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
        ${riskPill(r.score_old)}${icon('arrow', { size: 16, stroke: '#3F4A5C' })}${riskPill(r.score_new)}
      </div>
    </a>`) : html`<div class="empty"><strong>No rows moved</strong><span>Every HAZOP row is at its design-basis risk.</span></div>`}
    <div class="panel">
      <span style="display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600">${icon('sparkle', { size: 16, stroke: '#3448F0' })}${redTeam ? `Red Team on ${redTeam.row_code}` : 'Red Team'}</span>
      ${redTeam
        ? html`<span class="ink-2" style="font-size: 13px; line-height: 1.45">${plural(redTeam.proposals, 'proposal')}. Judge passed ${redTeam.passed}, blocked ${redTeam.blocked}.</span>
          <a class="card-link" href="#/approvals">Review in approvals</a>`
        : html`<span class="ink-2" style="font-size: 13px; line-height: 1.45">Not run on this replay yet. Pick a re-scored row in the register to look for missed scenarios.</span>
          <a class="card-link" href="#/hazop${rescored[0] ? `/${rescored[0].row_code}` : ''}">Open register</a>`}
    </div>
  </section>`;
}

const STAGES = {
  sense: { n: 1, label: 'Sense' },
  rescore: { n: 2, label: 'Re-score' },
  red_team: { n: 3, label: 'Red Team + Judge' },
  approve: { n: 4, label: 'Approve' },
};

function loopCard(ov) {
  const loop = ov.loop || [];
  const done = loop.filter((s) => s.done).length;
  const firstOpen = loop.findIndex((s) => !s.done);
  const pending = loop.find((s) => s.stage === 'approve')?.pending ?? 0;
  const rt = ov.red_team_summary;
  const detail = {
    sense: (s) => (s.done ? ov.headline?.title?.split('. ')[0] : 'Waiting for a health band change'),
    rescore: (s) => (s.done ? `${plural(ov.rescored_rows?.length ?? 0, 'row')} · rules in code` : 'Waiting for a trigger'),
    red_team: () => (rt ? `${plural(rt.proposals, 'proposal')} · ${rt.passed} passed · ${rt.blocked} blocked` : 'Not run yet'),
    approve: () => (pending ? `${plural(pending, 'draft')} waiting for a decision` : 'Nothing waiting'),
  };
  const time = (s) => (s.at ? clock(s.at) : s.offset_s != null ? `+${duration(s.offset_s)}` : s.stage === 'approve' && pending ? 'now' : '');
  const arcs = [0, 1, 2, 3].map((i) => html`<circle cx="80" cy="80" r="62" fill="none" stroke="${loop[i]?.done ? '#3448F0' : '#C9D0DC'}" stroke-width="12" stroke-linecap="round" stroke-dasharray="87.4 302.2" transform="rotate(${-85.4 + 90 * i} 80 80)"></circle>`);
  return html`<section class="card grow" style="flex: 1 1 0">
    <div class="card-head">
      <h2 class="card-title">The loop${ov.replay ? ` · ${ov.replay.scenario} run` : ''}</h2>
      ${ov.replay?.state === 'running' ? html`<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--accent); font-weight: 600"><span class="dot accent"></span>Live</span>` : ''}
    </div>
    <div class="loop">
      <div class="ring">
        <svg width="160" height="160" viewBox="0 0 160 160" role="img" aria-label="Loop progress: ${done} of 4 stages complete"><circle cx="80" cy="80" r="62" fill="none" stroke="#F6F8FB" stroke-width="12"></circle>${arcs}</svg>
        <div class="ring-center"><span class="ring-value">${done}/4</span><span class="muted" style="font-size: 12px">stages done</span></div>
      </div>
      <div class="steps">${loop.map((s, i) => {
        const meta = STAGES[s.stage] || { n: i + 1, label: s.stage };
        const state = s.done ? 'done' : i === firstOpen ? 'current' : '';
        return html`<div class="step ${state}">
          <span class="step-mark">${s.done ? icon('check', { size: 13, width: 2.4, stroke: '#FFFFFF' }) : state === 'current' ? html`<span class="dot accent"></span>` : ''}</span>
          <div class="step-body"><span class="step-title">${meta.n}. ${meta.label}</span><span class="step-detail">${(detail[s.stage] || (() => ''))(s)}</span></div>
          <span class="step-time">${time(s)}</span>
        </div>`;
      })}</div>
    </div>
    <a class="btn primary block" href="#/approvals">${icon('arrow', { size: 18 })}${pending ? `Review ${plural(pending, 'draft')}` : 'Open approvals'}</a>
  </section>`;
}

const ACTOR_DOT = [[/judge/i, 'crit'], [/health/i, 'warn'], [/risk/i, 'accent'], [/red team|redteam/i, ''], [/guardrail/i, '']];
function activityCard(items = []) {
  const dot = (actor) => ACTOR_DOT.find(([re]) => re.test(actor || ''))?.[1] ?? '';
  return html`<section class="card" style="width: 520px; flex-shrink: 0; gap: 6px">
    <div class="card-head"><h2 class="card-title">Activity</h2><a class="card-link" href="#/audit">Audit log</a></div>
    <div class="feed">${items.length ? items.map((a) => html`<div class="feed-item">
      <span class="feed-time">${clock(a.at)}</span>
      <span class="dot ${dot(a.actor)}" style="${/red team|redteam/i.test(a.actor) ? 'background: var(--ink)' : ''}"></span>
      <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0"><span class="feed-text">${a.text}</span><span class="feed-actor">${a.actor} · ${a.audit_id}</span></div>
    </div>`) : html`<div class="empty" style="margin-top: 8px"><strong>No activity yet</strong><span>Events appear here once a replay starts.</span></div>`}</div>
  </section>`;
}
