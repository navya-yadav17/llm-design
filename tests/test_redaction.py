from ops_diagnostics.redaction import redact_secrets


def test_redacts_common_secrets_without_removing_field_names() -> None:
    text = 'password="secret-value" api_key=abc123 Authorization: Bearer token123'

    redacted = redact_secrets(text)

    assert "secret-value" not in redacted
    assert "abc123" not in redacted
    assert "token123" not in redacted
    assert redacted.count("[REDACTED]") == 3
