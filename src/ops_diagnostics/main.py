from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ops_diagnostics.llm import LLMSettings, ProviderError, infer_root_cause
from ops_diagnostics.log_parser import parse_logs
from ops_diagnostics.redaction import redact_secrets

app = FastAPI(
    title="Ops Diagnostics",
    description="Privacy-conscious application log parsing and LLM-assisted triage.",
    version="0.1.0",
)
_llm_settings = LLMSettings.from_environment()


class AnalyzeRequest(BaseModel):
    logs: str = Field(min_length=1, max_length=200_000)


class AnalyzeResponse(BaseModel):
    status: str
    line_count: int
    severity_levels: list[str]
    timestamps: list[str]
    correlation_ids: list[str]
    stack_frames: list[str]
    root_cause_analysis: str | None


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
        stack_frames=[redact_secrets(frame) for frame in parsed.stack_frames],
        root_cause_analysis=analysis,
    )
