"""Context variable to store the bearer token for each request."""
from contextvars import ContextVar

# Context-local storage for the bearer token extracted by the middleware.
# Used to pass the Looker OAuth token from the FastAPI layer to the ADK agent.
request_bearer_token: ContextVar[str | None] = ContextVar("request_bearer_token", default=None)
