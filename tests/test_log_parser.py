from ops_diagnostics.log_parser import parse_logs


def test_parses_multilanguage_frames_and_correlation_metadata() -> None:
    parsed = parse_logs(
        "2026-10-24T10:30:00Z ERROR request_id=req-123 failure\n"
        '  File "service.py", line 42, in handle\n'
        "    at com.example.Service.run(Service.java:27)\n"
        "trace_id=trace-456 WARN retrying"
    )

    assert parsed.levels == ["ERROR", "WARN"]
    assert parsed.timestamps == ["2026-10-24T10:30:00Z"]
    assert parsed.correlation_ids == ["req-123", "trace-456"]
    assert len(parsed.stack_frames) == 2


def test_ignores_blank_lines() -> None:
    parsed = parse_logs("\n INFO started \n\n")

    assert parsed.lines == [" INFO started "]
    assert parsed.levels == ["INFO"]
