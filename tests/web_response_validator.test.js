'use strict';
const assert = require('node:assert/strict');
const { validateSourcesResponse, validateChatResponse } = require('../web/response-validator.js');

const sources = [{ source_id: 'mcc-2025', title: 'MCC Laws', version: '2025', scope: 'Cricket Laws', page_count: 42 }];
const validResponse = {
  request_id: 'request-1', session_id: 'session-1', status: 'answered', answer: 'A supported answer.',
  governance: { review_passed: true, citation_gate_passed: true, scope_gate_passed: true },
  claims: [{ text: 'The rule applies.', evidence_ids: ['mcc-2025:p0007'] }],
  citations: [{ id: 'mcc-2025:p0007', source_id: 'mcc-2025', title: 'MCC Laws', page: 7, text: 'Source passage.' }],
  sources,
  trace: [{ stage: 'deterministic_gate', status: 'passed', duration_ms: 2 }],
  usage: { input_tokens: 1, output_tokens: 2, model_calls: 1, tool_calls: 1 }, warnings: [],
};

assert.deepEqual(validateSourcesResponse({ sources }), sources);
assert.equal(validateChatResponse(validResponse, sources), validResponse);
for (const mutation of [
  (response) => { response.status = 'completed'; },
  (response) => { response.governance.citation_gate_passed = false; },
  (response) => { response.claims[0].evidence_ids = ['missing']; },
  (response) => { response.citations[0].source_id = 'not-connected'; },
  (response) => { response.trace[0].status = 'failed'; },
  (response) => { response.citations[0].page = 43; response.citations[0].id = 'mcc-2025:p0043'; },
  (response) => { response.citations[0].id = 'mcc-2025:p0008'; },
  (response) => { response.citations = [null]; },
]) {
  const candidate = structuredClone(validResponse); mutation(candidate);
  assert.throws(() => validateChatResponse(candidate, sources), /invalid response/);
}
assert.throws(() => validateSourcesResponse({ sources: [{ ...sources[0], page_count: 0 }] }), /invalid response/);
const insufficientEvidence = structuredClone(validResponse);
insufficientEvidence.status = 'insufficient_evidence';
insufficientEvidence.answer = 'The supplied sources do not support a verified answer.';
insufficientEvidence.claims = [];
insufficientEvidence.citations = [];
insufficientEvidence.sources = [];
insufficientEvidence.governance = { review_passed: false, citation_gate_passed: false, scope_gate_passed: true };
insufficientEvidence.trace = [{ stage: 'research', status: 'passed', duration_ms: null }];
assert.equal(validateChatResponse(insufficientEvidence, sources), insufficientEvidence);
const answeredWithWrongSources = structuredClone(validResponse);
answeredWithWrongSources.sources = [];
assert.throws(() => validateChatResponse(answeredWithWrongSources, sources), /invalid response/);
const rejectedWithCitation = structuredClone(insufficientEvidence);
rejectedWithCitation.status = 'rejected';
rejectedWithCitation.claims = [{ text: 'Unsupported.', evidence_ids: ['mcc-2025:p0007'] }];
assert.throws(() => validateChatResponse(rejectedWithCitation, sources), /invalid response/);
console.log('web_response_validator.test.js: passed');
