"""API contract tests — input validation, health/readiness, error shape.

None of these reach OpenAI: validation rejects bad input before the agent runs,
and the agent is stubbed where a valid request is needed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthAndReadiness:
    def test_health_is_liveness_only(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_readiness_reports_individual_checks(self):
        r = client.get("/ready")
        assert r.status_code in (200, 503)
        assert set(r.json()["checks"]) == {"database", "openai_key"}

    def test_every_response_carries_a_request_id(self):
        assert client.get("/health").headers.get("X-Request-ID")


class TestQueryValidation:
    """Input caps exist to stop unbounded payloads reaching a paid model."""

    def test_rejects_message_over_length_cap(self):
        r = client.post("/api/query", json={"message": "x" * 1001})
        assert r.status_code == 422

    def test_rejects_empty_message(self):
        assert client.post("/api/query", json={"message": ""}).status_code == 422

    def test_rejects_missing_message(self):
        assert client.post("/api/query", json={}).status_code == 422

    @pytest.mark.parametrize("minutes", [0, -5, 99999])
    def test_rejects_out_of_range_time_available(self, minutes):
        r = client.post(
            "/api/query", json={"message": "hi", "time_available": minutes}
        )
        assert r.status_code == 422

    def test_rejects_oversized_location(self):
        r = client.post("/api/query", json={"message": "hi", "location": "x" * 101})
        assert r.status_code == 422

    def test_accepts_valid_payload(self, monkeypatch):
        async def fake_handle_query(**_kwargs):
            return {"response": "ok", "type": "places", "tool_calls": []}

        monkeypatch.setattr(
            "app.routes.query.handle_query", fake_handle_query
        )
        r = client.post(
            "/api/query",
            json={"message": "study spot", "location": "CAS", "time_available": 30},
        )
        assert r.status_code == 200
        assert r.json()["response"] == "ok"


class TestErrorHandling:
    def test_internal_errors_do_not_leak_exception_text(self, monkeypatch):
        """Raw exception text can expose connection strings and prompts."""
        async def boom(**_kwargs):
            raise RuntimeError("postgresql://user:password@host/db is unreachable")

        monkeypatch.setattr("app.routes.query.handle_query", boom)
        r = client.post("/api/query", json={"message": "hi"})
        assert r.status_code == 500
        assert "password" not in r.text
        assert r.json()["detail"] == "Something went wrong."

    def test_timeout_returns_504_not_500(self, monkeypatch):

        async def slow(**_kwargs):
            raise TimeoutError()

        monkeypatch.setattr("app.routes.query.handle_query", slow)
        r = client.post("/api/query", json={"message": "hi"})
        assert r.status_code == 504
