"""
Deterministic post-processing, grounding verification, cross-field consistency,
and explainable rule-based Customer Risk Score computation.

Zero ML/DL models — pure deterministic business rules and text verification.
"""

from __future__ import annotations

import re
from typing import Optional

from backend.schemas.call_analysis import (
    CallAnalysisResult,
    RiskAssessment,
)
from backend.services.genai.prompts.system_prompt import DEFAULT_RUBRIC

_TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")


def _norm_for_match(text: str) -> str:
    s = re.sub("[إأآٱ]", "ا", text.lower())
    s = s.replace("ى", "ي").replace("ة", "ه")
    s = re.sub(r"[\u064B-\u065F\u0670]", "", s)  # strip diacritics
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_quote_grounded(quote: str, norm_transcript: str) -> bool:
    """Check whether a quote appears in the transcript (exact or >=70% token overlap)."""
    nq = _norm_for_match(quote)
    if not nq:
        return False
    if nq in norm_transcript:
        return True
    q_tokens = [t for t in nq.split() if len(t) > 1]
    if not q_tokens:
        return False
    tx_tokens = set(norm_transcript.split())
    matched = sum(1 for t in q_tokens if t in tx_tokens)
    return (matched / len(q_tokens)) >= 0.70


def _filter_grounded_quotes(quotes: list[str], norm_transcript: str) -> tuple[list[str], int]:
    kept: list[str] = []
    dropped = 0
    for q in quotes:
        if _is_quote_grounded(q, norm_transcript):
            kept.append(q)
        else:
            dropped += 1
    return kept, dropped


def compute_customer_risk_score(result: CallAnalysisResult) -> RiskAssessment:
    """
    Deterministic, explainable rule-based Customer Risk Score (0-100).

    Explicitly NOT a predicted churn probability.
    """
    score = 0.0
    factors: list[str] = []

    # 1. Dissatisfaction component (0-30 pts)
    dissat_pts = round(max(0.0, (10.0 - result.sentiment.score) * 3.0), 1)
    if dissat_pts >= 3.0:
        score += dissat_pts
        factors.append(
            f"Customer dissatisfaction (satisfaction {result.sentiment.score:.1f}/10): +{int(round(dissat_pts))} pts"
        )

    # 2. Issue priority component (0-25 pts)
    prio_map = {"critical": 25, "high": 15, "medium": 5, "low": 0}
    prio_pts = prio_map.get(result.problem.priority, 0)
    if prio_pts > 0:
        score += prio_pts
        factors.append(f"{result.problem.priority.title()} issue priority: +{prio_pts} pts")

    # 3. Unresolved / escalated status (0-20 pts)
    if not result.resolution.resolved:
        score += 15
        factors.append(
            f"Issue not resolved ({result.resolution.resolution_type.replace('_', ' ')}): +15 pts"
        )
    if result.resolution.escalation_required:
        score += 5
        factors.append("Escalation required: +5 pts")

    # 4. Operational signals (0-35 pts)
    sig = result.operational_signals
    if sig.repeated_complaint:
        score += 15
        factors.append("Repeated complaint detected: +15 pts")
    if sig.missed_commitment:
        score += 10
        factors.append("Missed prior commitment detected: +10 pts")
    if sig.potential_sla_violation:
        score += 10
        factors.append("Potential SLA violation detected: +10 pts")

    # 5. Declining sentiment trajectory (+5 pts)
    if result.sentiment.trajectory == "declining":
        score += 5
        factors.append("Declining sentiment trajectory: +5 pts")

    final_score = max(0, min(100, int(round(score))))
    if final_score >= 75:
        level = "critical"
    elif final_score >= 50:
        level = "high"
    elif final_score >= 25:
        level = "medium"
    else:
        level = "low"

    if not factors:
        factors.append("No elevated risk rules triggered.")

    return RiskAssessment(score=final_score, level=level, factors=factors)


def validate_and_enrich_result(
    result: CallAnalysisResult,
    transcript: str,
    rubric: Optional[dict] = None,
    injection_detected: bool = False,
    redaction_flags: Optional[list[str]] = None,
) -> CallAnalysisResult:
    """
    Apply deterministic grounding, N/A agent enforcement, cross-field consistency,
    and rule-based risk assessment to a CallAnalysisResult.
    """
    warnings_list = list(result.consistency_warnings)
    low_conf = list(result.low_confidence_flags)

    def _add_low_conf(flag: str) -> None:
        if flag not in low_conf:
            low_conf.append(flag)

    def _add_warning(msg: str) -> None:
        if msg not in warnings_list:
            warnings_list.append(msg)

    if injection_detected:
        _add_warning("Potential prompt-injection pattern detected in transcript; treated strictly as data.")
        _add_low_conf("prompt_injection_detected")

    for rf in redaction_flags or []:
        _add_warning(f"Sensitive PII masked ({rf}) before analysis.")

    norm_tx = _norm_for_match(transcript)

    # 1. Evidence grounding verification
    total_dropped = 0
    result.sentiment.evidence, d1 = _filter_grounded_quotes(result.sentiment.evidence, norm_tx)
    result.agent_evaluation.evaluation_evidence, d2 = _filter_grounded_quotes(
        result.agent_evaluation.evaluation_evidence, norm_tx
    )
    result.problem.root_cause_evidence, d3 = _filter_grounded_quotes(
        result.problem.root_cause_evidence, norm_tx
    )
    result.operational_signals.signal_evidence, d4 = _filter_grounded_quotes(
        result.operational_signals.signal_evidence, norm_tx
    )
    total_dropped = d1 + d2 + d3 + d4
    if total_dropped > 0:
        _add_warning(f"Removed {total_dropped} ungrounded quote(s) not matched in transcript.")
        _add_low_conf("unverified_evidence")

    # 2. Never invent timestamps if raw transcript has none
    has_raw_timestamps = bool(_TIMESTAMP_RE.search(transcript))
    if not has_raw_timestamps:
        for turn in result.speakers:
            if turn.start_seconds is not None or turn.end_seconds is not None:
                turn.start_seconds = None
                turn.end_seconds = None
                _add_warning("Stripped ungrounded speaker timestamps not present in source transcript.")

    # 3. Root cause must be evidence-supported
    if result.problem.root_cause and not result.problem.root_cause_evidence:
        result.problem.root_cause = None
        _add_warning("Cleared unsupported root_cause lacking grounded transcript evidence.")
        _add_low_conf("root_cause")

    # 4. Enforce N/A when no agent speaks
    has_agent_turn = any(t.speaker == "agent" and t.text.strip() for t in result.speakers)
    if not has_agent_turn or not result.agent_evaluation.applicable:
        result.agent_evaluation.applicable = False
        result.agent_evaluation.empathy_score = None
        result.agent_evaluation.clarity_score = None
        result.agent_evaluation.resolution_effectiveness_score = None
        result.agent_evaluation.professionalism_score = None
        result.agent_evaluation.overall_score = None
        result.agent_evaluation.strengths = []
        result.agent_evaluation.areas_for_improvement = [
            "N/A — No agent speech detected in this transcript."
        ]
        result.agent_evaluation.evaluation_evidence = []
        _add_low_conf("agent_evaluation")
    else:
        # Deterministically compute weighted overall_score from the 4 rubric scores
        ag = result.agent_evaluation
        dims = [
            ("empathy", ag.empathy_score),
            ("clarity", ag.clarity_score),
            ("resolution_effectiveness", ag.resolution_effectiveness_score),
            ("professionalism", ag.professionalism_score),
        ]
        valid_dims = [(name, val) for name, val in dims if val is not None]
        if valid_dims:
            active_rubric = rubric or DEFAULT_RUBRIC
            weighted_sum = 0.0
            weight_total = 0.0
            for name, val in valid_dims:
                w = float(active_rubric.get(name, {}).get("weight", 0.25))
                weighted_sum += val * w
                weight_total += w
            if weight_total > 0:
                ag.overall_score = round(weighted_sum / weight_total, 1)

    # 5. Cross-field resolution consistency
    res = result.resolution
    if res.resolution_type == "escalated":
        res.escalation_required = True
    if res.resolved and res.resolution_type in ("unresolved", "escalated", "pending_follow_up"):
        res.resolved = False
        _add_warning(
            f"Adjusted resolved=False for consistency with resolution_type='{res.resolution_type}'."
        )
    if res.resolution_type == "fully_resolved" and not res.resolved:
        res.resolved = True
        _add_warning("Adjusted resolved=True for consistency with resolution_type='fully_resolved'.")
    if res.follow_up_actions and not res.follow_up_required:
        res.follow_up_required = True

    # 6. Cross-field sentiment consistency
    sent = result.sentiment
    if sent.overall == "positive" and sent.score < 5.5:
        sent.overall = "mixed" if sent.score >= 4.0 else "negative"
        _add_warning(f"Adjusted sentiment label to '{sent.overall}' to match score {sent.score:.1f}/10.")
    elif sent.overall == "negative" and sent.score >= 6.5:
        sent.overall = "mixed"
        _add_warning(f"Adjusted sentiment label to 'mixed' to match score {sent.score:.1f}/10.")

    # 7. Cap confidence when flags or warnings exist
    if low_conf or warnings_list:
        result.confidence_score = min(result.confidence_score, 0.75)

    result.low_confidence_flags = low_conf
    result.consistency_warnings = warnings_list
    result.risk_assessment = compute_customer_risk_score(result)
    return result
