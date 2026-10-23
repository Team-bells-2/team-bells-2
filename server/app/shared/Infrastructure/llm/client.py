import hashlib
import json
from collections import OrderedDict
from functools import lru_cache
from typing import Any

import httpx

from app.shared.env import settings


class LLMError(Exception):
    """The provider could not be reached or returned something that is not a JSON object."""


class LLMClient:
    """The one way the app calls a language model (NFR-8): timeout, max_tokens,
    an in-memory cache of identical requests and a call counter."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        cache_size: int = 256,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.cache_size = cache_size
        self.calls = 0
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def complete_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        user_content = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        key = hashlib.sha256(f"{self.model}\n{system_prompt}\n{user_content}".encode()).hexdigest()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        if not self.api_key:
            raise LLMError("LLM is not configured. Set LLM_API_KEY.")
        self.calls += 1
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0,
                    "max_tokens": self.max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except httpx.HTTPError as error:
            raise LLMError(f"LLM request failed: {type(error).__name__}") from error
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise LLMError("LLM returned a malformed response.") from error
        if not isinstance(parsed, dict):
            raise LLMError("LLM returned JSON that is not an object.")

        result: dict[str, Any] = parsed  # pyright: ignore[reportUnknownVariableType]
        self._cache[key] = result
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return result


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
