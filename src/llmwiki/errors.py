"""Error type shared by all commands."""

from __future__ import annotations

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_ERROR = 2


class WikiError(Exception):
    """An expected failure with a stable machine-readable code.

    Always maps to exit code 2 (usage error, invalid input, missing vault,
    or operational failure).
    """

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        err: dict = {"code": self.code, "message": self.message}
        if self.details:
            err["details"] = self.details
        return {"error": err}
