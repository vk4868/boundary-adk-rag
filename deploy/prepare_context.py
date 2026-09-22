"""Build an explicit private upload context; never upload the repository wholesale."""
import argparse
import shutil
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='work/cloud-build-context')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=(root/args.output).resolve()
    if not out.is_relative_to(root/'work'):
        raise SystemExit('Output must be inside project work/.')
    if out.exists():
        raise SystemExit('Output exists; use a fresh named directory to avoid stale uploads.')
    required=['Dockerfile','pyproject.toml','uv.lock','.dockerignore','.gcloudignore','data/index.json']
    for name in required:
        if not (root/name).is_file(): raise SystemExit(f'Missing {name}')
    out.mkdir(parents=True)
    for name in required:
        target=out/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(root/name,target)
    for name in ['app','scripts','web']:
        shutil.copytree(root/name,out/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env*','.adk','*.log','*.jsonl','*.pdf','*.sqlite*','*.db'))
    print(out)
    print('Includes private derived index. Excludes PDFs, tokens, credentials, logs, and sessions.')

if __name__=='__main__': main()
