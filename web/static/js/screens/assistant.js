// Knowledge assistant: cited answers streamed over AG-UI SSE, with a source viewer.

import { api, postStream } from '../api.js';
import {
  html, raw, escape, render, markdown, mdInline, icon, titleCase, loading, on, toastError, ROLE_LABEL, duration,
} from '../ui.js';

export const title = 'Knowledge assistant';
export const subtitle = 'Unit 100 documents · every answer cited or flagged';

const CHAT_ROLES_DENY = ['auditor'];
const SUGGESTIONS = [
  'What is the procedure to switch P-101 to the standby pump?',
  'What does the PAH-201 alarm mean?',
  'Which HAZOP rows does P-101 feed?',
];
const STEP_LABEL = {
  guard_input: 'Checking the guardrail',
  retrieve: 'Searching documents',
  draft_answer: 'Drafting the answer',
  verify_citations: 'Verifying citations',
};

// The thread survives navigation between screens for this page load.
const chat = { sessionId: null, sessionOwner: null, messages: [], docs: null, activeMsg: null, activeCite: null, source: null };

export async function mount(el, docParam, shell) {
  const me = shell.user;
  if (chat.sessionOwner && chat.sessionOwner !== me?.id) Object.assign(chat, { sessionId: null, messages: [], activeMsg: null, activeCite: null, source: null });
  chat.sessionOwner = me?.id;
  const canAsk = !CHAT_ROLES_DENY.includes(me?.role);
  let busy = false;
  let controller = null;

  const draw = () => {
    const input = el.querySelector('#ask');
    const draft = input?.value ?? '';
    const hadFocus = document.activeElement === input;
    render(el, view(canAsk, busy, shell));
    const next = el.querySelector('#ask');
    if (next) { next.value = draft; if (hadFocus) next.focus(); }
    const thread = el.querySelector('.thread');
    if (thread) thread.scrollTop = thread.scrollHeight;
  };

  if (!chat.docs) {
    api.get('/documents').then((res) => { chat.docs = res.data || []; draw(); }).catch(() => { chat.docs = []; draw(); });
  }
  if (docParam) openDoc(docParam);

  async function openDoc(code) {
    chat.activeMsg = null;
    chat.activeCite = null;
    chat.source = { doc_code: code, loading: true };
    draw();
    chat.source = await loadSource({ doc_code: code });
    draw();
  }

  async function ensureSession() {
    if (chat.sessionId) return chat.sessionId;
    const res = await api.post('/chat-sessions');
    chat.sessionId = res.data.session_id;
    return chat.sessionId;
  }

  async function ask(content) {
    content = content.trim();
    if (!content || busy) return;
    if (content.length > 2000) { toastError({ message: 'Questions are limited to 2,000 characters.' }); return; }
    busy = true;
    chat.messages.push({ role: 'user', content, name: me?.display_name, roleLabel: ROLE_LABEL[me?.role] });
    const msg = { role: 'assistant', text: '', citations: [], steps: null, kind: null, progress: [], pending: true, started: performance.now() };
    chat.messages.push(msg);
    const input = el.querySelector('#ask');
    if (input) input.value = '';
    draw();

    controller = new AbortController();
    try {
      const sid = await ensureSession();
      await postStream(`/chat-sessions/${encodeURIComponent(sid)}/messages/stream`, { content }, (ev) => {
        handleEvent(msg, ev);
        draw();
      }, { signal: controller.signal });
    } catch (err) {
      if (err.name !== 'AbortError') {
        msg.error = err.message;
        toastError(err, 'The assistant');
      }
    } finally {
      msg.pending = false;
      msg.elapsed = (performance.now() - msg.started) / 1000;
      busy = false;
      controller = null;
      if (msg.citations.length) {
        chat.activeMsg = chat.messages.indexOf(msg);
        selectCite(msg.citations[0].index);
      }
      draw();
    }
  }

  async function selectCite(index) {
    const msg = chat.messages[chat.activeMsg];
    const cite = msg?.citations.find((c) => c.index === Number(index));
    if (!cite) return;
    chat.activeCite = cite.index;
    chat.source = { ...cite, loading: true };
    draw();
    chat.source = await loadSource(cite);
    draw();
  }

  on(el, 'submit', 'form.composer', (e) => {
    e.preventDefault();
    ask(el.querySelector('#ask').value);
  });
  on(el, 'click', '[data-suggest]', (e, btn) => ask(btn.dataset.suggest));
  on(el, 'click', '[data-cite]', (e, btn) => {
    const msgIdx = Number(btn.closest('[data-msg]')?.dataset.msg ?? chat.activeMsg);
    chat.activeMsg = msgIdx;
    selectCite(btn.dataset.cite);
  });
  on(el, 'click', '[data-doc]', (e, btn) => openDoc(btn.dataset.doc));
  on(el, 'click', '[data-act="library"]', () => { chat.source = null; chat.activeCite = null; draw(); });

  draw();
  return () => controller?.abort();
}

function handleEvent(msg, ev) {
  switch (ev.type) {
    case 'STEP_STARTED':
      msg.progress.push(STEP_LABEL[ev.stepName] || titleCase(ev.stepName));
      break;
    case 'TEXT_MESSAGE_CONTENT':
      msg.text += ev.delta || '';
      break;
    case 'CUSTOM':
      if (ev.name === 'citations') msg.citations = ev.value || [];
      if (ev.name === 'answer_kind') { msg.kind = ev.value?.kind; msg.confidence = ev.value?.confidence; }
      if (ev.name === 'guardrail_refusal') msg.guardrail = ev.value;
      break;
    case 'RUN_FINISHED': {
      const r = ev.result || {};
      // The final answer comes from RUN_FINISHED; streamed text is provisional.
      if (r.content) msg.text = r.content;
      if (r.steps) msg.steps = r.steps;
      if (r.citations) msg.citations = r.citations;
      if (r.kind) msg.kind = r.kind;
      if (r.guardrail) msg.guardrail = { ...msg.guardrail, ...r.guardrail };
      Object.assign(msg, {
        advisory_note: r.advisory_note, latency_ms: r.latency_ms, audit_id: r.audit_id ?? msg.guardrail?.audit_id,
        model_id: r.model_id, prompt_version: r.prompt_version,
      });
      break;
    }
    case 'RUN_ERROR':
      msg.error = ev.message || 'The answer could not be completed.';
      break;
    default:
  }
}

async function loadSource(cite) {
  const out = { ...cite, loading: false };
  const doc = chat.docs?.find((d) => d.doc_code === cite.doc_code);
  try {
    const res = await api.get(`/documents/${encodeURIComponent(cite.doc_code)}`);
    out.doc = res.data;
  } catch {
    out.doc = doc || null;
  }
  if (cite.chunk_id) {
    try {
      out.chunk = (await api.get(`/document-chunks/${encodeURIComponent(cite.chunk_id)}`)).data;
    } catch (err) {
      out.chunkError = err;
    }
  }
  return out;
}

// ---------- View ----------

function view(canAsk, busy, shell) {
  return html`<div class="row collapse-lg">
    <section class="card chat">
      <div style="display: flex; flex-direction: column; gap: 4px">
        <h2 class="card-title">Ask about Unit 100</h2>
        <span class="muted" style="font-size: 13px">Answers come only from the indexed documents, with citations. If the evidence is missing, it says so.</span>
      </div>
      <div class="thread" aria-live="polite">
        ${chat.messages.length ? chat.messages.map((m, i) => (m.role === 'user' ? userMsg(m) : botMsg(m, i))) : html`<div class="empty">
          <strong>No questions yet</strong>
          <span>Ask about a procedure, an alarm or an asset. SafeLoop can’t move valves or change setpoints, and will say so.</span>
        </div>`}
      </div>
      ${canAsk ? html`<div style="display: flex; flex-direction: column; gap: 12px">
        <div style="display: flex; gap: 8px; flex-wrap: wrap">${SUGGESTIONS.map((q) => html`<button type="button" class="suggest" data-suggest="${q}"${busy ? html` disabled` : ''}>${q}</button>`)}</div>
        <form class="composer">
          <input id="ask" type="text" aria-label="Ask a question" placeholder="Ask about a procedure, alarm or asset" maxlength="2000" autocomplete="off">
          <button type="submit" class="send-btn" aria-label="Send"${busy ? html` disabled` : ''}>${icon('send', { size: 20, stroke: '#FFFFFF' })}</button>
        </form>
      </div>` : html`<div class="panel"><span style="font-size: 14px; font-weight: 600">Read-only for ${ROLE_LABEL[shell.user?.role] || 'this role'}</span><span class="ink-2" style="font-size: 13px">Auditors can read every answer in the audit log but cannot ask the assistant.</span></div>`}
    </section>
    ${sourcePanel()}
  </div>`;
}

function userMsg(m) {
  return html`<div class="msg-user">
    <div class="bubble-user">${m.content}</div>
    <span class="muted" style="font-size: 12px">${m.name}${m.roleLabel ? ` · ${m.roleLabel}` : ''}</span>
  </div>`;
}

const citeButton = (n) => `<button type="button" class="cite-ref" data-cite="${n}" aria-label="Source ${n}">${n}</button>`;
const CITE = (html) => html.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, group) => group.split(',').map((n) => citeButton(n.trim())).join(''));

/** Answer text as markdown, with [n] markers turned into source buttons. */
function citedText(text) {
  return raw(CITE(String(markdown(text))));
}

function botMsg(m, i) {
  const refused = m.kind === 'refused';
  const insufficient = m.kind === 'insufficient';
  const who = refused ? 'Guardrail' : 'Knowledge agent';
  const timing = refused ? `${m.guardrail?.model_calls ?? 0} model calls` : m.latency_ms ? duration(m.latency_ms / 1000) : m.elapsed ? duration(m.elapsed) : '';
  const head = html`<div class="bot-head">
    <span class="bot-avatar">${icon(refused ? 'lock' : 'sparkle', { size: 14, stroke: '#FFFFFF' })}</span>
    <span style="font-size: 13px; font-weight: 600">${who}</span>
    ${!m.pending && timing ? html`<span class="mono muted" style="font-size: 12px">${timing}</span>` : ''}
  </div>`;

  if (m.error && !m.text) {
    return html`<div class="msg-bot" data-msg="${i}">${head}<div class="bubble-bot insufficient">
      <span class="badge-icon" style="background: var(--crit-soft)">${icon('warn', { size: 18, stroke: '#A3211A' })}</span>
      <div style="display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 600">No answer</span><span class="ink-2" style="font-size: 14px">${m.error}</span></div>
    </div></div>`;
  }
  if (refused) {
    const [first, ...rest] = m.text.split(/(?<=\.)\s+/);
    return html`<div class="msg-bot" data-msg="${i}">${head}<div class="bubble-bot refused">
      <span class="badge-icon" style="background: var(--ink)">${icon('lock', { size: 18, stroke: '#FFFFFF' })}</span>
      <div style="display: flex; flex-direction: column; gap: 4px">
        <span style="font-weight: 600">${first}</span>
        ${rest.length ? html`<span class="ink-2" style="font-size: 14px">${rest.join(' ')}</span>` : ''}
        <span class="mono muted" style="font-size: 12px">${m.guardrail?.rule_id ? `Rule ${m.guardrail.rule_id} · ` : ''}refused before any model call${m.audit_id ? ` · logged ${m.audit_id}` : ''}</span>
      </div>
    </div></div>`;
  }
  if (insufficient) {
    return html`<div class="msg-bot" data-msg="${i}">${head}<div class="bubble-bot insufficient">
      <span class="badge-icon" style="background: var(--risk-medium-bg)">${icon('question', { size: 18, stroke: '#7A5A00' })}</span>
      <div style="display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 600">Insufficient evidence</span><span class="ink-2" style="font-size: 14px">${m.text}</span></div>
    </div></div>`;
  }
  return html`<div class="msg-bot" data-msg="${i}">${head}<div class="bubble-bot">
    ${m.pending && !m.text ? html`<div class="progress-steps">${m.progress.length ? m.progress[m.progress.length - 1] : 'Starting'}…</div>` : ''}
    ${m.steps?.length
      ? html`<div class="answer-text">${citedText(m.text.split('\n')[0])}</div><ol>${m.steps.map((s) => html`<li>${raw(mdInline(s.text))} ${(s.citations || []).map((n) => html`<button type="button" class="cite-ref" data-cite="${n}" aria-label="Source ${n}">${n}</button>`)}</li>`)}</ol>`
      : m.text ? html`<div class="answer-text">${citedText(m.text)}</div>` : ''}
    ${m.pending && m.text ? html`<div class="progress-steps">${m.progress[m.progress.length - 1] || ''}…</div>` : ''}
    ${!m.pending && (m.citations.length || m.advisory_note) ? html`<div class="muted" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px">
      ${m.citations.length ? html`<span class="pill sm accent">${m.citations.length} source${m.citations.length === 1 ? '' : 's'}</span>` : ''}
      ${m.advisory_note || 'Advisory. Follow the approved SOP at the panel.'}
    </div>` : ''}
  </div></div>`;
}

function sourcePanel() {
  const msg = chat.messages[chat.activeMsg];
  const src = chat.source;
  const tabs = msg?.citations?.length ? html`<div class="source-tabs" role="group" aria-label="Sources">${msg.citations.map((c) => html`<button type="button" data-cite="${c.index}" aria-pressed="${c.index === chat.activeCite}"><span style="color: var(--accent); font-weight: 600">${c.index}</span>${c.doc_code}</button>`)}</div>` : '';

  if (!src) {
    return html`<aside aria-label="Document library" class="card drawer" style="width: 400px">
      <div class="card-head"><h2 class="card-title">Indexed documents</h2></div>
      ${tabs}
      ${chat.docs == null ? loading(300) : chat.docs.length ? html`<div class="doc-list">${chat.docs.map((d) => html`<button type="button" class="cite" data-doc="${d.doc_code}" style="border: none; text-align: left; cursor: pointer; font: inherit">
        <span class="badge-icon" style="width: 28px; height: 28px; border-radius: 9px; background: var(--accent-soft)">${icon('doc', { size: 14, stroke: '#3448F0' })}</span>
        <span class="cite-body"><span class="mono" style="font-size: 13px">${d.doc_code}</span><span class="muted" style="font-size: 12px">${d.title}</span></span>
      </button>`)}</div>` : html`<div class="empty"><strong>No documents indexed</strong><span>Run the ingest job to load the corpus.</span></div>`}
    </aside>`;
  }

  const d = src.doc;
  return html`<aside id="src" aria-label="Source viewer" class="card drawer" style="width: 400px">
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
      ${tabs || html`<span class="eyebrow">Source</span>`}
      <button type="button" class="card-link" data-act="library" style="border: none; background: none; cursor: pointer; padding: 0; color: var(--accent)">All documents</button>
    </div>
    ${src.loading ? loading(320) : html`
      <div style="display: flex; flex-direction: column; gap: 6px">
        <div style="display: flex; justify-content: space-between; gap: 8px; align-items: center">
          <span class="muted" style="font-size: 13px">${titleCase(d?.type || 'Document')}</span>
        </div>
        <h2 class="display" style="font-size: 20px; font-weight: 600">${d?.title || src.title || src.doc_code}</h2>
      </div>
      <div class="panel" style="gap: 8px">
        <div class="kv"><span>ID</span><span>${src.doc_code}</span></div>
        ${d?.type ? html`<div class="kv"><span>Type</span><span>${d.type}</span></div>` : ''}
        ${d?.asset_tags?.length ? html`<div class="kv"><span>Asset</span><span>${d.asset_tags.slice(0, 4).join(', ')}${d.asset_tags.length > 4 ? '…' : ''}</span></div>` : ''}
        ${d?.revision ?? src.revision ? html`<div class="kv"><span>Revision</span><span>${d?.revision ?? src.revision}</span></div>` : ''}
        ${d?.effective_date ? html`<div class="kv"><span>Effective</span><span>${d.effective_date}</span></div>` : ''}
        ${src.section ? html`<div class="kv"><span>Section</span><span>${src.section}</span></div>` : ''}
      </div>
      ${src.chunk ? html`<div class="passage"><span style="font-size: 12px; font-weight: 600; color: var(--accent)">Cited passage${src.chunk.section ? ` · ${src.chunk.section}` : ''}${src.chunk.page ? ` · page ${src.chunk.page}` : ''}</span>${markdown(src.chunk.text)}</div>`
        : html`<div class="empty"><strong>Passage not available</strong><span>${src.chunk_id ? 'The document-chunk endpoint is not implemented yet.' : 'This citation has no chunk to show. Open the document to read it.'}</span></div>`}
    `}
  </aside>`;
}
