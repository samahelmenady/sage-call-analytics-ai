"""
Call record storage abstraction and JSON-file implementation.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.genai.postprocessor import compute_customer_risk_score


class CallRepository(ABC):
    @abstractmethod
    async def save(self, result: CallAnalysisResult) -> None: ...

    @abstractmethod
    async def get(self, call_id: str) -> Optional[CallAnalysisResult]: ...

    @abstractmethod
    async def list_all(self, filters: Optional[dict] = None) -> list[CallAnalysisResult]: ...

    @abstractmethod
    async def delete(self, call_id: str) -> bool: ...


def _ensure_risk(record: CallAnalysisResult) -> CallAnalysisResult:
    if record.risk_assessment is None:
        record.risk_assessment = compute_customer_risk_score(record)
    return record


def _matches_search(record: CallAnalysisResult, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join(
        [
            record.call_id,
            record.problem.summary,
            record.call_summary,
            record.raw_transcript or "",
            " ".join(record.problem.keywords),
            " ".join(record.problem.pain_points),
        ]
    ).lower()
    return q in haystack


class JsonCallRepository(CallRepository):
    """Stores one JSON file per call in `calls_dir`."""

    def __init__(self, calls_dir: Path) -> None:
        self._dir = calls_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path_for(self, call_id: str) -> Path:
        safe_id = "".join(c for c in call_id if c.isalnum() or c in "-_")
        return self._dir / f"{safe_id}.json"

    async def save(self, result: CallAnalysisResult) -> None:
        _ensure_risk(result)
        path = self._path_for(result.call_id)
        payload = result.model_dump_json(indent=2)
        async with self._lock:
            path.write_text(payload, encoding="utf-8")

    async def get(self, call_id: str) -> Optional[CallAnalysisResult]:
        path = self._path_for(call_id)
        if not path.is_file():
            return None
        record = CallAnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
        return _ensure_risk(record)

    async def list_all(self, filters: Optional[dict] = None) -> list[CallAnalysisResult]:
        records: list[CallAnalysisResult] = []
        for file_path in self._dir.glob("*.json"):
            try:
                rec = CallAnalysisResult.model_validate_json(
                    file_path.read_text(encoding="utf-8")
                )
                records.append(_ensure_risk(rec))
            except Exception:
                continue

        filters = filters or {}
        filtered: list[CallAnalysisResult] = []
        search_q = filters.get("search") or ""
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")

        for r in records:
            if search_q and not _matches_search(r, search_q):
                continue
            if filters.get("sentiment") and r.sentiment.overall != filters["sentiment"]:
                continue
            if filters.get("category") and r.problem.category != filters["category"]:
                continue
            if filters.get("priority") and r.problem.priority != filters["priority"]:
                continue
            if filters.get("resolved") is not None and r.resolution.resolved != filters["resolved"]:
                continue
            if filters.get("risk_level") and (not r.risk_assessment or r.risk_assessment.level != filters["risk_level"]):
                continue
            if filters.get("sla_violation") is not None and r.operational_signals.potential_sla_violation != filters["sla_violation"]:
                continue
            if filters.get("escalation_required") is not None and r.resolution.escalation_required != filters["escalation_required"]:
                continue
            date_part = (r.analyzed_at or "")[:10]
            if date_from and date_part < date_from:
                continue
            if date_to and date_part > date_to:
                continue
            filtered.append(r)

        sort_by = filters.get("sort_by") or "date_desc"
        if sort_by == "date_asc":
            filtered.sort(key=lambda r: r.analyzed_at)
        elif sort_by == "risk_desc":
            filtered.sort(key=lambda r: (r.risk_assessment.score if r.risk_assessment else 0), reverse=True)
        elif sort_by == "sentiment_asc":
            filtered.sort(key=lambda r: r.sentiment.score)
        elif sort_by == "agent_desc":
            filtered.sort(
                key=lambda r: (r.agent_evaluation.overall_score if r.agent_evaluation.overall_score is not None else -1.0),
                reverse=True,
            )
        else:
            filtered.sort(key=lambda r: r.analyzed_at, reverse=True)

        return filtered

    async def delete(self, call_id: str) -> bool:
        path = self._path_for(call_id)
        async with self._lock:
            if not path.is_file():
                return False
            path.unlink()
            return True
