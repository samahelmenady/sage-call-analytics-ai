"""
GET /api/analytics

Aggregates stored call records into accurate management KPIs,
strictly excluding N/A (null) agent evaluations from agent averages.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter

from backend.services.call_repository import CallRepository
from backend.services.genai.postprocessor import compute_customer_risk_score


def _mean_non_null(values: list[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def make_analytics_router(repository: CallRepository) -> APIRouter:
    router = APIRouter()

    @router.get("/analytics")
    async def get_analytics() -> dict:
        calls = await repository.list_all()
        total = len(calls)

        if total == 0:
            return {
                "total_calls": 0,
                "evaluated_agent_calls": 0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0},
                "avg_satisfaction_score": 0.0,
                "category_breakdown": {},
                "priority_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "risk_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "avg_risk_score": 0.0,
                "high_risk_calls": 0,
                "sla_violation_count": 0,
                "repeated_complaint_count": 0,
                "escalation_count": 0,
                "emotion_breakdown": {},
                "resolution_rate": 0.0,
                "resolution_breakdown": {
                    "fully_resolved": 0,
                    "partially_resolved": 0,
                    "escalated": 0,
                    "pending_follow_up": 0,
                    "unresolved": 0,
                },
                "avg_agent_scores": {
                    "empathy": None,
                    "clarity": None,
                    "resolution_effectiveness": None,
                    "professionalism": None,
                    "overall": None,
                },
                "top_issues": [],
                "daily_trends": [],
            }

        sentiment_counts = Counter(c.sentiment.overall for c in calls)
        category_counts = Counter(c.problem.category for c in calls)
        priority_counts = Counter(c.problem.priority for c in calls)
        resolution_counts = Counter(c.resolution.resolution_type for c in calls)
        emotion_counts = Counter(
            emo.strip().lower() for c in calls for emo in c.sentiment.emotions if emo.strip()
        )

        risks = [c.risk_assessment or compute_customer_risk_score(c) for c in calls]
        risk_counts = Counter(r.level for r in risks)
        avg_risk = round(sum(r.score for r in risks) / total, 1)
        high_risk_calls = risk_counts.get("high", 0) + risk_counts.get("critical", 0)

        resolved_count = sum(1 for c in calls if c.resolution.resolved)
        sla_count = sum(1 for c in calls if c.operational_signals.potential_sla_violation)
        repeated_count = sum(1 for c in calls if c.operational_signals.repeated_complaint)
        escalation_count = sum(1 for c in calls if c.resolution.escalation_required)

        avg_sat = round(sum(c.sentiment.score for c in calls) / total, 2)

        applicable_agent_evals = [
            c.agent_evaluation for c in calls if c.agent_evaluation.applicable
        ]
        avg_agent = {
            "empathy": _mean_non_null([a.empathy_score for a in applicable_agent_evals]),
            "clarity": _mean_non_null([a.clarity_score for a in applicable_agent_evals]),
            "resolution_effectiveness": _mean_non_null(
                [a.resolution_effectiveness_score for a in applicable_agent_evals]
            ),
            "professionalism": _mean_non_null(
                [a.professionalism_score for a in applicable_agent_evals]
            ),
            "overall": _mean_non_null([a.overall_score for a in applicable_agent_evals]),
        }

        # Chronological daily trend buckets
        buckets: dict[str, list] = defaultdict(list)
        for c, r in zip(calls, risks):
            day = (c.analyzed_at or "")[:10] or "unknown"
            buckets[day].append((c, r))

        daily_trends = []
        for day in sorted(buckets.keys()):
            items = buckets[day]
            n_day = len(items)
            daily_trends.append(
                {
                    "date": day,
                    "calls": n_day,
                    "avg_satisfaction": round(sum(c.sentiment.score for c, _ in items) / n_day, 2),
                    "avg_risk_score": round(sum(r.score for _, r in items) / n_day, 1),
                    "resolution_rate": round(
                        sum(1 for c, _ in items if c.resolution.resolved) / n_day, 3
                    ),
                }
            )

        top_issues = [cat for cat, _ in category_counts.most_common(5)]

        return {
            "total_calls": total,
            "evaluated_agent_calls": len(applicable_agent_evals),
            "sentiment_distribution": {
                "positive": sentiment_counts.get("positive", 0),
                "neutral": sentiment_counts.get("neutral", 0),
                "negative": sentiment_counts.get("negative", 0),
                "mixed": sentiment_counts.get("mixed", 0),
            },
            "avg_satisfaction_score": avg_sat,
            "category_breakdown": dict(category_counts),
            "priority_breakdown": {
                "critical": priority_counts.get("critical", 0),
                "high": priority_counts.get("high", 0),
                "medium": priority_counts.get("medium", 0),
                "low": priority_counts.get("low", 0),
            },
            "risk_distribution": {
                "critical": risk_counts.get("critical", 0),
                "high": risk_counts.get("high", 0),
                "medium": risk_counts.get("medium", 0),
                "low": risk_counts.get("low", 0),
            },
            "avg_risk_score": avg_risk,
            "high_risk_calls": high_risk_calls,
            "sla_violation_count": sla_count,
            "repeated_complaint_count": repeated_count,
            "escalation_count": escalation_count,
            "emotion_breakdown": dict(emotion_counts),
            "resolution_rate": round(resolved_count / total, 3),
            "resolution_breakdown": {
                "fully_resolved": resolution_counts.get("fully_resolved", 0),
                "partially_resolved": resolution_counts.get("partially_resolved", 0),
                "escalated": resolution_counts.get("escalated", 0),
                "pending_follow_up": resolution_counts.get("pending_follow_up", 0),
                "unresolved": resolution_counts.get("unresolved", 0),
            },
            "avg_agent_scores": avg_agent,
            "top_issues": top_issues,
            "daily_trends": daily_trends,
        }

    return router
