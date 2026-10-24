import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from openai import OpenAI, OpenAIError, RateLimitError
from openai.types.chat import ChatCompletion

from app.shared.env import settings


class LLMError(Exception):
    """The provider could not be reached or returned something that is not a JSON object."""


class LLMClient:
    """The one way the app calls a language model (NFR-8): timeout, max_tokens, an in-memory cache of
    identical requests, a call counter, and one retry when the provider rate-limits (HTTP 429, BR-A6).

    Requests go through the OpenAI SDK (any OpenAI-compatible provider at LLM_BASE_URL). The SDK's own
    retries are off (max_retries=0) so that the single, capped rate-limit retry below is the only one.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        rate_limit_default_wait_seconds: float,
        rate_limit_max_wait_seconds: float,
        cache_size: int = 256,
        sleep: Callable[[float], None] = time.sleep,
        openai_client: OpenAI | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.rate_limit_default_wait_seconds = rate_limit_default_wait_seconds
        self.rate_limit_max_wait_seconds = rate_limit_max_wait_seconds
        self.cache_size = cache_size
        self.sleep = sleep
        self.calls = 0
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        # Built on first use: the SDK refuses an empty key, and the app must still start without one.
        self._openai = openai_client

    def complete_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        user_content = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        key = hashlib.sha256(f"{self.model}\n{system_prompt}\n{user_content}".encode()).hexdigest()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        if not self.api_key:
            raise LLMError("LLM is not configured. Set LLM_API_KEY.")
        try:
            try:
                completion = self._create(system_prompt, user_content)
            except RateLimitError as error:
                # Free tiers rate-limit bursts: wait once, briefly, then retry a single time.
                self.sleep(self._rate_limit_wait(error.response.headers.get("retry-after")))
                completion = self._create(system_prompt, user_content)
            content = completion.choices[0].message.content
            if content is None:
                raise LLMError("LLM returned a malformed response.")
            parsed = json.loads(content)
        except OpenAIError as error:
            status = getattr(error, "status_code", None)
            detail = f"HTTP {status}" if status else type(error).__name__
            raise LLMError(f"LLM request failed: {detail}") from error
        except (IndexError, json.JSONDecodeError) as error:
            raise LLMError("LLM returned a malformed response.") from error
        if not isinstance(parsed, dict):
            raise LLMError("LLM returned JSON that is not an object.")

        result: dict[str, Any] = parsed  # pyright: ignore[reportUnknownVariableType]
        self._cache[key] = result
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return result

    def _client(self) -> OpenAI:
        if self._openai is None:
            self._openai = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                max_retries=0,
            )
        return self._openai

    def _create(self, system_prompt: str, user_content: str) -> ChatCompletion:
        self.calls += 1
        return self._client().chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )

    def _rate_limit_wait(self, retry_after: str | None) -> float:
        """Retry-After in seconds, capped; the default when it is missing or not a number."""
        try:
            wait = float(retry_after) if retry_after is not None else self.rate_limit_default_wait_seconds
        except ValueError:
            wait = self.rate_limit_default_wait_seconds
        return max(0.0, min(wait, self.rate_limit_max_wait_seconds))


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        max_tokens=settings.LLM_MAX_TOKENS,
        rate_limit_default_wait_seconds=settings.LLM_RATE_LIMIT_DEFAULT_WAIT_SECONDS,
        rate_limit_max_wait_seconds=settings.LLM_RATE_LIMIT_MAX_WAIT_SECONDS,
    )
