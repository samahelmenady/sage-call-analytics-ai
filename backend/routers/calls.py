"""
GET /api/calls, GET /api/calls/{call_id}, DELETE /api/calls/{call_id}
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.call_repository import CallRepository


def make_calls_router(repository: CallRepository) -> APIRouter:
    router = APIRouter()

    @router.get("/calls", response_model=list[CallAnalysisResult])
    async def list_calls(
        response: Response,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        search: Optional[str] = None,
        sentiment: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        resolved: Optional[bool] = None,
        risk_level: Optional[str] = None,
        sla_violation: Optional[bool] = None,
        escalation_required: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = Query("date_desc"),
    ) -> list[CallAnalysisResult]:
        filters = {
            "search": search,
            "sentiment": sentiment,
            "category": category,
            "priority": priority,
            "resolved": resolved,
            "risk_level": risk_level,
            "sla_violation": sla_violation,
            "escalation_required": escalation_required,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
        }
        all_calls = await repository.list_all(filters=filters)
        response.headers["X-Total-Count"] = str(len(all_calls))
        start = (page - 1) * limit
        return all_calls[start : start + limit]

    @router.get("/calls/{call_id}", response_model=CallAnalysisResult)
    async def get_call(call_id: str) -> CallAnalysisResult:
        record = await repository.get(call_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found.")
        return record

    @router.delete("/calls/{call_id}")
    async def delete_call(call_id: str) -> dict:
        deleted = await repository.delete(call_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Call '{call_id}' not found.")
        return {"deleted": True, "call_id": call_id}

    return router
