"""Build native ADK EvalSet artifacts; this does not execute agents."""
import json
from pathlib import Path
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion

base=Path(__file__).resolve().parent
cases=[json.loads(line) for line in (base/'cases.jsonl').read_text().splitlines()]
selected=[case for case in cases if case['id'] in {'dev-01','dev-09','dev-13'}]
native=[]
for case in selected:
    conversations=[]
    for i,prompt in enumerate(case.get('prior_turns',[])+[case['question']]):
        conversations.append({'invocation_id':f'{case["id"]}-{i+1}','user_content':{'role':'user','parts':[{'text':prompt}]},'intermediate_data':{'tool_uses':[{'name':name,'args':{}} for name in ('list_sources','search_documents','read_evidence')]}})
    native.append({'eval_id':case['id'],'conversation':conversations,'session_input':{'app_name':'app','user_id':'native-eval-reviewer','state':{}}})
evalset=EvalSet.model_validate({'eval_set_id':'boundary_native_trajectory_v1','name':'Boundary native ADK tool trajectory','description':'Three development cases, four turns. Checks expected tool order only; no semantic accuracy claim.','eval_cases':native})
config=EvalConfig(criteria={'tool_trajectory_avg_score':ToolTrajectoryCriterion(threshold=1.0,match_type=ToolTrajectoryCriterion.MatchType.IN_ORDER,ignore_args=True)})
(base/'native.evalset.json').write_text(evalset.model_dump_json(indent=2))
(base/'native.config.json').write_text(config.model_dump_json(indent=2))
print('Validated native ADK EvalSet: 3 cases, 4 turns; tool order only, no model calls.')
