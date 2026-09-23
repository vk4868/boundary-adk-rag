"""Offline integration tests for issued-only atomic evidence reads."""

from types import SimpleNamespace

import pytest
from google.adk.events import EventActions

from app.agents import build_agent
from app.config import Settings
from app.index import IndexRepository
from app.models import CorpusIndex, EmbeddingDescriptor, PageRecord, SourceRecord
from app.tools import BudgetExceeded, READ_UNAVAILABLE_ERROR, RunLedger, build_tools


@pytest.fixture
def read_harness(tmp_path):
    sources = [
        SourceRecord(
            source_id="rules",
            title="Rules",
            version="test",
            scope="authorized rules",
            competition="MCC",
            allowed_roles=["analyst"],
            page_count=3,
            sha256="a" * 64,
        ),
        SourceRecord(
            source_id="secret",
            title="Secret Rules",
            version="test",
            scope="restricted rules",
            competition="MCC",
            allowed_roles=["admin"],
            page_count=1,
            sha256="b" * 64,
        ),
    ]
    pages = [
        PageRecord(
            evidence_id=f"rules:p{number:04d}",
            source_id="rules",
            page=number,
            text=("middle topic condition" if number == 2 else f"context page {number}"),
        )
        for number in (1, 2, 3)
    ] + [
        PageRecord(
            evidence_id="secret:p0001",
            source_id="secret",
            page=1,
            text="restricted",
        )
    ]
    index = CorpusIndex(
        schema_version=1,
        embedding=EmbeddingDescriptor(provider="lexical"),
        sources=sources,
        pages=pages,
    )
    path = tmp_path / "index.json"
    path.write_text(index.model_dump_json(), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        app_enable_model_calls=False,
        app_model_provider="disabled",
        app_embedding_provider="lexical",
        app_index_path=path,
        app_audit_path=tmp_path / "audit.jsonl",
    )
    repository = IndexRepository(settings)
    ledger = RunLedger("read-contract")
    researcher = build_agent(settings, repository, ledger, "analyst").sub_agents[0]
    read_tool = next(tool for tool in researcher.tools if tool.name == "read_evidence")
    return settings, repository, ledger, researcher, read_tool


def _tool_context():
    return SimpleNamespace(
        actions=EventActions(),
        tool_confirmation=None,
        request_confirmation=lambda **_kwargs: None,
    )


async def _invoke(researcher, tool, args):
    override = researcher.before_tool_callback(tool, args, _tool_context())
    if override is not None:
        return override
    return await tool.run_async(args=args, tool_context=_tool_context())


@pytest.mark.asyncio
async def test_bad_read_can_be_corrected_through_actual_adk_callback(read_harness):
    _settings, _repository, ledger, researcher, read_tool = read_harness
    ledger.issued_evidence_ids.add("rules:p0002")
    ledger.last_search_issued_ids = {"rules:p0002"}

    bad = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p0003"]}
    )
    assert bad == {
        "error": READ_UNAVAILABLE_ERROR,
        "allowed_evidence_ids": ["rules:p0002"],
        "retry_allowed": True,
        "guidance": (
            "Retry read_evidence once using exact IDs from allowed_evidence_ids."
        ),
    }
    assert ledger.read_evidence_attempts == 1
    assert not ledger.read_evidence_ids

    corrected = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p0002"]}
    )
    assert corrected["evidence"][0]["evidence_id"] == "rules:p0002"
    assert ledger.read_evidence_attempts == 2
    assert ledger.read_evidence_ids == {"rules:p0002"}


@pytest.mark.asyncio
async def test_malformed_missing_and_unauthorized_batches_are_atomic(read_harness):
    _settings, _repository, ledger, researcher, read_tool = read_harness
    ledger.issued_evidence_ids.update(
        {"rules:p0001", "rules:p9999", "secret:p0001"}
    )
    for evidence_ids in (
        ["rules:p1"],
        ["rules:p0001", "rules:p9999"],
        ["rules:p0001", "secret:p0001"],
    ):
        result = await _invoke(
            researcher, read_tool, {"evidence_ids": evidence_ids}
        )
        assert result["error"] == READ_UNAVAILABLE_ERROR
        assert result["allowed_evidence_ids"] == []
        assert result["retry_allowed"] is False
        assert not ledger.read_evidence_ids
    assert ledger.read_evidence_attempts == 3


@pytest.mark.asyncio
async def test_exhausted_ordinary_recovery_blocks_a_third_read_after_valid_evidence(
    read_harness,
):
    _settings, _repository, ledger, researcher, read_tool = read_harness
    ledger.issued_evidence_ids.update(
        {"rules:p0001", "rules:p0002", "rules:p0003"}
    )
    ledger.last_search_issued_ids = {
        "rules:p0001",
        "rules:p0002",
        "rules:p0003",
    }
    first = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p0001"]}
    )
    assert first["evidence"][0]["evidence_id"] == "rules:p0001"

    for unknown in ("rules:p9998", "rules:p9999"):
        failed = await _invoke(
            researcher, read_tool, {"evidence_ids": [unknown]}
        )
        assert failed["error"] == READ_UNAVAILABLE_ERROR
    assert ledger.ordinary_read_failures == 2

    blocked = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p0002"]}
    )
    assert blocked["retry_allowed"] is False
    assert ledger.read_evidence_ids == {"rules:p0001"}
    assert ledger.read_evidence_attempts == 4
    assert ledger.tool_calls == 4


@pytest.mark.asyncio
async def test_new_search_does_not_reopen_invocation_read_correction(read_harness):
    settings, repository, ledger, researcher, read_tool = read_harness
    ledger.issued_evidence_ids.add("rules:p0001")
    ledger.last_search_issued_ids = {"rules:p0001"}
    first_bad = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p9998"]}
    )
    assert first_bad["retry_allowed"] is True
    assert ledger.ordinary_read_failures == 1

    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )
    search_tool.func(query="middle topic condition", top_k=1)
    assert ledger.ordinary_read_failures == 1

    second_bad = await _invoke(
        researcher, read_tool, {"evidence_ids": ["rules:p9999"]}
    )
    assert second_bad["retry_allowed"] is False
    assert ledger.ordinary_read_failures == 2

    issued = sorted(ledger.last_search_issued_ids)[0]
    third = await _invoke(
        researcher, read_tool, {"evidence_ids": [issued]}
    )
    assert third["retry_allowed"] is False
    assert not ledger.read_evidence_ids


def test_search_returns_bounded_explicit_adjacent_ids_and_issues_them(read_harness):
    settings, repository, ledger, _researcher, _read_tool = read_harness
    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )
    result = search_tool.func(query="middle topic condition", top_k=1)

    hit = result["results"][0]
    assert hit["evidence_id"] == "rules:p0002"
    assert hit["adjacent_evidence_ids"] == ["rules:p0001", "rules:p0003"]
    assert ledger.last_search_hit_ids == {"rules:p0002"}
    assert ledger.last_search_issued_ids == {
        "rules:p0001",
        "rules:p0002",
        "rules:p0003",
    }
    assert ledger.issued_evidence_ids == ledger.last_search_issued_ids
    returned_fragments = [hit["snippet"]] + [
        preview["snippet"] for preview in hit["adjacent_previews"]
    ]
    assert ledger.evidence_chars == sum(map(len, returned_fragments))


def test_adjacent_reference_is_charged_if_later_returned_as_a_real_hit(read_harness):
    settings, _repository, ledger, _researcher, _read_tool = read_harness
    settings.app_max_evidence_chars = 1000
    ledger.add_evidence_batch(settings, [("rules:p0001", "x" * 950)])
    ledger.issue_evidence_references({"rules:p0002"})

    with pytest.raises(BudgetExceeded, match="evidence character budget"):
        ledger.add_evidence_batch(settings, [("rules:p0002", "y" * 100)])

    assert ledger.evidence_chars == 950
    assert len(ledger.search_exposure_fingerprints) == 1
    assert "rules:p0002" in ledger.issued_evidence_ids


def test_exact_fragment_repeats_dedupe_but_distinct_fragments_are_charged(
    read_harness,
):
    settings, _repository, ledger, _researcher, _read_tool = read_harness
    first = ("rules:p0001", "first fragment")
    second = ("rules:p0001", "different fragment")

    ledger.add_evidence_batch(settings, [first, first])
    assert ledger.evidence_chars == len(first[1])
    ledger.add_evidence_batch(settings, [first, second])

    assert ledger.evidence_chars == len(first[1]) + len(second[1])
    assert len(ledger.search_exposure_fingerprints) == 2


def test_two_search_preview_budget_leaves_room_for_three_full_pages(read_harness):
    settings, _repository, ledger, _researcher, _read_tool = read_harness
    search_fragments = []
    for search_number in range(2):
        for hit_number in range(5):
            search_fragments.append(
                (f"rules:p{hit_number + 1:04d}", "h" * 700 + str(search_number))
            )
            search_fragments.extend(
                [
                    (
                        f"rules:p{hit_number + 1:04d}",
                        "p" * 350 + str(search_number),
                    ),
                    (
                        f"rules:p{hit_number + 1:04d}",
                        "n" * 350 + str(search_number),
                    ),
                ]
            )
    ledger.add_evidence_batch(settings, search_fragments)
    ledger.add_read_evidence_batch(
        settings,
        [
            ("rules:p0001", "a" * 2987),
            ("rules:p0002", "b" * 3059),
            ("rules:p0003", "c" * 3039),
        ],
    )

    assert ledger.evidence_chars <= settings.app_max_evidence_chars
    assert settings.app_max_evidence_chars - ledger.evidence_chars > 0


def test_search_preview_budget_failure_is_atomic(read_harness):
    settings, repository, ledger, _researcher, _read_tool = read_harness
    settings.app_max_evidence_chars = 1000
    for page in repository.load().pages:
        if page.source_id == "rules":
            page.text = "topic " + "x " * 700
    search_tool = next(
        tool
        for tool in build_tools(repository, settings, ledger, "analyst")
        if tool.name == "search_documents"
    )

    with pytest.raises(BudgetExceeded, match="evidence character budget"):
        search_tool.func(query="topic", top_k=1)

    assert ledger.evidence_chars == 0
    assert not ledger.issued_evidence_ids
    assert not ledger.search_exposure_fingerprints
    assert ledger.successful_searches == 0
    assert not ledger.last_search_hit_ids
    assert not ledger.last_search_issued_ids


def test_new_read_and_search_state_is_cleared_between_invocations(read_harness):
    settings, _repository, ledger, _researcher, _read_tool = read_harness
    ledger.add_evidence_batch(settings, [("rules:p0001", "snippet")])
    ledger.issue_evidence_references({"rules:p0002"})
    ledger.last_search_hit_ids = {"rules:p0001"}
    ledger.last_search_issued_ids = {"rules:p0001", "rules:p0002"}
    ledger.read_evidence_attempts = 2

    ledger.reset("next-invocation")

    assert not ledger.issued_evidence_ids
    assert not ledger.search_exposure_fingerprints
    assert not ledger.last_search_hit_ids
    assert not ledger.last_search_issued_ids
    assert ledger.read_evidence_attempts == 0
    assert ledger.ordinary_read_failures == 0
