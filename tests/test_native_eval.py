"""Offline execution of Google's native trajectory metric on synthetic events."""
from pathlib import Path
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator

BASE=Path(__file__).resolve().parents[1]/'evals'

def native_metric():
    config=EvalConfig.model_validate_json((BASE/'native.config.json').read_text())
    return TrajectoryEvaluator(eval_metric=EvalMetric(metric_name='tool_trajectory_avg_score',criterion=config.criteria['tool_trajectory_avg_score']))

def test_native_artifact_validates_as_sdk_evalset():
    dataset=EvalSet.model_validate_json((BASE/'native.evalset.json').read_text())
    assert len(dataset.eval_cases)==3
    assert sum(len(c.conversation) for c in dataset.eval_cases)==4

def test_native_metric_detects_missing_read_evidence():
    dataset=EvalSet.model_validate_json((BASE/'native.evalset.json').read_text())
    expected=dataset.eval_cases[0].conversation
    actual=[inv.model_copy(deep=True) for inv in expected]
    actual[0].intermediate_data.tool_uses.pop()
    result=native_metric().evaluate_invocations(actual,expected)
    assert result.overall_score==0.0

def test_native_metric_accepts_required_order_with_extra_tool():
    dataset=EvalSet.model_validate_json((BASE/'native.evalset.json').read_text())
    expected=dataset.eval_cases[0].conversation
    actual=[inv.model_copy(deep=True) for inv in expected]
    actual[0].intermediate_data.tool_uses.insert(2,actual[0].intermediate_data.tool_uses[1].model_copy(deep=True))
    result=native_metric().evaluate_invocations(actual,expected)
    assert result.overall_score==1.0
