"""
Prompt builder that injects sanitized transcript, metadata, compact schema, and rubric.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from backend.schemas.call_analysis import LLMCallAnalysisSchema
from backend.services.genai.prompts.system_prompt import (
    DEFAULT_RUBRIC,
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)


def _format_rubric(rubric: Optional[dict] = None) -> str:
    active_rubric = rubric or DEFAULT_RUBRIC
    lines: list[str] = []
    for name, cfg in active_rubric.items():
        label = name.replace("_", " ").title()
        weight = cfg.get("weight", 0.25)
        desc = cfg.get("description", "")
        lines.append(f"- {label} (0-10, weight={weight:.0%}): {desc}")
    return "\n".join(lines)


def _strip_schema_bloat(node: Any) -> Any:
    """Remove redundant title/description keys from JSON Schema to cut prompt token cost."""
    if isinstance(node, dict):
        return {
            k: _strip_schema_bloat(v)
            for k, v in node.items()
            if k not in ("title",)
        }
    if isinstance(node, list):
        return [_strip_schema_bloat(item) for item in node]
    return node


@lru_cache(maxsize=1)
def _compact_schema_json() -> str:
    compact = _strip_schema_bloat(LLMCallAnalysisSchema.model_json_schema())
    return json.dumps(compact, separators=(",", ":"))


def build_analysis_prompt(
    transcript: str,
    call_id: str,
    language: str = "ar",
    rubric: Optional[dict] = None,
    analyzed_at: Optional[str] = None,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the GenAI provider."""
    timestamp = analyzed_at or datetime.now(timezone.utc).isoformat()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rubric_section=_format_rubric(rubric),
        schema_json=_compact_schema_json(),
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        call_id=call_id,
        analyzed_at=timestamp,
        language=language,
        transcript=transcript,
    )
    return system_prompt, user_prompt
