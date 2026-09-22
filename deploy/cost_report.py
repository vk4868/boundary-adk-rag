"""Reconcile private usage metadata; this is an estimate, never a billing invoice."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
from datetime import UTC, date, datetime
from pathlib import Path

LEGACY_MODEL = 'gemini-3.1-flash-lite'
LEGACY_ATTRIBUTION_SHA256 = '37ca7f91bc2942c976f7f796dde304c0b7a8ee9638fe192bfe36116d2178e015'
# Verified Google global standard rates on 2026-09-22. Flash 3.8's
# introductory rates end 2026-12-31; do not silently reuse them later.
MODEL_RATES = {
    LEGACY_MODEL: {'input_per_million': 0.25, 'output_per_million': 1.50,
                   'uncertain_request_reserve': 0.10},
    'gemini-3.8-flash': {'input_per_million': 0.75, 'output_per_million': 3.75,
                       'uncertain_request_reserve': 0.20},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cloud-audit', type=Path)
    parser.add_argument('--output', type=Path, default=Path('work/cost-ledger.json'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / 'work'):
        raise SystemExit('Private cost ledger must stay inside project work/.')

    records = {}
    legacy_ids = set()
    legacy_path = root / 'work/legacy-flash-lite-attribution.json'
    if legacy_path.exists():
        legacy_raw = legacy_path.read_bytes()
        if hashlib.sha256(legacy_raw).hexdigest() != LEGACY_ATTRIBUTION_SHA256:
            raise SystemExit('Historical model-attribution snapshot integrity check failed.')
        legacy_ids = set(json.loads(legacy_raw)['request_ids'])
    local = root / 'data/audit/events.jsonl'
    if local.exists():
        for line in local.read_text().splitlines():
            row = json.loads(line)
            if row.get('event') in {'chat_request', 'adk_cli_run'}:
                records[row['request_id']] = row
    if args.cloud_audit:
        for entry in json.loads(args.cloud_audit.read_text()):
            row = entry.get('jsonPayload', {})
            if row.get('event') in {'chat_request', 'adk_cli_run'}:
                records[row['request_id']] = row

    input_tokens = sum(row.get('input_tokens', 0) for row in records.values())
    output_tokens = sum(row.get('output_tokens', 0) for row in records.values())
    model_usage = {}
    legacy_rows = 0
    for row in records.values():
        if not all(key in row for key in ('model', 'model_provider', 'model_location')):
            if row['request_id'] not in legacy_ids:
                raise SystemExit('Incomplete model attribution on a non-legacy audit row.')
            if any(row.get(key, expected) != expected for key, expected in (
                ('model', LEGACY_MODEL), ('model_provider', 'vertex'), ('model_location', 'global')
            )):
                raise SystemExit('Historical attribution conflicts with recorded metadata.')
            legacy_rows += 1
        model = row.get('model', LEGACY_MODEL)
        if model not in MODEL_RATES:
            raise SystemExit('Unpriced model in audit; update verified rates before reconciliation.')
        if model == 'gemini-3.8-flash':
            try:
                used_at = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                if used_at.tzinfo is None:
                    raise ValueError('Timestamp has no timezone')
            except (KeyError, TypeError, ValueError):
                raise SystemExit('Flash 3.8 usage requires a timestamp for time-limited pricing.')
            if used_at.astimezone(UTC).date() > date(2026, 12, 31):
                raise SystemExit('Flash 3.8 introductory pricing expired for this usage; verify new rates.')
        if row.get('model_location', 'global') != 'global':
            raise SystemExit('Non-global model usage requires separately verified pricing.')
        if row.get('model_provider', 'vertex') != 'vertex':
            raise SystemExit('Unpriced model provider in audit.')
        usage = model_usage.setdefault(model, {'requests': 0, 'input_tokens': 0,
                                             'output_tokens_including_reasoning': 0,
                                             'estimated_usd': 0.0})
        usage['requests'] += 1
        usage['input_tokens'] += row.get('input_tokens', 0)
        usage['output_tokens_including_reasoning'] += row.get('output_tokens', 0)
    for model, usage in model_usage.items():
        rates = MODEL_RATES[model]
        usage['estimated_usd'] = (
            usage['input_tokens'] * rates['input_per_million']
            + usage['output_tokens_including_reasoning'] * rates['output_per_million']
        ) / 1_000_000
    generation = sum(usage['estimated_usd'] for usage in model_usage.values())
    # Initial standalone provider probe is not part of the application audit.
    probe_generation = 8 * 0.25 / 1_000_000 + 4 * 1.50 / 1_000_000
    index = json.loads((root / 'data/index.json').read_text())
    ingest_chars = index['embedding']['billable_character_count']
    ingestion = ingest_chars * 0.00015 / 1000
    search_calls = sum(
        flow.get('function_calls', []).count('search_documents')
        for row in records.values() for flow in row.get('event_flow', [])
    )
    native_tool_upper_bound = sum(
        row.get('tool_calls', 0) for row in records.values()
        if row.get('event') == 'adk_cli_run' and not row.get('event_flow')
    )
    # Query character statistics are not persisted per request. Reserve the
    # largest cap permitted by Settings, including any supported configuration
    # changes across runs, plus three standalone retrieval probes.
    query_character_cap = 10000
    query_character_upper_estimate = (search_calls + native_tool_upper_bound + 3) * query_character_cap + 50
    query_embeddings = query_character_upper_estimate * 0.00015 / 1000

    builds = {}
    for path in (root / 'work').glob('cloud-build-*-result.json'):
        build = json.loads(path.read_text())
        if not build.get('id') or not build.get('startTime') or not build.get('finishTime'):
            continue
        def seconds(value: str) -> float:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        elapsed = max(0, seconds(build['finishTime']) - seconds(build['startTime']))
        builds[build['id']] = {
            'status': build['status'], 'seconds': round(elapsed, 3),
            'estimated_usd': math.ceil(elapsed / 60) * 0.006,
        }
    build_cost = sum(build['estimated_usd'] for build in builds.values())
    # Failed requests may have an incomplete final usage record. This reserve is
    # additional to observed usage, deliberately conservative, and not a bill.
    failed = sum(row.get('status') == 'error' for row in records.values())
    unmetered = sum(row.get('unmetered_model_calls', 0) for row in records.values())
    # Keep one reservation per uncertain request, including a successful request
    # with missing provider usage. Failed requests are already reserved above.
    uncertain_requests = sum(
        row.get('status') == 'error' or row.get('unmetered_model_calls', 0) > 0
        for row in records.values()
    )
    uncertainty_reserve = sum(
        MODEL_RATES[row.get('model', LEGACY_MODEL)]['uncertain_request_reserve']
        for row in records.values()
        if row.get('status') == 'error' or row.get('unmetered_model_calls', 0) > 0
    )
    hosting_storage_reserve = 1.25
    observed_estimate = generation + probe_generation + ingestion + query_embeddings + build_cost
    committed_estimate = observed_estimate + uncertainty_reserve + hosting_storage_reserve
    result = {
        'currency': 'USD', 'authorized_ceiling': 10,
        'model_usage': model_usage, 'generation_location': 'global',
        'verified_model_rates': MODEL_RATES,
        'pricing_verified_date': '2026-09-22',
        'flash_3_8_introductory_rate_end_date': '2026-12-31',
        'legacy_rows_attributed_to_flash_lite': legacy_rows,
        'request_count': len(records), 'input_tokens': input_tokens,
        'output_tokens_including_reasoning': output_tokens,
        'generation_estimate_usd': generation + probe_generation,
        'ingestion_billable_characters': ingest_chars,
        'ingestion_estimate_usd': ingestion,
        'query_embedding_character_upper_estimate': query_character_upper_estimate,
        'query_characters_reserved_per_search': query_character_cap,
        'query_embedding_estimate_usd': query_embeddings,
        'builds': builds, 'build_estimate_usd': build_cost,
        'observed_usage_estimate_usd': observed_estimate,
        'failed_request_count': failed,
        'unmetered_model_call_count': unmetered,
        'uncertain_request_count': uncertain_requests,
        'additional_uncertainty_reserve_usd': uncertainty_reserve,
        'hosting_storage_reserve_usd': hosting_storage_reserve,
        'usage_plus_reserves_usd': committed_estimate,
        'remaining_authorization_after_reserves_usd': 10 - committed_estimate,
        'limits': [
            'Not a billing invoice; free allowances, credits and tax are not applied.',
            'Only the 61 request IDs in the integrity-pinned historical snapshot may omit model attribution; those runs used Flash Lite.',
            'Flash 3.8 rates shown are introductory global rates through 2026-12-31; later usage requires rate updates.',
            'Query embeddings use an upper character estimate, not measured billing statistics.',
            'Cloud runtime/storage are reserved, not measured; all final cloud audit records must be supplied.',
            'HTTP evaluator dispatch reservations are not added again to token usage.',
            'Missing audit records or unrecorded external runs are outside this ledger.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.' + secrets.token_hex(6) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(json.dumps(result, indent=2) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
