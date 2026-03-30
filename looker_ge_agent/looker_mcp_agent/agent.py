import logging
import json
import jwt
import time
from google.adk import Agent
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.agents.readonly_context import ReadonlyContext
import os
import google.auth
import google.auth.transport.requests
import google.oauth2.id_token
from dotenv import load_dotenv
from google.adk.planners import BuiltInPlanner
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

from .constants import MCP_SERVER_URL, LOOKER_AUTH_STATE_KEY, DEFAULT_MCP_SERVER_MODEL

_token_cache = {}

def get_id_token() -> str:
    """Retrieves a GCP ID token for authenticating with the MCP server, with caching."""
    target_url = MCP_SERVER_URL
    # Deriving the audience from the service URL (strip the path)
    audience = target_url.split('/mcp')[0]
    
    global _token_cache
    
    # Check if we have a valid cached token
    now = int(time.time())
    threshold_mins = int(os.environ.get("TOKEN_REFRESH_THRESHOLD_MINS", "15"))
    threshold_secs = threshold_mins * 60
    
    if target_url in _token_cache:
        cached_info = _token_cache[target_url]
        if now + threshold_secs < cached_info.get("token_expiration_time", 0):
            logger.info("Using cached valid old token")
            return cached_info["id_token"]
        else:
            logger.info("Cached token expired or about to expire. Refreshing...")
            
    logger.info("Generating a new GCP ID token...")
    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
    
    try:
        decoded_payload = jwt.decode(id_token, options={"verify_signature": False})
        _token_cache[target_url] = {
            "id_token": id_token,
            "token_expiration_time": decoded_payload.get('exp', 0)
        }
        logger.info(f"Cached new token with exp {decoded_payload.get('exp')}")
    except Exception as e:
        logger.warning(f"Failed to decode token for caching: {e}")
        
    return id_token

def set_header_tokens(context: ReadonlyContext, **kwargs) -> dict:
    """Generates headers for the outgoing MCP tool request."""
    ctx_dict = {}
    for attr in dir(context):
        if not attr.startswith("_") and not callable(getattr(context, attr)):
            try:
                ctx_dict[attr] = str(getattr(context, attr))
            except Exception as e:
                ctx_dict[attr] = f"<Error reading value: {e}>"

    # 1. Get the Looker OAuth token from context var
    state = kwargs.get('state') or getattr(context, 'state', None)
    session = kwargs.get('session') or getattr(context, 'session', None)
    looker_token = None
    
    if state and LOOKER_AUTH_STATE_KEY in state:
        looker_token = state.get(LOOKER_AUTH_STATE_KEY)
        logger.info(f"[set_header_tokens] Found token in state")
    elif session and hasattr(session, 'state') and LOOKER_AUTH_STATE_KEY in session.state:
        looker_token = session.state.get(LOOKER_AUTH_STATE_KEY)
        logger.info(f"[set_header_tokens] Found token in session.state")

    headers = {}

    if looker_token is not None:
        logger.info("[header_provider] Injecting X-Looker-Token header.")
        headers["X-Looker-Token"] = f"token {looker_token}"
    else:
        logger.warning("[header_provider] Looker token missing.")

    # 2. Get the GCP identity token for the Cloud Run MCP server
    id_token = get_id_token()

    if id_token:
        headers["Authorization"] = f"Bearer {id_token}"
    else:
        logger.warning("GCP ID token fetch failed.")

    return headers

def _safe_to_dict(obj):
    if hasattr(obj, 'model_dump'): return obj.model_dump()
    if hasattr(obj, 'to_dict'): return obj.to_dict()
    if isinstance(obj, dict): return obj
    try: return dict(obj)
    except:
        try: return vars(obj)
        except: return str(obj)

model = Gemini(model_name=DEFAULT_MCP_SERVER_MODEL)
# Create the simple ADK agent
root_agent = Agent(
    name="looker_mcp_agent",
    model=model,
    description="An agent that has access to Looker APIs via MCP.",
    instruction="You are a helpful assistant that can answer questions about Looker data. Use the Looker MCP tools to query and analyze data, or perform other Looker actions.",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=MCP_SERVER_URL
            ),
            header_provider=set_header_tokens,
            errlog=None
        )
    ],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    )
)
