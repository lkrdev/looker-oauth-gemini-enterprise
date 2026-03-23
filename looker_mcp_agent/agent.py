from google.adk import Agent
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.planners import BuiltInPlanner
from google.genai import types
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams, StdioServerParameters, StreamableHTTPConnectionParams
import logging
import os
import google.auth
import google.auth.transport.requests
import google.oauth2.id_token
from dotenv import load_dotenv
import json

from looker_mcp_agent.auth_context import request_bearer_token

# Configure logging to output INFO and DEBUG messages
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
if not MCP_SERVER_URL:
    raise ValueError("The environment variable MCP_SERVER_URL is not set.")

def get_id_token() -> str:
    """Retrieves a GCP ID token for authenticating with the MCP server.

    Uses the default Google Cloud credentials to fetch an ID token for the 
    audience derived from the MCP_SERVER_URL.

    Returns:
        str: The fetched ID token string.
    """
    target_url = MCP_SERVER_URL
    # Deriving the audience from the service URL (strip the path)
    audience = target_url.split('/mcp')[0]
    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
    return id_token


def get_access_token() -> str | None:
    """Retrieves the Looker OAuth access token from the request context.

    Pulls the 'Bearer' token extracted by the `HeaderLoggerMiddleware` and 
    stored in the `request_bearer_token` ContextVar.

    Returns:
        str | None: The Looker access token if found, else None.
    """
    token = request_bearer_token.get()
    
    if token is None:
        logging.warning("[get_access_token] ⚠️ No access token found in context.")
    else:
        logging.info("[get_access_token] ✅ Successfully retrieved access token.")
        
    return token


def set_header_tokens(context: ReadonlyContext) -> dict:
    """Generates headers for the outgoing MCP tool request.

    This function acts as a header provider for the MCPToolset. It injects both
    the Google Identity token (for service-to-service auth) and the user's
    Looker OAuth token (for user-level authorization).

    Args:
        context (ReadonlyContext): The ADK ReadonlyContext for the agent call.

    Returns:
        dict: A dictionary of headers including 'Authorization' and 'X-Looker-Token'.
    """
    # 1. Get the Looker OAuth token from context var
    looker_token = get_access_token()

    headers = {}

    if looker_token is not None:
        logging.info("[header_provider] Injecting X-Looker-Token header.")
        headers["X-Looker-Token"] = f"token {looker_token}"
    else:
        logging.warning("[header_provider] Looker token missing.")

    # 2. Get the GCP identity token for the Cloud Run MCP server
    logging.info("Generating a new GCP ID token...")
    id_token = get_id_token()

    if id_token:
        headers["Authorization"] = f"Bearer {id_token}"
    else:
        logging.warning("GCP ID token fetch failed.")

    return headers


# Initialize the Model
# Configure the model using MCP settings from environment variables.
model = Gemini(model_name=os.getenv("MCP_SERVER_MODEL", "gemini-3-flash-preview"))

# Define the Looker Agent
# This agent acts as the primary orchestrator for Looker data operations.
root_agent = Agent(
    name="looker_agent",
    description="Specialized agent for Looker data operations, querying DASHBOARDS, and exploring data.",
    model=model,
    instruction="""You are a specialized Looker assistant. 
You help users query data, understand dashboards, and perform actions in Looker.

Be concise and focus on Looker data.""",
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
            thinking_budget=int(os.getenv("MCP_THINKING_BUDGET", 1024)),
        )
    )
)

# def create_mcp_toolset_with_token(token: str) -> MCPToolset:
#     """Create an MCPToolset with the current user's authentication token."""
#     return MCPToolset(
#         connection_params=StdioConnectionParams(
#             server_params=StdioServerParameters(
#                 command="./toolbox",
#                 args=["--stdio", "--prebuilt", "looker"],
#                 env={
#                     "LOOKER_BASE_URL": "https://looker.cloud.google.com",
#                     "X-Looker-Token": token,
#                 }
#             )
#         )
#     )

# # Usage
# current_token = get_current_user_token()
# toolset = create_mcp_toolset_with_token(current_token)
