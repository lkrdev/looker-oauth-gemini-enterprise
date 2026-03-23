"""Middleware to extract Bearer tokens from incoming A2A Cloud Run headers."""
import logging
from looker_mcp_agent.auth_context import request_bearer_token

logger = logging.getLogger(__name__)

class HeaderLoggerMiddleware:
    """ASGIMiddleware that logs incoming request headers and extracts Bearer tokens.
    
    This middleware is inserted into the A2A ASGI app chain. It identifies 'Bearer' 
    tokens in the Authorization header and populates the `request_bearer_token` 
    ContextVar for downstream use by the Looker MCP Agent.
    """
    
    def __init__(self, app):
        """Initializes the middleware with the ASGI application."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Processes an ASGI request, logging headers and setting the bearer token."""
        if scope["type"] == "http":
            try:
                # Extract headers from ASGI scope
                headers = dict(scope.get("headers", []))
                # Decode byte headers to strings for logging/parsing
                decoded_headers = {k.decode("latin1"): v.decode("latin1") for k, v in headers.items()}
                logger.debug(f"Incoming request headers: {decoded_headers}")
                
                # Look for the Bearer token in the 'authorization' header
                auth_header = decoded_headers.get("authorization", "")
                if auth_header.lower().startswith("bearer "):
                    token = auth_header[7:].strip()
                    # Populate the context variable for the duration of this request
                    request_bearer_token.set(token)
                    logger.info("Successfully extracted Bearer token to ContextVar.")
            except Exception as e:
                logger.error(f"Error decoding headers in middleware: {e}")
        await self.app(scope, receive, send)
