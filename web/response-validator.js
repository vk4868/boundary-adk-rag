(function responseValidatorModule(root, factory) {
  const validator = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = validator;
  else root.BoundaryResponseValidator = validator;
})(typeof globalThis === 'undefined' ? this : globalThis, () => {
  const invalid = () => new Error('The workspace returned an invalid response. Please try again.');
  const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = (value) => typeof value === 'string' && value.trim().length > 0;
  const integer = (value, minimum) => Number.isInteger(value) && value >= minimum;
  const sourceId = (value) => typeof value === 'string' && /^[a-z0-9][a-z0-9_-]{1,63}$/.test(value);
  const traceStatus = new Set(['passed', 'failed', 'skipped']);

  function publicSourceMap(sources) {
    const result = new Map();
    if (!Array.isArray(sources)) throw invalid();
    sources.forEach((source) => {
      if (!isRecord(source) || !sourceId(source.source_id) || result.has(source.source_id) || !text(source.title) || !text(source.version) || !text(source.scope) || !integer(source.page_count, 1)) throw invalid();
      result.set(source.source_id, source);
    });
    return result;
  }

  function validateSourcesResponse(data) {
    if (!isRecord(data) || !Array.isArray(data.sources)) throw invalid();
    publicSourceMap(data.sources);
    return data.sources;
  }

  function validateChatResponse(data, knownSources) {
    if (!isRecord(data) || !text(data.request_id) || !text(data.session_id) || !['answered', 'insufficient_evidence', 'rejected'].includes(data.status) || !text(data.answer) || !Array.isArray(data.claims) || !Array.isArray(data.citations) || !Array.isArray(data.sources) || !Array.isArray(data.trace) || !isRecord(data.usage) || !isRecord(data.governance) || !Array.isArray(data.warnings)) throw invalid();
    const knownSourceMap = publicSourceMap(knownSources);
    const responseSourceMap = publicSourceMap(data.sources);
    responseSourceMap.forEach((source, id) => {
      const known = knownSourceMap.get(id);
      if (!known || known.title !== source.title || known.version !== source.version || known.scope !== source.scope || known.page_count !== source.page_count) throw invalid();
    });
    const governance = data.governance;
    if (![governance.review_passed, governance.citation_gate_passed, governance.scope_gate_passed].every((value) => typeof value === 'boolean')) throw invalid();
    data.trace.forEach((trace) => {
      if (!isRecord(trace) || !text(trace.stage) || !traceStatus.has(trace.status) || (trace.duration_ms !== undefined && trace.duration_ms !== null && !integer(trace.duration_ms, 0))) throw invalid();
    });
    ['input_tokens', 'output_tokens', 'model_calls', 'tool_calls'].forEach((field) => {
      if (!integer(data.usage[field], 0)) throw invalid();
    });
    if (!data.warnings.every((warning) => typeof warning === 'string')) throw invalid();

    if (data.status !== 'answered') {
      if (data.claims.length || data.citations.length || data.sources.length) throw invalid();
      return data;
    }
    if (governance.review_passed !== true || governance.citation_gate_passed !== true || governance.scope_gate_passed !== true) throw invalid();
    if (!data.trace.some((trace) => trace.stage === 'deterministic_gate' && trace.status === 'passed')) throw invalid();

    const citationsById = new Set();
    const citedSourceIds = new Set();
    if (!data.citations.length || !data.claims.length) throw invalid();
    data.citations.forEach((citation) => {
      if (!isRecord(citation)) throw invalid();
      const source = knownSourceMap.get(citation.source_id);
      const canonicalId = source && integer(citation.page, 1) ? `${citation.source_id}:p${String(citation.page).padStart(4, '0')}` : '';
      if (!text(citation.id) || citationsById.has(citation.id) || !source || citation.title !== source.title || citation.page > source.page_count || citation.id !== canonicalId || !text(citation.text)) throw invalid();
      citationsById.add(citation.id);
      citedSourceIds.add(citation.source_id);
    });
    data.claims.forEach((claim) => {
      if (!isRecord(claim) || !text(claim.text) || !Array.isArray(claim.evidence_ids) || !claim.evidence_ids.length) throw invalid();
      const evidenceIds = new Set();
      claim.evidence_ids.forEach((evidenceId) => {
        if (!text(evidenceId) || evidenceIds.has(evidenceId) || !citationsById.has(evidenceId)) throw invalid();
        evidenceIds.add(evidenceId);
      });
    });
    if (data.sources.map((source) => source.source_id).join('\u0000') !== [...citedSourceIds].sort().join('\u0000')) throw invalid();
    return data;
  }

  return { validateSourcesResponse, validateChatResponse };
});
