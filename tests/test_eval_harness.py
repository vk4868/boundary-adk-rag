"""Offline checks of evaluation integrity and selected-case accounting."""
import copy
import contextlib
import io
import json
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'evals'/'run.py'
spec=importlib.util.spec_from_file_location('evaluation_harness',MODULE)
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)

class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.response={'request_id':'a'*32,'session_id':'b'*32,'answer':'A supported answer.','warnings':[],'sources':[{'source_id':'usig_2023','page_count':25,'title':'US Ismaili Games','version':'Supplied copy','scope':'Tournament'}], 'usage':{'input_tokens':10,'output_tokens':5,'model_calls':3,'tool_calls':2},'status':'answered','claims':[{'text':'Four overs in this competition.','evidence_ids':['usig_2023:p0001']}],'citations':[{'id':'usig_2023:p0001','source_id':'usig_2023','page':1,'title':'US Ismaili Games','text':'A bowler can bowl a maximum of four overs.'}],'governance':{'review_passed':True,'citation_gate_passed':True,'scope_gate_passed':True},'trace':[{'stage':'deterministic_gate','status':'passed'}]}
        self.case={'id':'test','category':'single_source','expected_statuses':['answered'],'required_sources':['usig_2023'],'expected_pages':{'usig_2023':[1]},'human_rubric':'Must be scoped.'}
    def test_valid_response_remains_semantically_pending(self):
        result=harness.evaluate(self.case,self.response)
        self.assertTrue(result['automated_checks_passed']);self.assertEqual(result['semantic_review'],'pending')
    def test_fabricated_reference_fails(self):
        self.response['claims'][0]['evidence_ids']=['usig_2023:p9999']
        self.assertIn('unknown_evidence_reference',harness.integrity_checks(self.response))
    def test_failed_review_is_not_success(self):
        self.response['governance']['review_passed']=False
        self.assertIn('governance_not_passed',harness.integrity_checks(self.response))
    def test_source_missing_is_visible(self):
        self.case['required_sources']=['mcc_2022']
        self.assertIn('missing_source:mcc_2022',harness.evaluate(self.case,self.response)['failures'])
    def test_wrong_page_fails_coverage(self):
        self.response['citations'][0]['page']=9
        self.assertIn('missing_expected_page:usig_2023',harness.evaluate(self.case,self.response)['failures'])
    def test_duplicate_ids_fail(self):
        self.response['citations'].append(copy.deepcopy(self.response['citations'][0]))
        self.assertIn('duplicate_citation_id',harness.integrity_checks(self.response))
    def test_safe_abstention_has_no_factual_claims(self):
        self.response['status']='insufficient_evidence'
        self.assertIn('rejected_with_evidence_claims',harness.integrity_checks(self.response))
    def test_malformed_response_recorded_explicitly(self):
        self.assertIn('response_not_object',harness.evaluate(self.case,[])['failures'])
        self.response['trace']=None
        self.assertIn('invalid_trace',harness.evaluate(self.case,self.response)['failures'])
    def test_metadata_privacy_allowlist(self):
        self.response['usage']['answer']='secret passage'
        self.response['request_id']='raw document passage'
        result=harness.evaluate(self.case,self.response)
        self.assertNotIn('answer',result['usage']);self.assertIsNone(result['request_id'])
    def test_fabricated_page_is_invalid(self):
        self.response['claims'][0]['evidence_ids']=['usig_2023:p9999']
        self.response['citations'][0].update(id='usig_2023:p9999',page=9999)
        self.assertIn('citation_outside_source',harness.integrity_checks(self.response))
    def test_complete_contract_checked(self):
        self.response['trace'][0]['duration_ms']='not-an-int'
        self.response['sources'][0].pop('version')
        self.response['citations'][0].pop('title')
        errors=harness.integrity_checks(self.response)
        self.assertIn('invalid_trace',errors);self.assertIn('invalid_source',errors);self.assertIn('invalid_citation_title',errors)
    def test_exact_case_denominator(self):
        import json
        cases=[json.loads(line) for line in MODULE.with_name('cases.jsonl').read_text().splitlines()]
        self.assertEqual(len(cases),20);self.assertEqual(len({c['id'] for c in cases}),20)
        self.assertEqual(sum(1+len(c.get('prior_turns',[])) for c in cases),23)

    def test_private_writer_secures_existing_temp_before_serializing(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'responses.json'
            stale_temporary=output.with_suffix('.tmp')
            stale_temporary.write_text('stale private response')
            stale_temporary.chmod(0o644)
            original_dump=harness.json.dump

            def checked_dump(value,handle,**kwargs):
                temporary=next(Path(directory).glob('.responses.json.*.tmp'))
                self.assertNotEqual(temporary,stale_temporary)
                self.assertEqual(stat.S_IMODE(temporary.stat().st_mode),0o600)
                return original_dump(value,handle,**kwargs)

            with patch.object(harness.json,'dump',side_effect=checked_dump):
                harness.write_private(output,{'response':'private'})

            self.assertEqual(stale_temporary.read_text(),'stale private response')
            self.assertEqual(stat.S_IMODE(stale_temporary.stat().st_mode),0o644)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
            self.assertEqual(output.read_text(),'{\n  "response": "private"\n}')

    def test_reservation_rejects_zero_negative_nonfinite_and_invalid_amounts(self):
        for flag in ('--per-turn-reservation-usd','--max-estimated-usd'):
            for value in ('0','-1','nan','inf','-inf','not-money'):
                with self.subTest(flag=flag,value=value):
                    with patch('sys.argv',['evals/run.py',flag+'='+value]), contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as failure:
                            harness.main()
                    self.assertEqual(failure.exception.code,2)

    def test_custom_reservation_is_checkpointed_before_uncertain_dispatch(self):
        work=MODULE.parents[1]/'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            cases_path=Path(directory)/'cases.jsonl'
            output=Path(directory)/'report.json'
            cases=[]
            for number in range(4):
                case=copy.deepcopy(self.case)
                case.update(id=f'offline-{number}',question='Offline fixture',prior_turns=[])
                cases.append(case)
            cases_path.write_text('\n'.join(json.dumps(case) for case in cases))
            calls=[]

            def uncertain_request(*_args):
                checkpoint=json.loads(output.read_text())
                calls.append(checkpoint['dispatched_turns'])
                self.assertEqual(checkpoint['dispatched_turns'],len(calls))
                self.assertEqual(checkpoint['per_turn_reservation_usd'],0.20)
                self.assertEqual(checkpoint['estimated_usd'],round(0.20*len(calls),2))
                self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
                raise TimeoutError('offline uncertainty')

            arguments=['evals/run.py','--execute','--cases',str(cases_path),
                       '--output',str(output),'--per-turn-reservation-usd','0.20',
                       '--max-estimated-usd','0.60']
            with patch('sys.argv',arguments), patch.dict(harness.os.environ,{'APP_AUTH_TOKEN':'offline-token'},clear=True), patch.object(harness,'request',side_effect=uncertain_request), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    harness.main()
            report=json.loads(output.read_text())
            self.assertEqual(failure.exception.code,1)
            self.assertEqual(calls,[1,2,3])
            self.assertEqual(report['estimated_usd'],0.60)
            self.assertEqual(report['planned']['case_count'],4)
            self.assertEqual(report['planned']['per_turn_reservation_usd'],0.20)
            self.assertEqual(report['executed_count'],3)
            self.assertFalse(report['complete'])
            self.assertEqual(report['stop_reason'],'evaluation_budget_reservation')

    def test_reported_setup_cost_cannot_bypass_follow_up_reservation(self):
        work=MODULE.parents[1]/'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            cases_path=Path(directory)/'cases.jsonl'
            output=Path(directory)/'report.json'
            case=copy.deepcopy(self.case)
            case.update(question='Follow-up fixture',prior_turns=['Setup fixture'])
            cases_path.write_text(json.dumps(case))
            setup=copy.deepcopy(self.response)
            setup['usage']['estimated_cost_usd']=0.15
            arguments=['evals/run.py','--execute','--cases',str(cases_path),
                       '--output',str(output),'--save-responses',
                       '--per-turn-reservation-usd','0.10','--max-estimated-usd','0.20']
            with patch('sys.argv',arguments), patch.dict(harness.os.environ,{'APP_AUTH_TOKEN':'offline-token'},clear=True), patch.object(harness,'request',return_value=setup) as request, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    harness.main()
            report=json.loads(output.read_text())
            self.assertEqual(failure.exception.code,1)
            self.assertEqual(request.call_count,1)
            self.assertEqual(report['planned']['endpoint_turns'],2)
            self.assertEqual(report['dispatched_turns'],1)
            self.assertEqual(report['estimated_usd'],0.15)
            self.assertEqual(report['stop_reason'],'evaluation_budget_reservation')
            self.assertEqual(report['results'][0]['status'],'not_dispatched')
            self.assertIn('follow_up_not_dispatched:budget_reservation',report['results'][0]['failures'])
            self.assertEqual(len(json.loads(output.with_suffix('.responses.json').read_text())),1)

if __name__=='__main__':unittest.main()
