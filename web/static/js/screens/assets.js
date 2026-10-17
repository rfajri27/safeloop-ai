// Asset health: picker, health index gauge, sensor trend, health history and linked HAZOP rows.

import { api } from '../api.js';
import { lineChart, gauge } from '../charts.js';
import {
  html, render, icon, bandShape, riskPill, clock, num, cap, titleCase,
  loading, errorState, on, plural, bandLabel,
} from '../ui.js';

export const title = 'Asset health';
export const subtitle = 'Health index, sensor trend and the HAZOP rows each asset feeds';

const BAND_COLOR = { healthy: '#0B7A53', degraded: '#9A5B00', critical: '#C4281C' };

export async function mount(el, tagParam, shell) {
  const state = { list: [], tag: tagParam, detail: null, detailError: null, sensor: null, trend: null, trendError: null, history: null };
  render(el, loading(560));

  try {
    state.list = (await api.get('/assets')).data || [];
  } catch (err) {
    render(el, errorState(err, 'assets'));
    return;
  }
  if (!state.list.length) {
    render(el, html`<div class="card"><div class="empty"><strong>No monitored assets</strong><span>The Unit 100 asset model has not been loaded yet.</span></div></div>`);
    return;
  }
  if (!state.list.some((a) => a.tag === state.tag)) state.tag = state.list[0].tag;

  const draw = () => render(el, view(state));

  async function loadTrend() {
    state.trend = null;
    state.trendError = null;
    draw();
    if (!state.sensor) return;
    try {
      const res = await api.get(`/assets/${encodeURIComponent(state.tag)}/trend?sensor_tag=${encodeURIComponent(state.sensor)}`);
      state.trend = res.data;
    } catch (err) {
      state.trendError = err;
    }
    draw();
  }

  async function loadAsset() {
    Object.assign(state, { detail: null, detailError: null, history: null, sensor: null, trend: null, trendError: null });
    draw();
    const tag = encodeURIComponent(state.tag);
    const [detail, history] = await Promise.allSettled([api.get(`/assets/${tag}`), api.get(`/assets/${tag}/health-history`)]);
    if (detail.status === 'fulfilled') {
      state.detail = detail.value.data;
      state.sensor = state.detail.sensor_tags?.[0]?.tag ?? null;
    } else {
      state.detailError = detail.reason;
    }
    if (history.status === 'fulfilled') {
      state.history = history.value.data;
    }
    await loadTrend();
  }

  on(el, 'click', '[data-asset]', (e, btn) => {
    if (btn.dataset.asset === state.tag) return;
    state.tag = btn.dataset.asset;
    history.replaceState(null, '', `#/assets/${state.tag}`);
    loadAsset();
  });
  on(el, 'click', '[data-sensor]', (e, btn) => {
    state.sensor = btn.dataset.sensor;
    loadTrend();
  });

  await loadAsset();
}

function view(s) {
  const item = s.list.find((a) => a.tag === s.tag);
  return html`
    <div role="group" aria-label="Choose asset" class="asset-picker">
      ${s.list.map((a) => html`<button type="button" class="asset-btn" data-asset="${a.tag}" aria-pressed="${a.tag === s.tag}">
        ${bandShape(a.band, 10)}<span>${a.tag}</span><span>${num(a.health_index)}</span>
      </button>`)}
    </div>
    ${hero(item, s)}
    <div class="row collapse-lg">
      <div class="stack" style="flex: 1 1 0">
        ${trendCard(s)}
        ${historyCard(s)}
      </div>
      <div class="stack side-col">${feedsCard(s)}</div>
    </div>`;
}

function hero(item, s) {
  const d = s.detail;
  // List values win so the gauge always matches the overview tiles.
  const hi = item?.health_index ?? d?.health_index;
  const band = item?.band ?? d?.band;
  const change = d?.last_band_change;
  const rows = d?.feeds_rows || [];
  const bandCounts = rows.reduce((acc, r) => ({ ...acc, [r.band]: (acc[r.band] || 0) + 1 }), {});
  return html`<section class="card asset-hero">
    <div class="gauge">${gauge(hi, BAND_COLOR[band] || '#C9D0DC')}
      <div class="gauge-center"><span class="gauge-value">${num(hi)}</span><span class="muted" style="font-size: 12px; margin-top: 4px">Health index</span></div>
    </div>
    <div class="hero-main">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <span class="hero-name">${item?.tag} · ${item?.name}</span>
        ${band ? html`<span class="pill ${band === 'healthy' ? 'ok' : band === 'degraded' ? 'warn' : 'crit'}">${cap(band)}</span>` : html`<span class="pill neutral">No data yet</span>`}
      </div>
      <div class="ink-2" style="font-size: 15px">
        ${d ? html`${titleCase(d.asset_class)} · Node ${d.node?.code?.replace(/^N/, '')} ${d.node?.name}${d.standby ? html` · Standby ${d.standby.tag} (${bandLabel(d.standby.band)}, ${num(d.standby.health_index)})` : ''}` : html`Node ${item?.node?.replace(/^N/, '') ?? '—'}`}
      </div>
      ${hi == null ? html`<span class="muted" style="font-size: 13px">Health is computed once a scenario replay is running.</span>` : ''}
    </div>
    <div class="hero-stat">
      <span class="muted" style="font-size: 13px">Band changed</span>
      <span class="hero-stat-value">${change ? clock(change.at) : '—'}</span>
      <span class="ink-2" style="font-size: 13px">${change ? `${cap(change.from)} → ${cap(change.to)} · hour ${change.replay_hour}` : 'No change this run'}</span>
    </div>
    <div class="hero-stat">
      <span class="muted" style="font-size: 13px">Feeds HAZOP rows</span>
      <span class="hero-stat-value">${d ? rows.length : '—'}</span>
      <span class="ink-2" style="font-size: 13px">${Object.entries(bandCounts).map(([b, n]) => `${n} ${cap(b)}`).join(' · ') || '—'}</span>
    </div>
  </section>`;
}

function trendCard(s) {
  const d = s.detail;
  const sensors = d?.sensor_tags || [];
  const meta = sensors.find((t) => t.tag === s.sensor);
  const t = s.trend;
  const pts = (t?.points || []).map((p) => ({ x: p.replay_hour, y: p.value }));
  const last = pts[pts.length - 1];
  const thresholds = [];
  if (t?.alert_high != null) thresholds.push({ y: t.alert_high, text: `Alert ${t.alert_high}`, color: '#C4281C' });
  if (t?.alert_high_tightened != null) thresholds.push({ y: t.alert_high_tightened, text: `Tightened ${t.alert_high_tightened}`, color: '#9A5B00', dash: '2 4' });
  const change = d?.last_band_change;

  let body;
  if (s.detailError) body = unavailable(s.detailError, 'Asset detail');
  else if (!d) body = loading(260);
  else if (!sensors.length) body = html`<div class="empty"><strong>No sensor tags</strong><span>This asset has no tags in the model.</span></div>`;
  else if (s.trendError) body = unavailable(s.trendError, `Trend for ${s.sensor}`);
  else if (!t) body = loading(260);
  else if (!pts.length) body = html`<div class="empty"><strong>No readings yet</strong><span>Start a replay to stream ${s.sensor}.</span></div>`;
  else {
    body = html`
      <div class="big-reading"><span class="display">${num(last.y, 2)}</span><span class="muted" style="font-size: 14px">${t.eng_unit} · ${s.sensor} · hour ${last.x}</span></div>
      ${lineChart(pts, {
        label: t.summary || `${s.sensor} trend`,
        thresholds,
        marker: change ? { x: change.replay_hour, text: `${cap(change.to)}` } : null,
      })}
      ${t.summary ? html`<p class="note">${t.summary}</p>` : ''}`;
  }
  return html`<section class="card">
    <div class="card-head">
      <h2 class="card-title">Sensor trend</h2>
    </div>
    ${sensors.length ? html`<div class="sensor-tabs" role="group" aria-label="Sensor tag">${sensors.map((st) => html`<button type="button" class="sensor-tab" data-sensor="${st.tag}" aria-pressed="${st.tag === s.sensor}">${st.tag}</button>`)}</div>` : ''}
    ${body}
  </section>`;
}

function historyCard(s) {
  const pts = (s.history || []).map((p) => ({ x: p.replay_hour, y: p.health_index }));
  let body;
  if (!s.history) body = s.detail || s.detailError ? unavailable({ status: 501 }, 'Health history') : loading(210);
  else if (!pts.length) body = html`<div class="empty"><strong>No history yet</strong><span>Health is assessed once per replay hour while a scenario runs.</span></div>`;
  else {
    const first = pts[0];
    const last = pts[pts.length - 1];
    const crossed = s.history.find((p, i) => i && p.band !== s.history[i - 1].band);
    body = html`
      ${lineChart(pts, {
        width: 760, height: 220, yMin: 0, yMax: 100, fill: false, color: '#0D1526',
        label: `Health index from ${num(first.y)} to ${num(last.y)} over ${last.x - first.x} replay hours`,
        bands: [
          { from: 80, to: 100, fill: '#E3F5EC', text: 'Healthy ≥ 80', textColor: '#0B7A53' },
          { from: 50, to: 80, fill: '#FFF1DC', text: 'Degraded 50–79', textColor: '#9A5B00' },
          { from: 0, to: 50, fill: '#FDE7E4', text: 'Critical < 50', textColor: '#C4281C' },
        ],
        marker: crossed ? { x: crossed.replay_hour, text: cap(crossed.band) } : null,
      })}
      <p class="ink-2" style="font-size: 14px">${num(first.y)} → ${num(last.y)} over ${plural(last.x - first.x, 'replay hour')}${crossed ? `, crossing into ${cap(crossed.band)} at hour ${crossed.replay_hour}` : ''}. Computed in code by the Health Agent; the assistant can only quote it.</p>`;
  }
  return html`<section class="card">
    <div class="card-head"><h2 class="card-title">Health index</h2></div>
    ${body}
  </section>`;
}

function feedsCard(s) {
  const rows = s.detail?.feeds_rows;
  return html`<section class="card" style="gap: 12px">
    <div class="card-head"><h2 class="card-title">HAZOP rows it feeds</h2><a class="card-link" href="#/hazop">Register</a></div>
    ${!s.detail ? (s.detailError ? unavailable(s.detailError, 'Linked rows') : loading(200))
      : rows?.length ? rows.map((r) => html`<a class="link-card" href="#/matrix/${r.row_code}">
          <div class="link-card-top"><span class="mono muted" style="font-size: 13px">${r.row_code}</span><span style="margin-left: auto">${riskPill(r.score, r.band)}</span></div>
          <span style="font-size: 15px; font-weight: 600">${r.deviation}</span>
          <span class="ink-2" style="font-size: 13px">S${r.severity} · L${r.likelihood_base}${r.likelihood_live !== r.likelihood_base ? html` → <b>L${r.likelihood_live}</b>` : ''}${r.rule ? ` · rule ${r.rule}` : ''}${r.relation ? ` · ${r.relation}` : ''}</span>
          <div style="display: flex; gap: 6px; flex-wrap: wrap">${(r.safeguards || []).map((sg) => html`<span class="sg">${icon('shield', { size: 12 })}${sg}</span>`)}</div>
        </a>`)
      : html`<div class="empty"><strong>No linked rows</strong><span>This asset is not a cause or safeguard in the register.</span></div>`}
    <p class="muted" style="font-size: 13px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap">Links come from the Unit 100 asset model</p>
  </section>`;
}

function unavailable(err, what) {
  return err?.status === 501
    ? html`<div class="empty"><strong>${what} is not available yet</strong><span>The server endpoint is not implemented yet.</span></div>`
    : html`<div class="empty"><strong>Could not load ${what.toLowerCase()}</strong><span>${err?.message || 'Unknown error'}</span></div>`;
}
