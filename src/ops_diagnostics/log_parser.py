import re
from dataclasses import dataclass


_FRAME_PATTERNS = (
    re.compile(r'^\s*File "([^"]+)", line (\d+), in (.+)$'),
    re.compile(r"^\s*at (.+)$"),
)
_LEVEL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)(?![A-Za-z0-9_-])",
    re.I,
)
_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_CORRELATION_PATTERN = re.compile(
    r"\b(?:trace[_-]?id|request[_-]?id|correlation[_-]?id)\s*[=:]\s*([A-Za-z0-9._:-]{1,128})",
    re.I,
)


@dataclass(frozen=True)
class ParsedLogs:
    lines: list[str]
    stack_frames: list[str]
    levels: list[str]
    timestamps: list[str]
    correlation_ids: list[str]


def parse_logs(raw_logs: str) -> ParsedLogs:
    lines = [line for line in raw_logs.splitlines() if line.strip()]
    stack_frames = [
        line.strip()
        for line in lines
        if any(pattern.match(line) for pattern in _FRAME_PATTERNS)
    ]
    levels = list(dict.fromkeys(match.group(1).upper() for line in lines if (match := _LEVEL_PATTERN.search(line))))
    timestamps = list(dict.fromkeys(match.group(0) for line in lines if (match := _TIMESTAMP_PATTERN.search(line))))
    correlation_ids = list(
        dict.fromkeys(match.group(1) for line in lines if (match := _CORRELATION_PATTERN.search(line)))
    )
    return ParsedLogs(
        lines=lines,
        stack_frames=stack_frames,
        levels=levels,
        timestamps=timestamps,
        correlation_ids=correlation_ids,
    )
