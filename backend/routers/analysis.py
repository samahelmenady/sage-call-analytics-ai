"""
POST /api/analyze

Accepts a call transcript, runs GenAI analysis, applies deterministic grounding/risk rules,
persists the sanitized CallAnalysisResult, and returns validated JSON.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.schemas.call_analysis import CallAnalysisResult
from backend.services.call_repository import CallRepository
from backend.services.genai.analyzer import GenAIAnalyzer
from backend.services.genai.interface import AnalysisError, NonRetryableAnalysisError
from backend.services.security import sanitize_error_message, sanitize_transcript_for_llm


class CallMetadata(BaseModel):
    call_id: Optional[str] = None
    agent_id: Optional[str] = None
    queue: Optional[str] = None
    duration_seconds: Optional[int] = None
    filename: Optional[str] = None


class AnalyzeRequest(BaseModel):
    transcript: str
    language: str = "ar"
    source: Literal["audio", "text"] = "text"
    call_metadata: Optional[CallMetadata] = None


def make_analysis_router(
    analyzer: GenAIAnalyzer,
    repository: CallRepository,
) -> APIRouter:
    router = APIRouter()

    @router.post("/analyze", response_model=CallAnalysisResult)
    async def analyze(req: AnalyzeRequest) -> CallAnalysisResult:
        text = req.transcript.strip()
        if not text:
            raise HTTPException(status_code=400, detail="transcript must not be empty.")
        if len(text.split()) < 3:
            raise HTTPException(
                status_code=400,
                detail="transcript is too short (minimum 3 words required).",
            )
        if len(text) > settings.max_transcript_chars:
            raise HTTPException(
                status_code=400,
                detail=f"transcript exceeds {settings.max_transcript_chars:,} character limit.",
            )

        call_id = (
            req.call_metadata.call_id.strip()
            if req.call_metadata and req.call_metadata.call_id and req.call_metadata.call_id.strip()
            else f"CALL-{uuid.uuid4().hex[:8].upper()}"
        )

        try:
            result = await analyzer.analyze(
                transcript=text,
                call_id=call_id,
                language=req.language,
            )
        except NonRetryableAnalysisError as exc:
            raise HTTPException(status_code=503, detail=sanitize_error_message(str(exc))) from exc
        except AnalysisError as exc:
            raise HTTPException(status_code=502, detail=sanitize_error_message(str(exc))) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=sanitize_error_message(str(exc))) from exc

        result.source = req.source
        sanitized_tx, _, _ = sanitize_transcript_for_llm(text)
        result.raw_transcript = sanitized_tx
        if req.call_metadata:
            meta_dict = req.call_metadata.model_dump(exclude_none=True, exclude={"call_id"})
            if meta_dict:
                result.call_metadata = meta_dict

        await repository.save(result)
        return result

    return router
