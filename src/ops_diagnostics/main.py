import hmac
import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ops_diagnostics.llm import LLMSettings, ProviderError, infer_root_cause
from ops_diagnostics.log_parser import parse_logs
from ops_diagnostics.redaction import redact_secrets


@dataclass(frozen=True)
class IngressSettings:
    api_key: str
    rate_limit: int
    rate_window_seconds: int

    @classmethod
    def from_environment(cls) -> "IngressSettings":
        rate_limit = int(os.getenv("DIAGNOSTICS_RATE_LIMIT", "60"))
        rate_window_seconds = int(os.getenv("DIAGNOSTICS_RATE_WINDOW_SECONDS", "60"))
        if rate_limit < 1 or rate_window_seconds < 1:
            raise ValueError("Diagnostics rate-limit settings must be positive integers.")
        return cls(
            api_key=os.getenv("DIAGNOSTICS_API_KEY", ""),
            rate_limit=rate_limit,
            rate_window_seconds=rate_window_seconds,
        )


app = FastAPI(
    title="Ops Diagnostics",
    description="Privacy-conscious application log parsing and LLM-assisted triage.",
    version="0.1.0",
)
_llm_settings = LLMSettings.from_environment()
_ingress_settings = IngressSettings.from_environment()
_rate_limit_hits: OrderedDict[str, deque[float]] = OrderedDict()
_rate_limit_lock = Lock()
_MAX_TRACKED_CLIENTS = 10_000


class AnalyzeRequest(BaseModel):
    logs: str = Field(min_length=1, max_length=200_000)


class TraceGroupResponse(BaseModel):
    correlation_id: str
    line_numbers: list[int]


class AnalyzeResponse(BaseModel):
    status: str
    line_count: int
    severity_levels: list[str]
    timestamps: list[str]
    correlation_ids: list[str]
    trace_groups: list[TraceGroupResponse]
    stack_frames: list[str]
    root_cause_analysis: str | None


@app.middleware("http")
async def protect_analysis_endpoint(request, call_next):
    if request.url.path != "/v1/diagnostics/analyze":
        return await call_next(request)

    if not _ingress_settings.api_key:
        return JSONResponse(
            status_code=503,
            content={"detail": "DIAGNOSTICS_API_KEY must be configured to use the analysis endpoint."},
        )

    authorization = request.headers.get("authorization", "")
    scheme, separator, supplied_key = authorization.partition(" ")
    if (
        scheme.lower() != "bearer"
        or not separator
        or not hmac.compare_digest(supplied_key, _ingress_settings.api_key)
    ):
        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            content={"detail": "A valid bearer token is required."},
        )

    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_limit_lock:
        hits = _rate_limit_hits.setdefault(client_key, deque())
        _rate_limit_hits.move_to_end(client_key)
        cutoff = now - _ingress_settings.rate_window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= _ingress_settings.rate_limit:
            retry_after = max(1, int(hits[0] + _ingress_settings.rate_window_seconds - now + 0.999))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Request rate limit exceeded."},
            )
        hits.append(now)
        while len(_rate_limit_hits) > _MAX_TRACKED_CLIENTS:
            _rate_limit_hits.popitem(last=False)

    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/diagnostics/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    parsed = parse_logs(request.logs)
    try:
        analysis = infer_root_cause(request.logs, parsed, _llm_settings)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalyzeResponse(
        status="completed" if analysis is not None else "llm_disabled",
        line_count=len(parsed.lines),
        severity_levels=parsed.levels,
        timestamps=parsed.timestamps,
        correlation_ids=parsed.correlation_ids,
        trace_groups=[
            TraceGroupResponse(
                correlation_id=trace.correlation_id,
                line_numbers=trace.line_numbers,
            )
            for trace in parsed.trace_groups
        ],
        stack_frames=[redact_secrets(frame) for frame in parsed.stack_frames],
        root_cause_analysis=analysis,
    )
