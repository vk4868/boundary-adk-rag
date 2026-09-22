"""Cost reconciliation regressions using only synthetic local metadata."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def run_report(tmp_path, row):
    project = tmp_path / 'project'
    (project / 'deploy').mkdir(parents=True)
    (project / 'data').mkdir()
    (project / 'work').mkdir()
    script = project / 'deploy/cost_report.py'
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'deploy/cost_report.py', script)
    (project / 'data/index.json').write_text(json.dumps({
        'embedding': {'billable_character_count': 0},
    }))
    cloud = project / 'work/cloud.json'
    cloud.write_text(json.dumps([{'jsonPayload': row}]))
    result = subprocess.run(
        [sys.executable, str(script), '--cloud-audit', str(cloud)],
        cwd=project, capture_output=True, text=True,
    )
    return result, project / 'work/cost-ledger.json'


def synthetic_usage(**changes):
    return {
        'event': 'chat_request', 'request_id': 'synthetic-only',
        'model': 'gemini-3.8-flash', 'model_provider': 'vertex',
        'model_location': 'global', 'timestamp': '2026-09-22T13:00:00+00:00',
        'status': 'error', 'input_tokens': 10000, 'output_tokens': 1000,
        'unmetered_model_calls': 1,
    } | changes


def test_model_specific_usage_and_single_uncertainty_reservation(tmp_path):
    result, output = run_report(tmp_path, synthetic_usage())
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report['model_usage']['gemini-3.8-flash']['estimated_usd'] == pytest.approx(.01125)
    assert report['additional_uncertainty_reserve_usd'] == pytest.approx(.20)
    assert report['uncertain_request_count'] == 1
    assert report['legacy_rows_attributed_to_flash_lite'] == 0
    assert os.stat(output).st_mode & 0o777 == 0o600


@pytest.mark.parametrize('changes', [
    {'model': 'unknown-model'},
    {'model_provider': 'unknown-provider'},
    {'model_location': 'us-central1'},
    {'timestamp': '2027-01-01T00:00:00+00:00'},
    {'timestamp': '2026-09-22T13:00:00'},
])
def test_unknown_or_expired_pricing_fails_without_writing_ledger(tmp_path, changes):
    result, output = run_report(tmp_path, synthetic_usage(**changes))
    assert result.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize('missing_key', ['model', 'model_provider', 'model_location'])
def test_new_request_cannot_inherit_historical_attribution(tmp_path, missing_key):
    row = synthetic_usage()
    del row[missing_key]
    result, output = run_report(tmp_path, row)
    assert result.returncode != 0
    assert 'non-legacy' in result.stderr
    assert not output.exists()
