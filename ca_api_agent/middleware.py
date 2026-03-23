"""Middleware to extract Bearer tokens from incoming A2A Cloud Run headers."""
import logging
from ca_api_agent.auth_context import request_bearer_token

logger = logging.getLogger(__name__)

class HeaderLoggerMiddleware:
    """ASGIMiddleware that logs incoming request headers and extracts Bearer tokens."""
    
    def __init__(self, app):
        """Initializes the middleware with the ASGI application."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Processes an ASGI request, logging headers and setting the bearer token."""
        if scope["type"] == "http":
            try:
                headers = dict(scope.get("headers", []))
                decoded_headers = {k.decode("latin1"): v.decode("latin1") for k, v in headers.items()}
                logger.info(f"Incoming request headers: {decoded_headers}")
                
                auth_header = decoded_headers.get("authorization", "")
                if auth_header.lower().startswith("bearer "):
                    token = auth_header[7:].strip()
                    request_bearer_token.set(token)
            except Exception as e:
                logger.error(f"Error decoding headers: {e}")
        await self.app(scope, receive, send)
