from contextvars import ContextVar

request_bearer_token: ContextVar[str | None] = ContextVar("request_bearer_token", default=None)
