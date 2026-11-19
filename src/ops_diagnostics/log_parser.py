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
    r"""["']?\b(?:trace[_-]?id|request[_-]?id|correlation[_-]?id)\b["']?\s*[=:]\s*["']?([A-Za-z0-9._:-]{1,128})""",
    re.I,
)


@dataclass(frozen=True)
class ParsedLogs:
    lines: list[str]
    stack_frames: list[str]
    levels: list[str]
    timestamps: list[str]
    correlation_ids: list[str]
    trace_groups: list["TraceGroup"]


@dataclass(frozen=True)
class TraceGroup:
    correlation_id: str
    line_numbers: list[int]


def _is_stack_frame(line: str) -> bool:
    return any(pattern.match(line) for pattern in _FRAME_PATTERNS)


def parse_logs(raw_logs: str) -> ParsedLogs:
    lines = [line for line in raw_logs.splitlines() if line.strip()]
    stack_frames = [
        line.strip()
        for line in lines
        if _is_stack_frame(line)
    ]
    levels = list(dict.fromkeys(match.group(1).upper() for line in lines if (match := _LEVEL_PATTERN.search(line))))
    timestamps = list(dict.fromkeys(match.group(0) for line in lines if (match := _TIMESTAMP_PATTERN.search(line))))
    trace_lines: dict[str, list[int]] = {}
    active_ids: list[str] = []
    correlation_ids: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        line_ids = [match.group(1) for match in _CORRELATION_PATTERN.finditer(line)]
        if line_ids:
            active_ids = list(dict.fromkeys(line_ids))
            for correlation_id in active_ids:
                if correlation_id not in correlation_ids:
                    correlation_ids.append(correlation_id)
                trace_lines.setdefault(correlation_id, []).append(line_number)
        elif active_ids and (_is_stack_frame(line) or line[:1].isspace()):
            for correlation_id in active_ids:
                trace_lines[correlation_id].append(line_number)
        else:
            active_ids = []

    return ParsedLogs(
        lines=lines,
        stack_frames=stack_frames,
        levels=levels,
        timestamps=timestamps,
        correlation_ids=correlation_ids,
        trace_groups=[
            TraceGroup(correlation_id, line_numbers)
            for correlation_id, line_numbers in trace_lines.items()
        ],
    )
