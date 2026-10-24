"""CORS limited to CORS_ORIGINS (NFR-7). Run: cd server && python -m unittest discover -s tests -t ."""

import os
import unittest
from unittest import mock

import tests.support  # noqa: F401  (test settings first)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import app
from app.shared.env import Settings


def preflight(client: TestClient, origin: str):
    return client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


class CorsTest(unittest.TestCase):
    def test_app_uses_the_configured_origins(self) -> None:
        cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        self.assertEqual(len(cors), 1)
        self.assertEqual(cors[0].kwargs["allow_origins"], [])  # the tests set CORS_ORIGINS=[]

    def test_listed_origin_allowed_other_refused(self) -> None:
        with mock.patch.dict(os.environ, {"CORS_ORIGINS": '["http://localhost:3000"]'}):
            origins = Settings().CORS_ORIGINS
        probe = FastAPI()
        probe.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"])
        probe.get("/health")(lambda: {"status": "ok"})
        client = TestClient(probe)
        allowed = preflight(client, "http://localhost:3000")
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertNotIn("access-control-allow-origin", preflight(client, "http://evil.example").headers)
