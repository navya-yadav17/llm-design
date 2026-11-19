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
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

The local runner uses `.venv` when present, generates a random API key if `DIAGNOSTICS_API_KEY` is not set, and prints a generated key once for API requests. It binds to `127.0.0.1` and does not persist the generated key. To use your own key, set `DIAGNOSTICS_API_KEY` in the current PowerShell session before running it. To change the port, add `-Port 8080`. The execution-policy bypass applies only to this PowerShell process.

Check `http://127.0.0.1:8000/health` or submit logs from another PowerShell window. Copy the key printed by the runner into `$env:DIAGNOSTICS_API_KEY` before submitting a request:

```powershell
$env:DIAGNOSTICS_API_KEY = "paste-the-key-printed-by-run-local"
```

```powershell
$body = @{ logs = "2026-10-24T10:30:00Z ERROR request_id=req-123 failure`n  at app.handler(service.py:42)" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/diagnostics/analyze -Headers @{ Authorization = "Bearer $env:DIAGNOSTICS_API_KEY" } -ContentType "application/json" -Body $body
```

The analysis endpoint requires `DIAGNOSTICS_API_KEY`; it fails closed with `503` if the key is not configured and returns `401` for missing or incorrect bearer tokens. Requests are limited per client IP using `DIAGNOSTICS_RATE_LIMIT` and `DIAGNOSTICS_RATE_WINDOW_SECONDS` (defaults: 60 requests per 60 seconds). The rate limiter is process-local, so it is not shared across workers or replicas and is not a substitute for an edge/API gateway limit. `/health` remains public and is not rate-limited. Responses include correlation-ID trace groups with 1-based line numbers into the non-empty input lines; raw log lines are not returned.

To enable model-assisted analysis, set `DIAGNOSTICS_LLM_ENABLED=true`, `DIAGNOSTICS_LLM_BASE_URL`, and `DIAGNOSTICS_LLM_MODEL`. `DIAGNOSTICS_LLM_API_KEY` is optional for local gateways. Environment variables must be loaded into the process by the operator; the service does not load `.env` files automatically. Only use a provider approved for your log data. Redaction is best-effort and must not be treated as a guarantee that logs contain no sensitive data.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
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

Authentication and process-local request limits protect the analysis endpoint. The service still does not persist logs, so retention controls are not applicable yet; persistent storage, auditability, distributed rate limiting, and workflow integrations require a deployment-specific design. The intended diagnosis should distinguish observed evidence from hypotheses, include confidence and verification steps, and never trigger automatic remediation in the initial releases.

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

1. Validate parsing against representative logs from the target services and broaden the root-cause evaluation set.
2. Expand trace stitching across events and sources after defining the ingestion format.
3. Add persistence only with a defined retention, audit, and privacy policy.
4. Add alerting/ticket integrations and measure MTTD/MTTR.
5. Select a cloud and deploy behind production-grade authentication and rate limiting.

## Operational success measures

Establish a baseline before rollout, then measure time from first relevant log event to a useful alert (MTTD) and to operator-confirmed resolution (MTTR). Track diagnosis usefulness and false-positive rates alongside latency and cost; compare against a non-LLM baseline before expanding automation.
