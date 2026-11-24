"""Unit tests for CallAnalysisResult Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.call_analysis import CallAnalysisResult


def _valid_payload() -> dict:
    return {
        "call_id": "CALL-001",
        "analyzed_at": "2026-11-24T20:00:00Z",
        "transcript_language": "ar",
        "speakers": [
            {"speaker": "customer", "text": "تم خصم المبلغ مرتين", "turn_index": 0},
            {"speaker": "agent", "text": "أعتذر لك، سأراجع الطلب حالاً", "turn_index": 1},
        ],
        "sentiment": {
            "overall": "negative",
            "score": 3.5,
            "trajectory": "improving",
            "evidence": ["تم خصم المبلغ مرتين"],
        },
        "problem": {
            "summary": "Customer was charged twice for the same order.",
            "category": "billing",
            "priority": "high",
            "priority_rationale": "Duplicate charge affects customer funds.",
            "keywords": ["duplicate charge", "billing"],
        },
        "agent_evaluation": {
            "empathy_score": 8.0,
            "clarity_score": 7.5,
            "resolution_effectiveness_score": 7.0,
            "professionalism_score": 9.0,
            "overall_score": 7.9,
            "strengths": ["Polite apology"],
            "areas_for_improvement": ["Provide refund SLA"],
            "evaluation_evidence": ["أعتذر لك، سأراجع الطلب حالاً"],
        },
        "resolution": {
            "resolved": False,
            "resolution_type": "pending_follow_up",
            "resolution_summary": "Escalated to billing team.",
            "follow_up_required": True,
            "follow_up_actions": ["Confirm refund within 48h"],
        },
        "call_summary": "Customer reported a duplicate charge. Agent apologized and escalated.",
        "key_insights": ["Duplicate billing triggers high frustration."],
        "recommendations": ["Automate duplicate charge detection."],
        "confidence_score": 0.91,
        "low_confidence_flags": [],
    }


def test_valid_payload_passes() -> None:
    result = CallAnalysisResult.model_validate(_valid_payload())
    assert result.call_id == "CALL-001"
    assert result.problem.category == "billing"
    assert result.agent_evaluation.overall_score == 7.9


def test_score_out_of_range_rejected() -> None:
    payload = _valid_payload()
    payload["sentiment"]["score"] = 11.0
    with pytest.raises(ValidationError):
        CallAnalysisResult.model_validate(payload)


def test_invalid_category_rejected() -> None:
    payload = _valid_payload()
    payload["problem"]["category"] = "unknown_category"
    with pytest.raises(ValidationError):
        CallAnalysisResult.model_validate(payload)


def test_missing_required_field_rejected() -> None:
    payload = _valid_payload()
    del payload["call_summary"]
    with pytest.raises(ValidationError):
        CallAnalysisResult.model_validate(payload)


def test_confidence_out_of_bounds_rejected() -> None:
    payload = _valid_payload()
    payload["confidence_score"] = 1.5
    with pytest.raises(ValidationError):
        CallAnalysisResult.model_validate(payload)
