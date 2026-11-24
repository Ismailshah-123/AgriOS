"""Replaceable model providers for knowledge: embeddings and chat LLM.

Embeddings: "none" (FTS only) | "fastembed" (local ONNX, CPU; default model is the
multilingual MiniLM so Urdu questions can match English passages).
LLM: any OpenAI-compatible chat-completions endpoint. Presets: groq, xai, ollama;
"openai_compatible" takes LLM_BASE_URL + LLM_MODEL. "none" disables generation entirely and
the system answers extractively (hard rule 8). The LLM is an integration, not our model.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from app.core.config import Settings

logger = logging.getLogger("agrios.knowledge")

LLM_PRESETS: dict[str, tuple[str, str]] = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "xai": ("https://api.x.ai/v1", "grok-3-mini"),
    "ollama": ("http://127.0.0.1:11434/v1", "llama3"),
}


# ------------------------------------------------------------------------- embeddings
class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...  # (n, d), L2-normalised


class FastEmbedder:
    def __init__(self, model_name: str, cache_dir: str) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir, threads=2)
        self._lock = threading.Lock()  # ONNX session shared between request threads

    def embed(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            vecs = np.asarray(list(self._model.embed(texts, batch_size=16)), dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.maximum(norms, 1e-12)


_embedders: dict[str, Embedder] = {}
_embed_lock = threading.Lock()


def get_embedder(settings: Settings) -> Embedder | None:
    """Lazily loaded singleton; None when disabled or the model cannot be loaded (logged —
    retrieval then falls back to full-text search and the response says so)."""
    if settings.embedding_provider == "none":
        return None
    key = f"{settings.embedding_provider}:{settings.embedding_model}"
    with _embed_lock:
        if key not in _embedders:
            try:
                settings.embedding_cache_path.mkdir(parents=True, exist_ok=True)
                _embedders[key] = FastEmbedder(
                    settings.embedding_model, str(settings.embedding_cache_path)
                )
            except Exception:
                logger.exception("embedding_model_unavailable")
                return None
        return _embedders[key]


def set_embedder_for_tests(settings: Settings, embedder: Embedder | None) -> None:
    key = f"{settings.embedding_provider}:{settings.embedding_model}"
    if embedder is None:
        _embedders.pop(key, None)
    else:
        _embedders[key] = embedder


# ------------------------------------------------------------------------------- LLM
class LLMError(RuntimeError):
    """Stable code in args[0]: llm_disabled | llm_timeout | llm_http_<status> | llm_bad_response."""


@dataclass(frozen=True)
class LLMReply:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


class ChatLLM(Protocol):
    provider: str
    model: str

    def chat(
        self, messages: list[dict[str, Any]], *, max_tokens: int, json_mode: bool = False
    ) -> LLMReply: ...


class _RateLimited(Exception):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after


class OpenAICompatibleLLM:
    def __init__(
        self,
        provider: str,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_s: float,
        fallback: str | None = None,
    ) -> None:
        self.provider, self.model, self.fallback = provider, model, fallback
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._timeout = timeout_s

    def chat(
        self, messages: list[dict[str, Any]], *, max_tokens: int, json_mode: bool = False
    ) -> LLMReply:
        """One retry after a short Retry-After on HTTP 429, then the fallback model (free tiers
        limit tokens per minute per model). Any other failure raises LLMError."""
        t0 = time.perf_counter()
        models = [self.model, *([self.fallback] if self.fallback else [])]
        last = "llm_unreachable"
        for model in models:
            for attempt in range(2):
                try:
                    data = self._post(model, messages, max_tokens, json_mode)
                    return self._reply(data, model, t0)
                except _RateLimited as rl:
                    last = "llm_http_429"
                    if attempt == 0 and rl.retry_after <= 8:
                        time.sleep(rl.retry_after)
                        continue
                    break
        raise LLMError(last)

    def _post(
        self, model: str, messages: list[dict[str, Any]], max_tokens: int, json_mode: bool
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # fewer hidden reasoning tokens
        headers = {"Content-Type": "application/json", "User-Agent": "agrios-knowledge/1"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        req = urllib.request.Request(  # noqa: S310 - URL comes from settings, not users
            self._url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                return json.load(resp)  # type: ignore[no-any-return]
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                try:
                    wait = float(exc.headers.get("retry-after") or 30)
                except ValueError:
                    wait = 30.0
                raise _RateLimited(wait) from None
            raise LLMError(f"llm_http_{exc.code}") from None  # body may echo the request
        except TimeoutError:
            raise LLMError("llm_timeout") from None
        except (urllib.error.URLError, OSError):
            raise LLMError("llm_unreachable") from None

    def _reply(self, data: dict[str, Any], model: str, t0: float) -> LLMReply:
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("llm_bad_response") from None
        usage = data.get("usage") or {}
        return LLMReply(
            text=text.strip(),
            provider=self.provider,
            model=data.get("model") or model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )


_test_llm: ChatLLM | None = None
_test_llm_set = False


def set_llm_for_tests(llm: ChatLLM | None, active: bool = True) -> None:
    global _test_llm, _test_llm_set
    _test_llm, _test_llm_set = llm, active


def get_llm(settings: Settings) -> ChatLLM | None:
    if _test_llm_set:
        return _test_llm
    if settings.llm_provider == "none":
        return None
    preset = LLM_PRESETS.get(settings.llm_provider)
    base = settings.llm_base_url or (preset[0] if preset else None)
    model = settings.llm_model or (preset[1] if preset else None)
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if not base or not model or (settings.llm_provider in ("groq", "xai") and not key):
        return None  # misconfigured: behave as disabled (status endpoint reports why)
    fallback = settings.llm_fallback_model or (
        "openai/gpt-oss-20b" if settings.llm_provider == "groq" else None
    )
    return OpenAICompatibleLLM(
        settings.llm_provider, base, model, key, settings.llm_timeout_s, fallback
    )


VISION_PRESETS = {"groq": "qwen/qwen3.8-27b"}


def get_vision_llm(settings: Settings) -> ChatLLM | None:
    """Image-capable chat model (Crop Doctor assistant). None when not configured."""
    if _test_llm_set:
        return _test_llm
    base_llm = get_llm(settings)
    model = settings.llm_vision_model or VISION_PRESETS.get(settings.llm_provider)
    if base_llm is None or not model:
        return None
    preset = LLM_PRESETS.get(settings.llm_provider)
    base = settings.llm_base_url or (preset[0] if preset else "")
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return OpenAICompatibleLLM(settings.llm_provider, base, model, key, settings.llm_timeout_s)


def provider_status(settings: Settings) -> dict[str, Any]:
    """Configuration summary for the UI. Never includes keys or URLs with credentials."""
    llm = get_llm(settings)
    reason = None
    if llm is None and settings.llm_provider != "none":
        reason = "missing API key, base URL or model"
    return {
        "llm": {
            "provider": settings.llm_provider,
            "model": llm.model if llm else None,
            "enabled": llm is not None,
            "reason": reason,
            "external": settings.llm_provider in ("groq", "xai", "openai_compatible"),
        },
        "vision": {
            "model": settings.llm_vision_model or VISION_PRESETS.get(settings.llm_provider),
            "enabled": llm is not None
            and bool(settings.llm_vision_model or VISION_PRESETS.get(settings.llm_provider)),
        },
        "embeddings": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model if settings.embedding_provider != "none" else None,
            "enabled": settings.embedding_provider != "none",
        },
    }
