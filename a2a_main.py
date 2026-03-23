"""Entry point for running the A2A agent on Cloud Run."""
import os
from dotenv import load_dotenv
import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from a2a.types import AgentCard

from looker_mcp_agent.agent import root_agent
from looker_mcp_agent.auth_context import request_bearer_token

import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cloud Run sets the PORT environment variable, which defaults to 8080 locally if not set.
# The port is required by to_a2a() to correctly generate the agent card endpoint URL.
port = int(os.environ.get("PORT", 8080))

# Define A2A agent card
my_agent_card = AgentCard(
    name="root_agent",
    url=os.environ.get("A2A_AGENT_URL"),
    description="Specialized agent for Looker data operations, querying DASHBOARDS, and exploring data.",
    version="0.0.1",
    capabilities={
        "streaming": True
    },
    skills=[
        {
            "description": "Specialized agent for Looker data operations, querying DASHBOARDS, and exploring data.",
            "id": "root_agent",
            "name": "custom",
            "tags": ["custom_agent"]
        }
    ],
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain"],
    supportsAuthenticatedExtendedCard=False,
)

# Convert the root_agent into an A2A compliant app.
a2a_app = to_a2a(root_agent, port=port, agent_card=my_agent_card)
# a2a_app = to_a2a(root_agent, port=port)


from looker_mcp_agent.middleware import HeaderLoggerMiddleware

# Wrap a2a_app with the logging middleware
a2a_app = HeaderLoggerMiddleware(a2a_app)

if __name__ == "__main__":
    # Start the application using Uvicorn. 
    # Listens on all interfaces (0.0.0.0) which is required for Cloud Run containers.
    uvicorn.run("a2a_main:a2a_app", host="0.0.0.0", port=port)
