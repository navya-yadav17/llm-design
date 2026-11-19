import pytest
from fastapi.testclient import TestClient

from ops_diagnostics import main
from ops_diagnostics.llm import LLMSettings
from ops_diagnostics.main import IngressSettings


@pytest.fixture(autouse=True)
def configure_ingress(monkeypatch) -> None:
    main._rate_limit_hits.clear()
    monkeypatch.setattr(
        main,
        "_ingress_settings",
        IngressSettings(api_key="test-key", rate_limit=60, rate_window_seconds=60),
    )


def test_health_endpoint() -> None:
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_endpoint_returns_parsed_logs_when_llm_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_llm_settings",
        LLMSettings(enabled=False, base_url="", model="", api_key=""),
    )

    response = TestClient(main.app).post(
        "/v1/diagnostics/analyze",
        json={
            "logs": (
                "2026-10-24T10:30:00Z ERROR request_id=req-123 failure\n"
                '  File "service.py", line 42, in handle'
            )
        },
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "llm_disabled",
        "line_count": 2,
        "severity_levels": ["ERROR"],
        "timestamps": ["2026-10-24T10:30:00Z"],
        "correlation_ids": ["req-123"],
        "trace_groups": [{"correlation_id": "req-123", "line_numbers": [1, 2]}],
        "stack_frames": ['File "service.py", line 42, in handle'],
        "root_cause_analysis": None,
    }


def test_analyze_endpoint_rejects_empty_logs() -> None:
    response = TestClient(main.app).post(
        "/v1/diagnostics/analyze",
        json={"logs": ""},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 422


def test_analyze_endpoint_requires_a_valid_bearer_token() -> None:
    client = TestClient(main.app)

    missing_token = client.post("/v1/diagnostics/analyze", json={"logs": "ERROR failed"})
    invalid_token = client.post(
        "/v1/diagnostics/analyze",
        json={"logs": "ERROR failed"},
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert missing_token.status_code == 401
    assert missing_token.headers["www-authenticate"] == "Bearer"
    assert invalid_token.status_code == 401


def test_analysis_endpoint_fails_closed_when_authentication_is_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_ingress_settings",
        IngressSettings(api_key="", rate_limit=60, rate_window_seconds=60),
    )

    response = TestClient(main.app).post(
        "/v1/diagnostics/analyze",
        json={"logs": "ERROR failed"},
    )

    assert response.status_code == 503


def test_analysis_endpoint_enforces_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_ingress_settings",
        IngressSettings(api_key="test-key", rate_limit=1, rate_window_seconds=60),
    )
    client = TestClient(main.app)
    headers = {"Authorization": "Bearer test-key"}

    first = client.post(
        "/v1/diagnostics/analyze",
        json={"logs": "ERROR failed"},
        headers=headers,
    )
    second = client.post(
        "/v1/diagnostics/analyze",
        json={"logs": "ERROR failed"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) > 0


def test_health_endpoint_is_not_rate_limited_or_authenticated(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_ingress_settings",
        IngressSettings(api_key="test-key", rate_limit=1, rate_window_seconds=60),
    )
    client = TestClient(main.app)

    responses = [client.get("/health") for _ in range(2)]

    assert [response.status_code for response in responses] == [200, 200]
