"""Native ADK evidence must never enter the container upload context."""
from pathlib import Path
import shutil
import subprocess
import sys


def test_prepared_context_excludes_nested_private_runtime_artifacts(tmp_path):
    project = tmp_path / 'project'
    (project / 'deploy').mkdir(parents=True)
    script = project / 'deploy/prepare_context.py'
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'deploy/prepare_context.py', script)
    for name in ['Dockerfile', 'pyproject.toml', 'uv.lock', '.dockerignore',
                 '.gcloudignore', 'data/index.json', 'app/agent.py',
                 'scripts/ingest.py', 'web/index.html']:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic runtime')
    for name in ['app/.adk/eval_history/private.json', 'app/.env',
                 'app/debug.log', 'app/answers.jsonl', 'app/source.pdf',
                 'app/session.sqlite3', 'app/sessions.db']:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('PRIVATE-SYNTHETIC-MARKER')
    result = subprocess.run([sys.executable, str(script), '--output', 'work/context'],
                            cwd=project, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = project / 'work/context'
    assert (output / 'app/agent.py').is_file()
    assert (output / 'data/index.json').is_file()
    assert not (output / 'app/.adk').exists()
    assert all(b'PRIVATE-SYNTHETIC-MARKER' not in path.read_bytes()
               for path in output.rglob('*') if path.is_file())
