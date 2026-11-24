"""
Security, PII redaction, prompt-injection defense, and error sanitization helpers.
"""

from __future__ import annotations

import re

# Match 13-19 digit payment card PANs (optionally space/dash separated)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
# Match common API keys / Bearer tokens
_SECRET_RE = re.compile(
    r"(?i)(?:bearer\s+[a-z0-9._\-]{12,}|AIza[0-9A-Za-z\-_]{20,}|sk-[0-9A-Za-z\-_]{16,}|[a-zA-Z0-9]{32,})"
)
# Match email addresses
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Match Egyptian 14-digit national IDs
_EG_NID_RE = re.compile(r"(?<!\d)[23]\d{13}(?!\d)")
# Match CVV phrases
_CVV_RE = re.compile(r"(?i)\b(?:cvv|cvc|الرقم السري|سي في في)\s*[:#]?\s*\d{3,4}\b")

# Control chars (excluding \n, \r, \t)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"),
    re.compile(r"(?i)disregard\s+(?:the\s+)?system\s+prompt"),
    re.compile(r"(?i)you\s+are\s+now\s+(?:a|an)\b"),
    re.compile(r"(?i)override\s+(?:json|schema|output)"),
    re.compile(r"(?i)<\s*/?\s*UNTRUSTED_TRANSCRIPT\s*>"),
    re.compile(r"(?i)تجاهل\s+(?:كل\s+)?التعليمات\s+السابقة"),
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Redact sensitive payment/identity data before sending to external LLMs or storing."""
    flags: list[str] = []
    cleaned = text

    def _sub(pattern: re.Pattern[str], replacement: str, label: str, src: str) -> str:
        updated, count = pattern.subn(replacement, src)
        if count > 0 and label not in flags:
            flags.append(label)
        return updated

    cleaned = _sub(_CARD_RE, "[REDACTED_CARD]", "card_number_redacted", cleaned)
    cleaned = _sub(_CVV_RE, "[REDACTED_CVV]", "cvv_redacted", cleaned)
    cleaned = _sub(_EG_NID_RE, "[REDACTED_NATIONAL_ID]", "national_id_redacted", cleaned)
    cleaned = _sub(_EMAIL_RE, "[REDACTED_EMAIL]", "email_redacted", cleaned)
    return cleaned, flags


def detect_prompt_injection(text: str) -> bool:
    """Detect common prompt-injection attempts embedded inside transcripts."""
    return any(pat.search(text) for pat in _INJECTION_PATTERNS)


def sanitize_transcript_for_llm(transcript: str) -> tuple[str, bool, list[str]]:
    """
    Strip control characters, neutralize delimiter breakout tags, and redact sensitive PII.

    Returns (sanitized_text, injection_detected, redaction_flags).
    """
    cleaned = _CTRL_RE.sub(" ", transcript).strip()
    injection_detected = detect_prompt_injection(cleaned)
    cleaned = re.sub(r"(?i)<\s*/?\s*UNTRUSTED_TRANSCRIPT\s*>", "[TAG_REMOVED]", cleaned)
    cleaned, redaction_flags = redact_pii(cleaned)
    return cleaned, injection_detected, redaction_flags


def sanitize_error_message(message: str) -> str:
    """Prevent API keys or Bearer tokens from leaking in HTTP error responses."""
    return _SECRET_RE.sub("[REDACTED_SECRET]", str(message))
