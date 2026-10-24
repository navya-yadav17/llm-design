# Ops Diagnostics

A local-first foundation for turning application error logs into structured, evidence-based on-call diagnostics.

## Step 1 scope

This initial slice provides:

- A FastAPI service with a health check and a log-analysis endpoint.
- Basic extraction of severity, timestamps, common correlation IDs, and Python/JVM/Node-style stack frames.
- An OpenAI-compatible LLM provider boundary, disabled unless explicitly opted in.
- Redaction of common credential patterns before sending log text to the configured provider.
- No persistence, telemetry, or automatic remediation.

The parser output is available even while LLM calls are disabled. In that mode the API reports `llm_disabled` and does not invent a root cause. This is a starting point, not yet a production incident-management system.

## Run locally

Requires Python 3.11 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn ops_diagnostics.main:app --reload --app-dir src
```

Check `http://127.0.0.1:8000/health` or submit logs:

```powershell
$body = @{ logs = "2026-10-24T10:30:00Z ERROR request_id=req-123 failure`n  at app.handler(service.py:42)" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/diagnostics/analyze -ContentType "application/json" -Body $body
```

To enable model-assisted analysis, copy `.env.example` to `.env` and set `DIAGNOSTICS_LLM_ENABLED=true`, `DIAGNOSTICS_LLM_BASE_URL`, and `DIAGNOSTICS_LLM_MODEL`. `DIAGNOSTICS_LLM_API_KEY` is optional for local gateways. Environment variables must be loaded into the process by the operator; the service does not load `.env` files automatically. Only use a provider approved for your log data. Redaction is best-effort and must not be treated as a guarantee that logs contain no sensitive data.

## Test

```powershell
python -m pytest
```

## Target architecture

```text
application agents / files / log platforms
                |
                v
authenticated ingestion -> size/rate limits -> normalization + secret scrubbing
                |
                v
event grouping + trace/correlation-ID stitching -> multi-tier stack-trace synthesis
                |
                v
evidence extraction -> opt-in LLM inference -> confidence + citations to source lines
                |
                v
diagnostic API -> alert/ticket/chat integrations -> operator feedback
                |
                v
redacted, retention-controlled telemetry for quality and MTTD/MTTR measurement
```

The ingestion, storage, and workflow integrations are future phases, not part of this local prototype. The intended diagnosis should distinguish observed evidence from hypotheses, include confidence and verification steps, and never trigger automatic remediation in the initial releases.

## Initial architecture

```text
log source / operator
        |
        v
FastAPI ingress -> bounded request validation -> metadata + stack-frame parser
                                             -> credential redaction
                                             -> opt-in LLM provider adapter
        |
        v
structured diagnostic response (no persistence in this step)
```

## Next steps

1. Validate parser behavior against representative logs from the target services.
2. Add provider-specific configuration, timeouts/retries, and evaluation fixtures.
3. Add authenticated ingestion, rate limits, auditability, and an explicit retention policy before operational deployment.
4. Connect alerting/ticketing workflows only after diagnosis quality and privacy boundaries are validated.
5. Add deployment manifests and observability after selecting a hosting target.

## Operational success measures

Establish a baseline before rollout, then measure time from first relevant log event to a useful alert (MTTD) and to operator-confirmed resolution (MTTR). Track diagnosis usefulness and false-positive rates alongside latency and cost; compare against a non-LLM baseline before expanding automation.
