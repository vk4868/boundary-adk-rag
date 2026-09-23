"""Independent offline governance review: no credentials, PDFs, or model requests."""
from dataclasses import fields
from pathlib import Path
import json
import pytest
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models import LlmResponse
from google.genai import types
from app.agents import build_agent
from app.config import Settings
from app.gate import apply_gate
from app.index import IndexRepository
from app.models import ClaimDraft,CorpusIndex,EmbeddingDescriptor,PageRecord,QuestionPartAssessment,ResearchDraft,ReviewDecision,SourceRecord
from app.tools import BudgetExceeded,RunLedger,build_tools

@pytest.fixture
def context(tmp_path):
    source=SourceRecord(source_id='local_rules',title='Local tournament supplied rules',version='Supplied copy',scope='Local tournament',competition='Local Tournament',allowed_roles=['analyst'],page_count=1,sha256='a'*64)
    page=PageRecord(evidence_id='local_rules:p0001',source_id='local_rules',page=1,text='Local Tournament bowlers may bowl four overs. '+'padding '*220+'The supporting ending must remain visible.')
    index=CorpusIndex(schema_version=1,embedding=EmbeddingDescriptor(provider='lexical'),sources=[source],pages=[page])
    path=tmp_path/'index.json';path.write_text(index.model_dump_json())
    settings=Settings(_env_file=None,app_enable_model_calls=False,app_model_provider='disabled',app_embedding_provider='lexical',app_index_path=path,app_audit_path=tmp_path/'audit.jsonl')
    repository=IndexRepository(settings);ledger=RunLedger('a'*32)
    return settings,repository,ledger

def draft():return ResearchDraft(status='answered',claims=[ClaimDraft(text='In the Local Tournament, bowlers may bowl four overs.',evidence_ids=['local_rules:p0001'])])
def review():return ReviewDecision(verdict='pass',answer_status='answered',checked_claims=1,citation_support_ok=True,scope_and_version_ok=True,parts=[QuestionPartAssessment(part_id='answer',description='requested answer',supported=True,claim_indices=[0])],all_parts_supported=True,conditions_preserved=True,unsupported_absence_claim_indices=[],abstention_justified=False)
def gate(context,d=None,r=None,role='analyst'):
    _,repo,ledger=context
    return apply_gate(request_id=ledger.request_id,session_id='b'*32,role=role,draft=d or draft(),review=r or review(),ledger=ledger,repository=repo,trace=[])
def issue(context):
    _,_,ledger=context;ledger.issued_evidence_ids.add('local_rules:p0001')
    if hasattr(ledger,'read_evidence_ids'):ledger.read_evidence_ids.add('local_rules:p0001')

def test_agent_is_real_adk_sequence(context):
    settings,repo,ledger=context;agent=build_agent(settings,repo,ledger,'analyst')
    assert isinstance(agent,SequentialAgent)
    assert len(agent.sub_agents)>=3
    assert isinstance(agent.sub_agents[0],LlmAgent) and isinstance(agent.sub_agents[1],LlmAgent)
    assert agent.sub_agents[0].model.model==agent.sub_agents[1].model.model==settings.app_model
    assert agent.sub_agents[0].model.retry_options.attempts==1
    assert {t.name for t in agent.sub_agents[0].tools}=={'list_sources','search_documents','read_evidence'}
    assert not agent.sub_agents[1].tools

def test_stale_evidence_fails(context):
    result=gate(context);assert not result.passed and not result.response.claims

def test_acl_rechecked_after_issuance(context):
    issue(context);result=gate(context,role='admin');assert not result.passed and not result.response.citations

def test_review_rejection_does_not_leak_draft(context):
    issue(context);r=ReviewDecision(verdict='fail',answer_status='answered',checked_claims=1,citation_support_ok=False,scope_and_version_ok=True,parts=[QuestionPartAssessment(part_id='answer',description='requested answer',supported=False,claim_indices=[])],all_parts_supported=False,conditions_preserved=False,unsupported_absence_claim_indices=[],abstention_justified=False,issues=['Unsupported'])
    result=gate(context,r=r);assert not result.passed and not result.response.claims
    assert 'four overs' not in result.response.answer

def test_review_claim_count_must_match(context):
    issue(context);r=review();r.checked_claims=0;assert not gate(context,r=r).passed

def test_local_rule_cannot_silently_be_universal(context):
    issue(context);d=draft();d.claims[0].text='In all cricket, bowlers may bowl four overs.';assert not gate(context,d=d).passed

def test_success_citation_exposes_actual_supporting_end(context):
    issue(context);result=gate(context);assert result.passed
    assert 'supporting ending must remain visible' in result.response.citations[0].text

def test_budget_rejects_next_tool_before_dispatch(context):
    settings,_,ledger=context;ledger.tool_calls=settings.app_max_tool_calls
    with pytest.raises(BudgetExceeded):ledger.begin_tool(settings)

def test_role_rejected_before_tool_construction(context):
    settings,repo,ledger=context
    with pytest.raises(PermissionError):build_tools(repo,settings,ledger,'admin')

def test_ledger_reset_clears_previous_evidence(context):
    issue(context);ledger=context[2];ledger.model_calls=4;ledger.reset('c'*32)
    assert not ledger.issued_evidence_ids and ledger.model_calls==0
    if hasattr(ledger,'read_evidence_ids'):assert not ledger.read_evidence_ids

def test_model_usage_counts_candidates_and_thinking(context):
    settings,repo,ledger=context;agent=build_agent(settings,repo,ledger,'analyst')
    response=LlmResponse(usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=20,candidates_token_count=7,thoughts_token_count=3))
    agent.sub_agents[0].after_model_callback(None,response)
    assert ledger.input_tokens==20 and ledger.output_tokens==10
