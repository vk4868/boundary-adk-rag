#!/usr/bin/env python3
"""Custom HTTP development evaluator. No judge calls; semantic quality needs source review."""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.request

SOURCE_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{1,63}$')
OPAQUE_ID = re.compile(r'^[A-Za-z0-9_-]{24,96}$')
COUNTERS = ('input_tokens','output_tokens','model_calls','tool_calls')
STATUSES = {'answered','insufficient_evidence','rejected'}

def nonempty(value):return isinstance(value,str) and bool(value.strip())
def opaque(value):return isinstance(value,str) and bool(OPAQUE_ID.fullmatch(value))
def count(value):return type(value) is int and value>=0

def positive_finite_usd(value):
    try:
        number=float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError('must be a finite positive USD amount') from exc
    if not math.isfinite(number) or number<=0:
        raise argparse.ArgumentTypeError('must be a finite positive USD amount')
    return number

def usage_metadata(data):
    usage=data.get('usage',{}) if isinstance(data,dict) else {}
    if not isinstance(usage,dict):return {}
    clean={key:usage[key] for key in COUNTERS if count(usage.get(key))}
    cost=usage.get('estimated_cost_usd',usage.get('estimated_usd'))
    if type(cost) in (int,float) and math.isfinite(cost) and 0<=cost<100:clean['estimated_cost_usd']=cost
    return clean

def integrity_checks(data) -> list[str]:
    if not isinstance(data,dict):return ['response_not_object']
    errors=[]
    if data.get('status') not in STATUSES:errors.append('invalid_status')
    if not opaque(data.get('request_id')):errors.append('invalid_request_id')
    if not opaque(data.get('session_id')):errors.append('invalid_session_id')
    if not nonempty(data.get('answer')):errors.append('invalid_answer')
    usage=data.get('usage')
    if not isinstance(usage,dict) or any(not count(usage.get(k)) for k in COUNTERS):errors.append('invalid_usage')
    trace=data.get('trace')
    if not isinstance(trace,list):errors.append('invalid_trace');trace=[]
    elif any(not isinstance(t,dict) or not nonempty(t.get('stage')) or t.get('status') not in {'passed','failed','skipped'} or (t.get('duration_ms') is not None and not count(t['duration_ms'])) for t in trace):errors.append('invalid_trace')
    governance=data.get('governance')
    if not isinstance(governance,dict) or any(type(governance.get(k)) is not bool for k in ('review_passed','citation_gate_passed','scope_gate_passed')):errors.append('invalid_governance')
    if data.get('status')=='answered':
        if not isinstance(governance,dict) or any(governance.get(k) is not True for k in ('review_passed','citation_gate_passed','scope_gate_passed')):errors.append('governance_not_passed')
        if not any(isinstance(t,dict) and t.get('stage')=='deterministic_gate' and t.get('status')=='passed' for t in trace):errors.append('deterministic_gate_not_passed')
    if not isinstance(data.get('warnings'),list) or any(not isinstance(w,str) for w in data['warnings']):errors.append('invalid_warnings')
    citations=data.get('citations');claims=data.get('claims');sources=data.get('sources')
    if not isinstance(citations,list) or not isinstance(claims,list):return sorted(set(errors+['invalid_claim_or_citation_array']))
    source_pages={}
    if not isinstance(sources,list):errors.append('invalid_sources')
    else:
        for source in sources:
            if not isinstance(source,dict) or not isinstance(source.get('source_id'),str) or not SOURCE_ID.fullmatch(source['source_id']) or type(source.get('page_count')) is not int or source['page_count']<1 or any(not nonempty(source.get(k)) for k in ('title','version','scope')):errors.append('invalid_source');continue
            if source['source_id'] in source_pages:errors.append('duplicate_source')
            source_pages[source['source_id']]=source['page_count']
    ids=[]
    for cite in citations:
        if not isinstance(cite,dict):errors.append('invalid_citation');continue
        eid=cite.get('id');sid=cite.get('source_id');page=cite.get('page')
        if not nonempty(eid):errors.append('empty_citation_id')
        else:ids.append(eid)
        if not isinstance(sid,str) or not SOURCE_ID.fullmatch(sid) or type(page) is not int or page<1:errors.append('invalid_citation_location')
        elif eid!=f'{sid}:p{page:04d}':errors.append('noncanonical_citation_id')
        elif sid not in source_pages or page>source_pages[sid]:errors.append('citation_outside_source')
        if not nonempty(cite.get('text')):errors.append('empty_citation_excerpt')
        if not nonempty(cite.get('title')):errors.append('invalid_citation_title')
    if len(ids)!=len(set(ids)):errors.append('duplicate_citation_id')
    if data.get('status')=='answered' and not claims:errors.append('answered_without_claims')
    if data.get('status') in {'insufficient_evidence','rejected'} and (claims or citations):errors.append('rejected_with_evidence_claims')
    for claim in claims:
        if not isinstance(claim,dict):errors.append('invalid_claim');continue
        if not nonempty(claim.get('text')):errors.append('empty_claim')
        refs=claim.get('evidence_ids')
        if not isinstance(refs,list) or not refs:errors.append('uncited_claim');continue
        if any(not isinstance(ref,str) or ref not in ids for ref in refs):errors.append('unknown_evidence_reference')
        elif len(refs)!=len(set(refs)):errors.append('duplicate_claim_reference')
    return sorted(set(errors))

def evaluate(case:dict,data) -> dict:
    errors=integrity_checks(data);record=data if isinstance(data,dict) else {}
    status=record.get('status') if record.get('status') in STATUSES else 'invalid'
    if status not in case['expected_statuses']:errors.append('unexpected_status')
    citations=record.get('citations',[]) if isinstance(record.get('citations',[]),list) else []
    valid_citations=[c for c in citations if isinstance(c,dict) and isinstance(c.get('source_id'),str) and SOURCE_ID.fullmatch(c['source_id']) and type(c.get('page')) is int and c['page']>=1]
    actual_sources={c['source_id'] for c in valid_citations}
    if status=='answered' or case['expected_statuses']==['answered']:
        for source in case.get('required_sources',[]):
            if source not in actual_sources:errors.append(f'missing_source:{source}')
        for source,pages in case.get('expected_pages',{}).items():
            if not any(c['source_id']==source and c['page'] in pages for c in valid_citations):errors.append(f'missing_expected_page:{source}')
    return {'case_id':case['id'],'category':case['category'],'status':status,'automated_checks_passed':not errors,'failures':sorted(set(errors)),'semantic_review':'pending','human_rubric':case['human_rubric'],'request_id':record.get('request_id') if opaque(record.get('request_id')) else None,'usage':usage_metadata(record),'citation_locations':[{'source_id':c['source_id'],'page':c['page']} for c in valid_citations]}

def request(base,token,message,session_id,timeout):
    payload={'message':message}
    if session_id:payload['session_id']=session_id
    req=urllib.request.Request(base.rstrip('/')+'/api/chat',json.dumps(payload).encode(),{'Content-Type':'application/json','X-App-Token':token},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)


def write_private(path: Path, value: object) -> None:
    """Atomically replace a JSON report without exposing its new bytes."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        # Enforce the mode on the descriptor before JSON serialization writes
        # any bytes, even if the platform changed the creation mode.
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',default='http://127.0.0.1:8000');p.add_argument('--cases',type=Path,default=Path(__file__).with_name('cases.jsonl'))
    p.add_argument('--output',type=Path,default=Path('work/eval-report.json'));p.add_argument('--ids',help='Comma-separated case IDs; defaults all20')
    p.add_argument('--timeout',type=float,default=150);p.add_argument('--save-responses',action='store_true');p.add_argument('--max-estimated-usd',type=positive_finite_usd,default=1.0)
    p.add_argument('--per-turn-reservation-usd',type=positive_finite_usd,default=0.10,help='Conservative allowance reserved before every endpoint dispatch; retained when usage is uncertain')
    p.add_argument('--execute',action='store_true',help='Explicitly opt into endpoint calls; otherwise plan only')
    a=p.parse_args();all_cases=[json.loads(line) for line in a.cases.read_text().splitlines() if line.strip()]
    if len({c['id'] for c in all_cases})!=len(all_cases):p.error('Duplicate case IDs')
    cases=all_cases
    if a.ids:
        selected=set(a.ids.split(','));cases=[c for c in all_cases if c['id'] in selected]
        if selected-{c['id'] for c in cases}:p.error('Unknown requested case IDs')
    plan={'case_count':len(cases),'endpoint_turns':sum(1+len(c.get('prior_turns',[])) for c in cases),'ids':[c['id'] for c in cases],'semantic_scoring':'source_review_required','per_turn_reservation_usd':a.per_turn_reservation_usd,'max_estimated_usd':a.max_estimated_usd}
    if not a.execute:print(json.dumps(plan,indent=2));return
    token=os.environ.get('APP_AUTH_TOKEN') or os.environ.get('APP_TOKEN')
    if not token:p.error('Set APP_AUTH_TOKEN or APP_TOKEN; never pass token on command line')
    out=a.output.resolve();project=Path(__file__).resolve().parents[1]
    if project/'work' not in out.parents:p.error('Output must be under project work/ (private, gitignored)')
    reservation=Decimal(str(a.per_turn_reservation_usd));budget=Decimal(str(a.max_estimated_usd))
    results=[];raw=[];estimated_usd=Decimal('0');stop_reason=None;dispatched=0;start=time.monotonic()
    def checkpoint():
        report={'dataset_sha256':hashlib.sha256(a.cases.read_bytes()).hexdigest(),'planned':plan,'executed_count':len(results),'dispatched_turns':dispatched,'complete':len(results)==len(cases),'stop_reason':stop_reason,'automated_pass_count':sum(r['automated_checks_passed'] for r in results),'estimated_usd':float(estimated_usd),'per_turn_reservation_usd':a.per_turn_reservation_usd,'max_estimated_usd':a.max_estimated_usd,'elapsed_seconds':round(time.monotonic()-start,3),'semantic_review':'pending','results':results}
        out.parent.mkdir(parents=True,exist_ok=True)
        write_private(out,report)
        if a.save_responses:write_private(out.with_suffix('.responses.json'),raw)
        return report
    checkpoint()
    for case in cases:
        required_turns=1+len(case.get('prior_turns',[]))
        if estimated_usd+reservation*required_turns>budget:stop_reason='evaluation_budget_reservation';break
        session=None;case_started=time.monotonic();result=None
        try:
            prompts=case.get('prior_turns',[])+[case['question']]
            for turn_number,prompt in enumerate(prompts):
                if estimated_usd+reservation>budget:
                    stop_reason='evaluation_budget_reservation'
                    result={'case_id':case['id'],'category':case['category'],'status':'not_dispatched','automated_checks_passed':False,'failures':['follow_up_not_dispatched:budget_reservation'],'semantic_review':'pending'}
                    break
                estimated_usd+=reservation;dispatched+=1;checkpoint()  # Retain reservation on uncertain transport outcome.
                data=request(a.base_url,token,prompt,session,a.timeout)
                clean_usage=usage_metadata(data);cost=clean_usage.get('estimated_cost_usd')
                if cost is not None:estimated_usd+=Decimal(str(cost))-reservation
                if a.save_responses:raw.append({'case_id':case['id'],'question':prompt,'response':data})
                if turn_number<len(prompts)-1:
                    failures=integrity_checks(data)
                    if not isinstance(data,dict) or data.get('status')!='answered':failures.append('setup_not_answered')
                    if failures:
                        result=evaluate(case,data);result['failures']=sorted(set('setup:'+f for f in failures));result['automated_checks_passed']=False;break
                    session=data['session_id']
                else:result=evaluate(case,data)
        except Exception as exc:
            result={'case_id':case['id'],'category':case['category'],'automated_checks_passed':False,'failures':['request_failed:'+type(exc).__name__],'semantic_review':'pending'}
        result['duration_seconds']=round(time.monotonic()-case_started,3);results.append(result);checkpoint()
        print(json.dumps({'case_id':case['id'],'passed':result['automated_checks_passed'],'failures':result['failures']}),flush=True)
        if stop_reason:break
    report=checkpoint();print(json.dumps({'report':str(out),'complete':report['complete'],'automated_pass_count':report['automated_pass_count'],'semantic_review':'pending'}))
    if not report['complete'] or report['automated_pass_count']!=len(cases):raise SystemExit(1)

if __name__=='__main__':main()
