"""Unit tests for prompt_builder."""

from __future__ import annotations

from backend.services.genai.prompts.prompt_builder import build_analysis_prompt


def test_prompt_injects_transcript_and_metadata() -> None:
    sys_p, usr_p = build_analysis_prompt(
        transcript="Customer: My order is late.",
        call_id="CALL-99",
        language="en",
    )
    assert "Customer: My order is late." in usr_p
    assert "CALL-99" in usr_p
    assert "Expected Language Hint: en" in usr_p
    assert "<UNTRUSTED_TRANSCRIPT>" in usr_p
    assert "operational_signals" in sys_p
    assert "agent_evaluation" in sys_p


def test_prompt_includes_custom_rubric() -> None:
    custom_rubric = {
        "speed": {"weight": 0.5, "description": "How fast the agent responded."}
    }
    sys_p, _ = build_analysis_prompt(
        transcript="Hello",
        call_id="CALL-1",
        rubric=custom_rubric,
    )
    assert "Speed (0-10, weight=50%): How fast the agent responded." in sys_p
