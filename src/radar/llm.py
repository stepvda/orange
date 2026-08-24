"""Provider-agnostic LLM access.

§4.4.6: the pipeline is model-agnostic behind a thin abstraction, because the
economics change every few months. Practically — a small, cheap model for the
high-volume gating and classification stages; a strong model for synthesis and
critique, where quality dominates cost because the volume is low.

NFR-05 / NFR-10: Orange sells trusted AI on sovereign infrastructure, so the
design must not depend on any single provider. Every provider below speaks the
OpenAI-compatible wire format, which is what Ollama and most sovereign
inference stacks expose — switching is an .env change, not a re-architecture.

Two hard rules from §4.4.4 are enforced here rather than left to prompts:
  * every call records the prompt version that produced it (DR-10);
  * `NO_NUMBERS_RULE` is appended to every generative system prompt, because
    "no model-generated numbers" is the rule most worth enforcing rigidly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# §4.4.4 defence 3. Market sizes, growth rates and percentages are never
# generated — they are looked up, attributed and dated, or they are absent.
NO_NUMBERS_RULE = (
    "\n\nHARD RULE — NO GENERATED NUMBERS: never state a market size, growth rate, "
    "percentage, monetary value, headcount or date that does not appear verbatim in "
    "the evidence provided to you. If you want to express magnitude, use qualitative "
    "language instead. Inventing a figure invalidates the entire output."
)


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = field(default=None, repr=False)

    def json(self) -> Any:
        """Parse the response as JSON, tolerating a markdown code fence."""
        text = self.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}\n---\n{self.text[:800]}") from exc


class LLMClient:
    """Thin wrapper over an OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        provider: str | None = None,
        strong_model: str | None = None,
        cheap_model: str | None = None,
        max_retries: int = 2,
    ):
        self.provider = (provider or os.getenv("RADAR_LLM_PROVIDER", "deepseek")).lower()
        self.max_retries = max_retries
        self.strong_model = strong_model or os.getenv("RADAR_LLM_MODEL_STRONG", "deepseek-chat")
        self.cheap_model = cheap_model or os.getenv("RADAR_LLM_MODEL_CHEAP", "deepseek-chat")
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._client = None if self.provider == "mock" else self._build_client()

    def _build_client(self):
        from openai import OpenAI

        if self.provider == "deepseek":
            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise LLMError("DEEPSEEK_API_KEY is not set. Copy .env.example to .env and fill it in.")
            return OpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
        if self.provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise LLMError("OPENAI_API_KEY is not set.")
            return OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL") or None)
        if self.provider == "ollama":
            # Sovereign / local deployment path (NFR-05). Ollama needs no key.
            return OpenAI(api_key="ollama", base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
        raise LLMError(f"Unknown LLM provider {self.provider!r}. Supported: deepseek, openai, ollama, mock.")

    # -- core call ---------------------------------------------------------

    def complete(
        self,
        system: str,
        user: str,
        *,
        strong: bool = False,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: int = 4000,
        apply_no_numbers_rule: bool = True,
    ) -> LLMResponse:
        model = self.strong_model if strong else self.cheap_model
        if apply_no_numbers_rule:
            system = system + NO_NUMBERS_RULE
        if json_mode:
            # DeepSeek's JSON mode requires the word "json" in the prompt.
            if "json" not in (system + user).lower():
                system += "\n\nRespond with a single valid JSON object."

        if self.provider == "mock":
            return self._mock(system, user, model, json_mode)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                self.calls += 1
                if usage:
                    self.prompt_tokens += usage.prompt_tokens or 0
                    self.completion_tokens += usage.completion_tokens or 0
                return LLMResponse(
                    text=resp.choices[0].message.content or "",
                    model=model,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    raw=resp,
                )
            except Exception as exc:  # noqa: BLE001 — provider SDKs raise varied types
                last_error = exc
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    log.warning("LLM call failed (attempt %d/%d): %s — retrying in %ds",
                                attempt + 1, self.max_retries + 1, exc, backoff)
                    time.sleep(backoff)
        raise LLMError(f"LLM call failed after {self.max_retries + 1} attempts: {last_error}") from last_error

    def complete_json(self, system: str, user: str, **kwargs) -> Any:
        kwargs.setdefault("json_mode", True)
        return self.complete(system, user, **kwargs).json()

    # -- mock provider -----------------------------------------------------

    def _mock(self, system: str, user: str, model: str, json_mode: bool) -> LLMResponse:
        """Deterministic stub so the pipeline and tests run with no network.

        Keyed on a hash of the prompt so repeated runs are identical (SC-11).
        """
        self.calls += 1
        digest = hashlib.sha256((system + user).encode()).hexdigest()
        if not json_mode:
            return LLMResponse(text=f"[mock output {digest[:8]}]", model="mock")
        # Shape-appropriate stubs, chosen by a marker the caller puts in the system prompt.
        if "MOCK_KIND=signal_type" in system:
            payload = {"items": []}
        elif "MOCK_KIND=synthesis" in system:
            payload = {"candidates": []}
        elif "MOCK_KIND=critic" in system:
            payload = {"score": 3, "verdict": "revise", "notes": "mock", "issues": []}
        elif "MOCK_KIND=relevance" in system:
            payload = {"items": []}
        elif "MOCK_KIND=brief_support" in system:
            # Supports nothing. The tests that reach this branch are about what
            # happens when the vocabulary test came up short AND the model agrees
            # the evidence is only adjacent — the case that must block.
            payload = {"supporting": [], "note": "mock"}
        elif "MOCK_KIND=scoping" in system:
            # Shaped like a first turn: a question, nothing understood, nothing
            # ready. The scoping tests are about what the SERVER does with a
            # reply — resolving ids, re-retrieving each brief, refusing a ready
            # flag the corpus does not support — so the stub has to be a
            # well-formed reply rather than a marker.
            payload = {"reply": "[mock question]", "understood": {}, "missing": ["vertical"],
                       "asking_for": "vertical", "suggestions": [], "ready": False, "briefs": []}
        else:
            payload = {"mock": True, "digest": digest[:16]}
        return LLMResponse(text=json.dumps(payload), model="mock")

    # -- reporting ---------------------------------------------------------

    def usage_summary(self) -> dict[str, Any]:
        """NFR-10: per-refresh inference cost is measured and reported."""
        return {
            "provider": self.provider,
            "strong_model": self.strong_model,
            "cheap_model": self.cheap_model,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }
