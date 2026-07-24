from __future__ import annotations

from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
analysis_id_context: ContextVar[str] = ContextVar("analysis_id", default="-")


def get_request_id() -> str:
    return request_id_context.get()


def get_analysis_id() -> str:
    return analysis_id_context.get()
