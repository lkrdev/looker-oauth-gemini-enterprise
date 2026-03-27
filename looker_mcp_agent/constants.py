import os
from dotenv import load_dotenv

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "<your-mcp-server-url>")
LOOKER_AUTH_STATE_KEY = os.getenv("LOOKER_AUTH_STATE_KEY", "<your-auth-state-key>")
DEFAULT_MCP_SERVER_MODEL = os.getenv("MCP_SERVER_MODEL", "<your-model-name>")
