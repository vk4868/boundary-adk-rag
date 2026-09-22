'use strict';
const $ = (id) => document.getElementById(id);
const state = { token: '', sessionId: null, sources: [], busy: false, pendingPrompt: null };
const el = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
function notice(text) { $('notice').textContent = text || ''; $('notice').hidden = !text; }
async function api(path, options = {}, token = state.token) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', 'X-App-Token': token, ...(options.headers || {}) } });
  let data; try { data = await response.json(); } catch { throw new Error('The workspace returned an unreadable response. Please try again.'); }
  if (!response.ok) { const error = new Error(response.status === 401 || response.status === 403 ? 'Your access token was not accepted. Reconnect to your workspace.' : 'The workspace could not complete this request. Please try again.'); error.status = response.status; throw error; }
  return data;
}
function renderSources() {
  $('sources').replaceChildren();
  state.sources.forEach((s) => {
    const card = el('div', undefined, 'source-card');
    const top = el('div', undefined, 'source-top'); top.append(el('span', '▤', 'document-icon'), el('h3', s.title));
    card.append(top, el('p', `${s.version} · ${s.page_count} pages`));
    card.append(el('span', s.scope, 'source-tag'));
    $('sources').append(card);
  });
  if (!state.sources.length) $('sources').append(el('p', 'No documents are available for this workspace. Ask the owner to index the collection.', 'muted'));
  $('source-count').textContent = state.sources.length;
  $('composer-scope').textContent = `${state.sources.length} source document${state.sources.length === 1 ? '' : 's'}`;
}
$('connect-button').addEventListener('click', () => { $('connect-dialog').showModal(); $('token').focus(); });
function clearConnectDialog() { $('token').value = ''; $('connect-error').textContent = ''; $('connect-error').hidden = true; }
$('cancel-connect').addEventListener('click', () => { state.pendingPrompt = null; clearConnectDialog(); $('connect-dialog').close(); });
$('connect-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const token = $('token').value.trim(); if (!token) return;
  $('confirm-connect').disabled = true; $('connect-error').hidden = true;
  try {
    const data = await api('/api/sources', {}, token); const sources = BoundaryResponseValidator.validateSourcesResponse(data);
    state.token = token; state.sources = sources; state.sessionId = null;
    renderSources(); $('connection-label').textContent = 'Workspace connected'; $('connection-dot').classList.add('connected'); clearConnectDialog(); $('connect-dialog').close(); notice('');
    if (state.pendingPrompt) { $('question').value = state.pendingPrompt; state.pendingPrompt = null; $('question').focus(); }
  } catch (error) { $('connect-error').textContent = error.message; $('connect-error').hidden = false; }
  finally { $('confirm-connect').disabled = false; }
});
$('connect-dialog').addEventListener('cancel', () => { state.pendingPrompt = null; clearConnectDialog(); });
let evidenceTrigger = null;
function closeEvidence() {
  $('evidence-panel').hidden = true;
  if (evidenceTrigger?.isConnected) evidenceTrigger.focus();
  evidenceTrigger = null;
}
function showEvidence(citation, trigger) {
  evidenceTrigger = trigger;
  $('evidence-title').textContent = citation.title;
  $('evidence-content').replaceChildren(el('div', `Page ${citation.page} · ${citation.id}`, 'evidence-meta'), el('blockquote', citation.text, 'evidence-quote'));
  $('evidence-panel').hidden = false; $('close-evidence').focus();
}
$('close-evidence').addEventListener('click', closeEvidence);
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('evidence-panel').hidden) closeEvidence(); });
const executionTraceStages = new Set(['document_research_pipeline', 'document_researcher', 'evidence_reviewer', 'deterministic_evidence_gate']);
function traceStatusLabel(stage, status) {
  if (executionTraceStages.has(stage) && status === 'passed') return 'Completed';
  if (stage === 'deterministic_gate' && status === 'passed') return 'Passed';
  if (stage === 'deterministic_gate' && status === 'failed') return 'Failed';
  return status;
}
function renderTurn(question, data) {
  const turn = $('turn-template').content.cloneNode(true);
  turn.querySelector('.question-row h2').textContent = question;
  const answered = data.status === 'answered';
  const status = turn.querySelector('.answer-status');
  status.textContent = answered ? 'Evidence reviewed' : (data.status === 'insufficient_evidence' ? 'Insufficient evidence' : 'Request not answered');
  if (!answered) status.classList.add('warning');
  const citations = data.citations;
  const byId = new Map(citations.map((c, i) => [c.id, { citation: c, number: i + 1 }]));
  const claims = data.claims;
  const answerElement = turn.querySelector('.answer-text');
  answerElement.textContent = data.answer;
  if (answered) {
    answerElement.hidden = true;
    claims.forEach((claim) => {
      const p = el('p', claim.text, 'claim');
      claim.evidence_ids.forEach((id) => { const entry = byId.get(id); const button = el('button', String(entry.number), 'cite-button'); button.setAttribute('aria-label', `View source ${entry.number}: ${entry.citation.title}, page ${entry.citation.page}`); button.addEventListener('click', () => showEvidence(entry.citation, button)); p.append(button); });
      turn.querySelector('.claim-list').append(p);
    });
    citations.forEach((c, i) => { const button = el('button', undefined, 'source-chip'); button.append(el('span', `${i + 1}`), document.createTextNode(`${c.title} · p. ${c.page}`)); button.addEventListener('click', () => showEvidence(c, button)); turn.querySelector('.answer-sources').append(button); });
  }
  const detail = turn.querySelector('.run-detail-content');
  data.trace.forEach((t) => { const row = el('div', undefined, 'trace-item'); row.append(el('span', t.stage.replaceAll('_', ' ')), el('span', [traceStatusLabel(t.stage, t.status), t.duration_ms !== undefined && t.duration_ms !== null ? `${(t.duration_ms / 1000).toFixed(1)}s` : ''].filter(Boolean).join(' · '))); detail.append(row); });
  const usage = data.usage; detail.append(el('div', `${usage.model_calls} model calls · ${usage.tool_calls} tool calls · ${usage.input_tokens} input / ${usage.output_tokens} output tokens`, 'usage-line'));
  detail.append(el('div', `Request ${data.request_id}`, 'usage-line'));
  data.warnings.forEach((warning) => detail.append(el('div', warning, 'usage-line')));
  $('conversation').append(turn);
}
function setBusy(busy) { state.busy = busy; $('busy').hidden = !busy; $('send-button').disabled = busy; $('question').disabled = busy; $('new-research').disabled = busy; $('connect-button').disabled = busy; document.querySelectorAll('.suggestion').forEach((b) => { b.disabled = busy; }); }
async function research() {
  if (state.busy) return; const question = $('question').value.trim(); if (!question) { $('question').focus(); return; }
  if (!state.token) { state.pendingPrompt = question; $('connect-dialog').showModal(); $('token').focus(); return; }
  notice(''); setBusy(true); $('welcome').hidden = true; $('conversation').hidden = false; closeEvidence(); $('workspace-body').scrollTop = $('workspace-body').scrollHeight;
  try {
    const data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: question, ...(state.sessionId ? { session_id: state.sessionId } : {}) }) });
    const validated = BoundaryResponseValidator.validateChatResponse(data, state.sources);
    state.sessionId = validated.session_id; renderTurn(question, validated); $('question').value = ''; $('question').placeholder = 'Ask a follow-up or explore another rule…';
  } catch (error) {
    notice(error.message); if (error.status === 401 || error.status === 403) { state.token = ''; state.sessionId = null; $('connection-label').textContent = 'Reconnect workspace'; $('connection-dot').classList.remove('connected'); }
    if (!$('conversation').children.length) { $('welcome').hidden = false; $('conversation').hidden = true; }
  } finally { setBusy(false); $('question').focus(); $('workspace-body').scrollTop = $('workspace-body').scrollHeight; }
}
$('question-form').addEventListener('submit', (event) => { event.preventDefault(); research(); });
$('question').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); research(); } });
document.querySelectorAll('.suggestion').forEach((button) => button.addEventListener('click', () => { $('question').value = button.dataset.prompt; $('question').focus(); }));
$('new-research').addEventListener('click', () => { if (state.busy) return; state.sessionId = null; $('conversation').replaceChildren(); $('conversation').hidden = true; $('welcome').hidden = false; closeEvidence(); $('question').value = ''; $('question').placeholder = 'Ask a question about your documents…'; notice(''); $('question').focus(); });
