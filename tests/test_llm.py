from ops_diagnostics.llm import LLMSettings, infer_root_cause
from ops_diagnostics.log_parser import parse_logs


def test_sends_bearer_key_and_redacts_logs_before_provider_call(monkeypatch) -> None:
    request: dict[str, object] = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "Check the database connection."}}]}

    def mock_post(url: str, **kwargs: object) -> MockResponse:
        request["url"] = url
        request.update(kwargs)
        return MockResponse()

    monkeypatch.setattr("ops_diagnostics.llm.httpx.post", mock_post)
    raw_logs = "2026-10-24T10:30:00Z ERROR api_key=secret-value"
    settings = LLMSettings(
        enabled=True,
        base_url="https://provider.example/v1",
        model="diagnostic-model",
        api_key="provider-key",
    )

    result = infer_root_cause(raw_logs, parse_logs(raw_logs), settings)

    assert result == "Check the database connection."
    assert request["url"] == "https://provider.example/v1/chat/completions"
    assert request["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer provider-key",
    }
    payload = request["json"]
    assert isinstance(payload, dict)
    prompt = payload["messages"][1]["content"]
    assert "secret-value" not in prompt
    assert "api_key=[REDACTED]" in prompt


def test_disabled_provider_does_not_make_a_request() -> None:
    settings = LLMSettings(enabled=False, base_url="", model="", api_key="")

    assert infer_root_cause("ERROR failed", parse_logs("ERROR failed"), settings) is None
