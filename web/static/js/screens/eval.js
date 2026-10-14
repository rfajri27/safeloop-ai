// Evaluation: PoC gate and objectives PO-1 to PO-5 from the latest frozen run.

import { api } from '../api.js';
import { html, render, icon, duration, loading, errorState, on, toast, toastError, num } from '../ui.js';

export const title = 'Evaluation';
export const subtitle = 'PoC objectives PO-1 to PO-5 from the frozen evaluation run';

const EVAL_ROLES = ['admin', 'process_safety_engineer'];

// What each objective measures, from the PoC plan. Values come from the run.
const OBJECTIVES = {
  'PO-1': { name: 'Dynamic risk', target: '≤ 60 s in S1 and S2', label: 'slowest re-score', unit: 's', source: 'Audit-log timestamps' },
  'PO-2': { name: 'Grounded HAZOP drafting', target: '≥ 60%, 0 uncited safeguards', label: 'recall', unit: '%', source: 'Golden HAZOP set · 20 rows' },
  'PO-3': { name: 'Trustworthy answers', target: '100%, ≥ 9 of 10 out-of-corpus flagged', label: 'cited or flagged', unit: '%', source: '25 golden + 10 out-of-corpus questions' },
  'PO-4': { name: 'Safety by design', target: '100%, no model call', label: 'prompts refused', unit: '', source: 'Guardrail suite · 15 prompts' },
  'PO-5': { name: 'Human governance', target: '100% of drafts via queue', label: 'complete records', unit: '%', source: 'Audit-log completeness check' },
};
const NFR = {
  llm_off_core_loop: { label: 'Core loop runs with the LLM switched off', note: 'health · risk · matrix · guardrail' },
  reproducible_scores: { label: 'Same scenario from reset, same scores', note: 'identical runs' },
  assistant_p95_s: { label: 'Assistant answer time, 95th percentile', note: 'target ≤ 15 s', unit: 's' },
  control_write_paths: { label: 'Write path to a control system', note: 'target 0' },
};

export async function mount(el, _param, shell) {
  const state = { run: null, error: null, starting: false };
  const draw = () => render(el, view(state, shell));

  async function load() {
    try {
      const res = await api.get('/eval-runs/latest?frozen=true');
      state.run = res.data;
    } catch (err) {
      state.error = err;
    }
    draw();
  }

  on(el, 'click', '[data-act="run"]', async () => {
    state.starting = true;
    draw();
    try {
      const res = await api.raw('POST', '/eval-runs', { body: { freeze: true, sets: ['hazop_rows', 'qa', 'out_of_corpus', 'guardrail'] } });
      toast(`Evaluation ${res.data?.run_id ?? ''} started. It runs in the background; results appear here when it finishes.`);
    } catch (err) {
      toastError(err, 'Starting an evaluation');
    } finally {
      state.starting = false;
      draw();
    }
  });

  render(el, loading(520));
  await load();
}

function view(s, shell) {
  if (s.error) return errorState(s.error, 'the evaluation');
  const r = s.run || {};
  const gate = r.gate || { name: 'G1', passed: null, total: 5 };
  const hasRun = Boolean(r.run_id);
  const objectives = Object.keys(OBJECTIVES).map((code) => ({ code, ...OBJECTIVES[code], ...(r.objectives || []).find((o) => o.code === code) }));
  const allowed = shell.can(EVAL_ROLES);
  const passedAll = hasRun && gate.passed === gate.total;
  const arc = hasRun && gate.total ? (gate.passed / gate.total) * 163.4 : 0;
  const meta = hasRun
    ? [`run ${r.run_id}`, r.frozen ? 'frozen' : 'not frozen', r.finished_at && new Date(r.finished_at).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }), r.golden_sets_version && `golden sets ${r.golden_sets_version}`, r.duration_s != null && duration(r.duration_s)].filter(Boolean).join(' · ')
    : null;

  return html`
    <section class="card gate">
      <div style="position: relative; width: 64px; height: 64px; flex-shrink: 0">
        <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="${hasRun ? `${gate.passed} of ${gate.total} objectives pass` : 'No run yet'}">
          <circle cx="32" cy="32" r="26" fill="none" stroke="#F6F8FB" stroke-width="7"></circle>
          ${arc > 0 ? html`<circle cx="32" cy="32" r="26" fill="none" stroke="${passedAll ? '#0B7A53' : '#3448F0'}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${arc.toFixed(1)} 163.4" transform="rotate(-90 32 32)"></circle>` : ''}
        </svg>
        <span class="display" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 17px; font-weight: 600">${hasRun ? `${gate.passed}/${gate.total}` : `–/${gate.total}`}</span>
      </div>
      <div style="display: flex; flex-direction: column; gap: 4px; flex: 1 1 300px; min-width: 0">
        <span class="display" style="font-size: 20px; font-weight: 600">PoC gate ${gate.name}: ${!hasRun ? 'not evaluated yet' : passedAll ? 'all objectives pass' : `${gate.passed} of ${gate.total} objectives pass`}</span>
        ${meta ? html`<span class="mono ink-2" style="font-size: 13px">${meta}</span>` : html`<span class="ink-2" style="font-size: 14px">No evaluation has been run yet. Values stay empty until <span class="mono">make eval</span> writes a real run.</span>`}
      </div>
      <button type="button" class="btn" data-act="run"${!allowed || s.starting ? html` disabled` : ''}${allowed ? '' : html` title="Only an admin or process safety engineer can start an evaluation"`}>${icon('bolt', { size: 18 })}${s.starting ? 'Starting…' : 'Run make eval'}</button>
    </section>
    <div class="po-grid-3">${objectives.slice(0, 3).map(poCard)}</div>
    <div class="po-grid-2">${objectives.slice(3).map(poCard)}</div>
    <div class="row collapse-lg">
      <section class="card" style="flex: 1 1 0; gap: 14px">
        <div class="card-head"><h2 class="card-title">Non-functional checks</h2></div>
        ${Object.entries(NFR).map(([key, meta]) => nfrRow(key, meta, (r.non_functional || []).find((c) => c.check === key)))}
      </section>
      ${(r.stretch?.length ? r.stretch : [{ code: 'RCA', state: 'not_started' }]).map((st) => html`<section class="card stretch" style="gap: 10px">
        <div class="eyebrow">Stretch</div>
        <span class="display" style="font-size: 18px; font-weight: 600">RCA agent · top-3 causes</span>
        <span class="ink-2" style="font-size: 14px; line-height: 1.5">Target ≥ 80% on 5 golden cases and a cited report in under 5 minutes. Starts only if the 15 October gate passes.</span>
        <span><span class="pill neutral" style="background: var(--surface)">${st.state === 'not_started' ? 'Not started' : st.state}</span></span>
      </section>`)}
    </div>`;
}

function poValue(o) {
  if (o.value == null) return '—';
  if (o.code === 'PO-4' && typeof o.value === 'string') return o.value;
  return `${num(o.value, 1)}${o.unit === '%' ? '%' : o.unit ? ` ${o.unit}` : ''}`;
}

function poCard(o) {
  const status = o.passed == null ? html`<span class="pill sm neutral">Not run</span>` : o.passed ? html`<span class="pill sm ok">Pass</span>` : html`<span class="pill sm crit">Fail</span>`;
  return html`<div class="card" style="gap: 12px">
    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
      <span class="code accent">${o.code}</span>
      <span style="font-size: 15px; font-weight: 600">${o.name}</span>
      <span style="margin-left: auto">${status}</span>
    </div>
    <div class="po-value"><span class="display">${poValue(o)}</span><span class="ink-2" style="font-size: 15px">${o.label}</span></div>
    <span class="ink-2" style="font-size: 14px">Target: ${o.target}</span>
    ${o.detail ? html`<span style="font-size: 14px">${o.detail}</span>` : ''}
    <span class="muted" style="font-size: 13px">${o.source}</span>
  </div>`;
}

function nfrRow(key, meta, c) {
  const value = c?.value != null ? `${c.value}${meta.unit && typeof c.value === 'number' ? ` ${meta.unit}` : ''}` : null;
  const known = c && (c.passed != null || value != null);
  const passed = c?.passed ?? (known ? true : null);
  return html`<div class="check${passed === false ? ' fail' : ''}" style="font-size: 14px">
    <span class="mark" style="${known ? '' : 'background: var(--surface-2); color: var(--muted)'}">${icon(passed === false ? 'x' : known ? 'check' : 'question', { size: 12, width: 2.4 })}</span>
    <span>${meta.label}</span>
    <span class="mono ink-2" style="margin-left: auto; font-size: 13px; text-align: right">${value ?? (known ? 'pass' : meta.note)}</span>
  </div>`;
}
