"""
Sage backend — FastAPI application entry point.

Start with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import warnings

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers.analysis import make_analysis_router
from backend.routers.analytics import make_analytics_router
from backend.routers.calls import make_calls_router
from backend.routers.transcription import make_transcription_router
from backend.services.call_repository import JsonCallRepository
from backend.services.genai.analyzer import GenAIAnalyzer
from backend.services.genai.interface import AnalysisError, GenAIProvider
from backend.services.model_config import load_model_config
from backend.services.stt.interface import STTError, STTProvider

_model_cfg = load_model_config()


def _resolve_genai_provider_name() -> str:
    # Explicit env override wins over YAML; YAML wins over settings default.
    if "genai_provider" in settings.model_fields_set and settings.genai_provider:
        configured = settings.genai_provider.lower()
    else:
        configured = (
            _model_cfg.get("genai", {}).get("active") or settings.genai_provider
        ).lower()

    if configured == "auto":
        if settings.gemini_api_key:
            return "gemini"
        if settings.genai_api_key or settings.cohere_api_key:
            return "cohere"
        return "gemini"  # preferred default for clear missing-key messaging
    return configured


def _build_stt_provider() -> STTProvider:
    if "stt_provider" in settings.model_fields_set and settings.stt_provider:
        provider_name = settings.stt_provider.lower()
    else:
        provider_name = (_model_cfg.get("stt", {}).get("active") or settings.stt_provider).lower()

    if provider_name == "cohere":
        from backend.services.stt.cohere_stt import CohereSTTProvider
        return CohereSTTProvider()
    raise STTError(
        f"Unknown STT_PROVIDER '{provider_name}'. Currently supported: 'cohere'."
    )


def _build_genai_provider() -> tuple[GenAIProvider, int]:
    genai_cfg = _model_cfg.get("genai", {})
    provider_name = _resolve_genai_provider_name()
    provider_opts = genai_cfg.get("providers", {}).get(provider_name, {})
    rubric = _model_cfg.get("evaluation_rubric")
    retry_attempts = int(provider_opts.get("retry_attempts", 2))
    timeout_seconds = int(provider_opts.get("timeout_seconds", settings.analysis_timeout_seconds))

    if provider_name == "gemini":
        from backend.services.genai.gemini_genai import GeminiGenAIProvider
        model = (
            (settings.genai_model if "genai_model" in settings.model_fields_set and settings.genai_model else None)
            or (settings.gemini_model if "gemini_model" in settings.model_fields_set and settings.gemini_model else None)
            or provider_opts.get("model")
            or settings.gemini_model
        )
        return (
            GeminiGenAIProvider(
                model=model,
                temperature=provider_opts.get("temperature", 0.1),
                max_tokens=provider_opts.get("max_tokens", 4096),
                timeout_seconds=timeout_seconds,
                rubric=rubric,
            ),
            retry_attempts,
        )

    if provider_name == "cohere":
        from backend.services.genai.cohere_genai import CohereGenAIProvider
        model = (
            (settings.genai_model if "genai_model" in settings.model_fields_set and settings.genai_model else None)
            or (settings.cohere_genai_model if "cohere_genai_model" in settings.model_fields_set and settings.cohere_genai_model else None)
            or provider_opts.get("model")
            or settings.cohere_genai_model
        )
        return (
            CohereGenAIProvider(
                model=model,
                temperature=provider_opts.get("temperature", 0.1),
                max_tokens=provider_opts.get("max_tokens", 4096),
                timeout_seconds=timeout_seconds,
                rubric=rubric,
            ),
            retry_attempts,
        )

    raise AnalysisError(
        f"Unknown GENAI_PROVIDER '{provider_name}'. Supported: 'auto', 'gemini', 'cohere'."
    )


app = FastAPI(title="Sage Customer Support Intelligence API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

_call_repository = JsonCallRepository(settings.calls_dir)

_stt_error_msg: str | None = None
_stt_provider: STTProvider | None = None
try:
    _stt_provider = _build_stt_provider()
    app.include_router(make_transcription_router(_stt_provider), prefix="/api")
except STTError as _stt_err:
    _stt_error_msg = str(_stt_err)
    warnings.warn(f"Transcription endpoint degraded: {_stt_err}", stacklevel=1)
    _fallback_stt_router = APIRouter()

    @_fallback_stt_router.post("/transcribe")
    async def transcribe_unavailable() -> None:
        raise HTTPException(status_code=503, detail=_stt_error_msg)

    app.include_router(_fallback_stt_router, prefix="/api")

_genai_error_msg: str | None = None
_genai_provider: GenAIProvider | None = None
_fallback_provider: GenAIProvider | None = None
try:
    _genai_provider, _retry_attempts = _build_genai_provider()
    if (
        _resolve_genai_provider_name() == "gemini"
        and _genai_provider.provider_name == "gemini"
        and (settings.genai_api_key or settings.cohere_api_key)
        and (settings.genai_provider.lower() == "auto" or _model_cfg.get("genai", {}).get("active") == "auto")
    ):
        try:
            from backend.services.genai.cohere_genai import CohereGenAIProvider
            _cohere_opts = _model_cfg.get("genai", {}).get("providers", {}).get("cohere", {})
            _fallback_provider = CohereGenAIProvider(
                model=_cohere_opts.get("model", settings.cohere_genai_model),
                temperature=_cohere_opts.get("temperature", 0.1),
                max_tokens=_cohere_opts.get("max_tokens", 4096),
                rubric=_model_cfg.get("evaluation_rubric"),
            )
        except Exception:
            _fallback_provider = None
    _analyzer = GenAIAnalyzer(
        _genai_provider,
        max_retries=_retry_attempts,
        fallback_provider=_fallback_provider,
    )
    app.include_router(make_analysis_router(_analyzer, _call_repository), prefix="/api")
except AnalysisError as _genai_err:
    _genai_error_msg = str(_genai_err)
    warnings.warn(f"Analysis endpoint degraded: {_genai_err}", stacklevel=1)
    _fallback_genai_router = APIRouter()

    @_fallback_genai_router.post("/analyze")
    async def analyze_unavailable() -> None:
        raise HTTPException(status_code=503, detail=_genai_error_msg)

    app.include_router(_fallback_genai_router, prefix="/api")

app.include_router(make_calls_router(_call_repository), prefix="/api")
app.include_router(make_analytics_router(_call_repository), prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok" if (_stt_provider and _genai_provider) else "degraded",
        "version": "2.0.0",
        "stt_provider": settings.stt_provider,
        "stt_model": settings.stt_model,
        "stt_ready": _stt_provider is not None,
        "stt_error": _stt_error_msg,
        "genai_provider": _genai_provider.provider_name if _genai_provider else _resolve_genai_provider_name(),
        "genai_model": _genai_provider.model_name if _genai_provider else "unconfigured",
        "genai_ready": _genai_provider is not None,
        "genai_error": _genai_error_msg,
        "configured_keys": {
            "cohere": bool(settings.cohere_api_key),
            "gemini": bool(settings.gemini_api_key),
        },
    }


_frontend_dir = settings.project_root / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
