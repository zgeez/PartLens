"""Redact configured secrets before diagnostic text or run events leave a process."""

from __future__ import annotations

import os
import re
from typing import Any


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if re.search(r"(?i)(api[_-]?key|access[_-]?key(?:id)?|authorization|password|secret|token|signature)$", k)
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for name, secret in os.environ.items():
            if len(secret) >= 4 and (re.search(r"(?i)(key|token|password|secret)$", name)
                                     or name == "JLC_APP_ID"):
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)([?&](?:api[_-]?key|ossaccesskeyid|access[_-]?key|security-token|signature|token)=)[^&\s]+",
                       r"\1[REDACTED]", value)
        value = re.sub(r'(?i)JOP\s+appid="[^\r\n]+', 'JOP [REDACTED]', value)
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    return value
