"""Uniform error envelope {"error": {"code", "message", "details"}} for every non-2xx response."""
from __future__ import annotations


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def body(self) -> dict:
        err = {"code": self.code, "message": self.message}
        if self.details is not None:
            err["details"] = self.details
        return {"error": err}


def not_found(code, message, details=None):
    return APIError(404, code, message, details)


def unprocessable(code, message, details=None):
    return APIError(422, code, message, details)


def conflict(code, message, details=None):
    return APIError(409, code, message, details)


def unavailable(code, message, details=None):
    return APIError(503, code, message, details)
