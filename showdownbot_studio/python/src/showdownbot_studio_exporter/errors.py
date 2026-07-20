"""Export refuse reasons — exit code 2 on CLI."""

from __future__ import annotations


class ExportRefuse(Exception):
    """Fail-closed export refusal with a stable reason code."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(f"{reason}: {message}")

    def format_stderr(self) -> str:
        return f"{self.reason}: {self.message}"
