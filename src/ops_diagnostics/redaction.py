import re


_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), 1),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+"), 1),
    (
        re.compile(
            r"""(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\b(\s*[:=]\s*)("[^"]*"|'[^']*'|[^\s,;]+)"""
        ),
        2,
    ),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern, preserved_groups in _SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda match: "".join(
                match.group(index) for index in range(1, preserved_groups + 1)
            )
            + "[REDACTED]",
            redacted,
        )
    return redacted
