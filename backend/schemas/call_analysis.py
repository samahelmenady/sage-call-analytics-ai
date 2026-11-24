"""
Validated Pydantic schemas for customer support call analysis.

Every GenAI provider output must pass LLMCallAnalysisSchema validation,
deterministic grounding/consistency checks, and rule-based risk scoring
before being persisted or returned to the client.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SpeakerTurn(BaseModel):
    speaker: Literal["agent", "customer", "unknown"]
    text: str
    turn_index: int = Field(ge=0)
    start_seconds: Optional[float] = Field(default=None, ge=0.0)
    end_seconds: Optional[float] = Field(default=None, ge=0.0)


class SentimentAnalysis(BaseModel):
    overall: Literal["positive", "neutral", "negative", "mixed"]
    score: float = Field(ge=0.0, le=10.0, description="Estimated customer satisfaction 0=worst, 10=best")
    trajectory: Literal["improving", "stable", "declining", "volatile"]
    emotions: list[str] = Field(
        default_factory=list,
        description="Observed customer emotions grounded in the transcript",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Direct customer transcript quotes supporting the sentiment",
    )


class ProblemClassification(BaseModel):
    summary: str = Field(description="Concise problem description")
    category: Literal[
        "billing",
        "technical",
        "shipping",
        "account",
        "product_quality",
        "returns",
        "general_inquiry",
        "other",
    ]
    priority: Literal["critical", "high", "medium", "low"]
    priority_rationale: str
    keywords: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    root_cause: Optional[str] = Field(
        default=None,
        description="Root cause only if explicitly supported by transcript evidence; otherwise null",
    )
    root_cause_evidence: list[str] = Field(default_factory=list)


class AgentEvaluation(BaseModel):
    applicable: bool = Field(
        default=True,
        description="False when no agent speaks in the transcript (all scores become null / N/A)",
    )
    empathy_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    clarity_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    resolution_effectiveness_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    professionalism_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    evaluation_evidence: list[str] = Field(
        default_factory=list,
        description="Direct agent transcript quotes supporting scores",
    )


class ResolutionStatus(BaseModel):
    resolved: bool
    resolution_type: Literal[
        "fully_resolved",
        "partially_resolved",
        "escalated",
        "pending_follow_up",
        "unresolved",
    ]
    resolution_summary: Optional[str] = None
    follow_up_required: bool
    follow_up_actions: list[str] = Field(default_factory=list)
    escalation_required: bool = False
    escalation_reason: Optional[str] = None


class OperationalSignals(BaseModel):
    repeated_complaint: bool = False
    missed_commitment: bool = False
    potential_sla_violation: bool = False
    signal_evidence: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Explainable, deterministic rule-based Customer Risk Score (0-100)."""

    score: int = Field(ge=0, le=100)
    level: Literal["low", "medium", "high", "critical"]
    factors: list[str] = Field(default_factory=list)


class LLMCallAnalysisSchema(BaseModel):
    """Strict schema passed to GenAI structured output (no untyped dict fields)."""

    call_id: str
    analyzed_at: str
    transcript_language: Literal["ar", "en", "mixed", "other"]

    speakers: list[SpeakerTurn] = Field(default_factory=list)
    sentiment: SentimentAnalysis
    problem: ProblemClassification
    agent_evaluation: AgentEvaluation
    resolution: ResolutionStatus
    operational_signals: OperationalSignals = Field(default_factory=OperationalSignals)

    call_summary: str = Field(description="2-4 sentence factual summary")
    key_insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    confidence_score: float = Field(ge=0.0, le=1.0)
    low_confidence_flags: list[str] = Field(default_factory=list)


class CallAnalysisResult(LLMCallAnalysisSchema):
    # Server-populated deterministic & enrichment fields
    risk_assessment: Optional[RiskAssessment] = None
    consistency_warnings: list[str] = Field(default_factory=list)
    raw_transcript: Optional[str] = None
    source: Literal["audio", "text"] = "text"
    call_metadata: Optional[dict[str, Any]] = None
    analysis_meta: Optional[dict[str, Any]] = None
