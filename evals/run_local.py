#!/usr/bin/env python3
"""Bounded localhost-only Ollama smoke/regression run; source review is separate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings
from evals.run import evaluate, write_private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--ids', default='dev-01,dev-05,dev-09,dev-13,dev-15,dev-19')
    parser.add_argument('--output', type=Path, default=ROOT/'work/local-ollama-eval.json')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535: parser.error('invalid port')
    dataset = ROOT/'evals/cases.jsonl'
    all_cases = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    requested = args.ids.split(',')
    cases = [case for case in all_cases if case['id'] in requested]
    if len(cases) != len(set(requested)) or len(requested) != len(set(requested)):
        parser.error('unknown or duplicate case IDs')
    output = args.output.resolve()
    if ROOT/'work' not in output.parents: parser.error('output must be in private project work/')
    plan = {'cases':len(cases),'turns':sum(1+len(c.get('prior_turns',[])) for c in cases),'ids':[c['id'] for c in cases]}
    if not args.execute:
        print(json.dumps(plan,indent=2));return
    if output.exists():
        parser.error('output already exists; choose a new --output to preserve prior evidence')
    settings = get_settings()
    if settings.app_model_provider != 'ollama' or settings.app_embedding_provider != 'ollama':
        parser.error('requires local Ollama generation and embeddings')
    if not settings.auth_ready: parser.error('configure APP_TOKEN locally')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            raise RuntimeError('redirect rejected')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    base=f'http://127.0.0.1:{args.port}'
    with opener.open(base+'/health',timeout=5) as response: health=json.load(response)
    if not health.get('model_ready') or health.get('model_provider') != 'ollama' or health.get('model') != settings.app_model or health.get('index',{}).get('retrieval_provider') != 'ollama':
        parser.error('server health is not the configured local Ollama workflow')
    report={'plan':plan,'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),'index_sha256':settings.app_index_sha256,'model':settings.app_model,'provider':'ollama','health':health,'api_inference_cost_usd':0,'semantic_review':'pending','results':[],'turns':[],'complete':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    for case in cases:
        session=None; final=None;failed=False
        questions=case.get('prior_turns',[])+[case['question']]
        for i,question in enumerate(questions):
            t=time.monotonic();record={'case_id':case['id'],'turn':i,'question':question,'is_final':i==len(questions)-1}
            payload={'message':question}
            if session:payload['session_id']=session
            req=urllib.request.Request(base+'/api/chat',json.dumps(payload).encode(),{'Content-Type':'application/json','X-App-Token':settings.app_token.get_secret_value()})
            try:
                with opener.open(req,timeout=settings.app_max_request_seconds+30) as response:
                    record['http_status']=response.status
                    final=json.load(response)
                record['response']=final
                session=final.get('session_id')
                # Never continue a context-dependent case after an invalid setup.
                if not record['is_final'] and (not session or final.get('status')!='answered'):
                    failed=True
                    record['failure']='setup_not_answered'
            except urllib.error.HTTPError as exc:
                record['http_status']=exc.code
                record['error_body']=exc.read().decode('utf-8','replace')
                failed=True;final=None
            except Exception as exc:
                record['error_type']=type(exc).__name__
                failed=True;final=None
            record['elapsed_seconds']=round(time.monotonic()-t,3)
            report['turns'].append(record)
            report['elapsed_seconds']=round(time.monotonic()-started,3)
            write_private(output,report)
            print(json.dumps({'case_id':case['id'],'turn':i,'http':record.get('http_status'),'status':(final or {}).get('status'),'seconds':record['elapsed_seconds']}),flush=True)
            if failed:break
        result=evaluate(case,final) if not failed else {'case_id':case['id'],'automated_checks_passed':False,'failures':['unavailable_or_failed_setup'],'semantic_review':'pending'}
        report['results'].append(result)
        write_private(output,report)
    report['complete']=True
    report['automated_pass_count']=sum(r['automated_checks_passed'] for r in report['results'])
    report['dispatched_turns']=len(report['turns'])
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    write_private(output,report)
    print(json.dumps({'complete':True,'automated_pass_count':report['automated_pass_count'],'cases':len(cases),'dispatched_turns':len(report['turns'])}),flush=True)

if __name__=='__main__':main()
