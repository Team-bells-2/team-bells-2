"""LLM wrapper: rate-limit retry and cache (NFR-8; BR-A6). Run: cd server && python -m unittest discover -s tests -t ."""

import json
import unittest
from unittest import mock

import httpx

import tests.support  # noqa: F401  (test settings first)
from app.shared.Infrastructure.llm.client import LLMClient, LLMError

REQUEST = httpx.Request("POST", "http://llm.invalid/v1/chat/completions")


def reply(status: int, body: object = None, retry_after: str | None = None) -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    content = {"choices": [{"message": {"content": json.dumps(body)}}]} if body is not None else {}
    return httpx.Response(status, json=content, headers=headers, request=REQUEST)


class LLMClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.waits: list[float] = []
        self.client = LLMClient(
            base_url="http://llm.invalid/v1", api_key="key", model="m", timeout_seconds=5, max_tokens=100,
            rate_limit_default_wait_seconds=1.5, rate_limit_max_wait_seconds=3, sleep=self.waits.append,
        )

    def call(self, *responses: httpx.Response) -> dict:
        with mock.patch("httpx.post", side_effect=list(responses)) as post:
            try:
                return self.client.complete_json("prompt", {"message": "hi"})
            finally:
                self.posts = post.call_count

    def test_rate_limited_once_then_succeeds(self) -> None:
        self.assertEqual(self.call(reply(429, retry_after="2"), reply(200, {"ok": True})), {"ok": True})
        self.assertEqual((self.posts, self.waits, self.client.calls), (2, [2.0], 2))

    def test_rate_limited_twice_fails(self) -> None:
        with self.assertRaises(LLMError):
            self.call(reply(429), reply(429))
        self.assertEqual((self.posts, self.waits), (2, [1.5]))  # default wait when Retry-After is missing

    def test_wait_is_capped(self) -> None:
        self.call(reply(429, retry_after="60"), reply(200, {"ok": True}))
        self.assertEqual(self.waits, [3.0])

    def test_unreadable_retry_after_uses_the_default(self) -> None:
        self.call(reply(429, retry_after="Wed, 21 Oct 2026 07:28:00 GMT"), reply(200, {"ok": True}))
        self.assertEqual(self.waits, [1.5])

    def test_other_errors_are_not_retried(self) -> None:
        with self.assertRaises(LLMError):
            self.call(reply(500))
        self.assertEqual((self.posts, self.waits), (1, []))

    def test_identical_requests_are_cached(self) -> None:
        self.call(reply(200, {"ok": True}))
        self.assertEqual(self.call(), {"ok": True})  # no response queued: served from the cache
        self.assertEqual(self.client.calls, 1)
