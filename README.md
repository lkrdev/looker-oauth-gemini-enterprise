# Looker MCP Agent (Reasoning Engine)

This repository contains a specialized AI agent designed to interact with Looker using the **Model Context Protocol (MCP)**. The agent is deployed as a **Vertex AI Reasoning Engine** agent.

## Architecture Overview

The application is built on the **Google Python ADK** and exposes a Looker-integrated agent that utilizes a remote MCP server for tool execution.

### Core Components:
- **`looker_ge_agent/`**: Acts as the main entrypoint module. It serves the `root_agent` and by default serves the Looker MCP agent.
- **`looker_mcp_agent/`**: Contains the core agent logic and ADK setup.
- **`deploy.sh` & `deployment/deploy.py`**: Deployment scripts for building the agent and deploying it to Vertex AI Reasoning Engine.
- **`scripts/`**: Utility scripts for GCP and Gemini Enterprise (AgentSpace) registration.
- **`archive/`**: Contains older legacy A2A streaming architectural implementations.

## Developer Quickstart

### 1. Prerequisites
- Python 3.12+
- `uv` for dependency management.
- Access to a Looker instance and a deployed MCP server (Toolbox).
- `gcloud` CLI installed and authenticated.

### 2. Environment Setup
Create a `.env` file in the root directory (copy the fields required from the previous configuration):

```bash
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=<your-project-id>-adk-staging

# Looker Credentials (if needed by your tools natively or injected)
LOOKERSDK_BASE_URL=https://<your-instance>.cloud.looker.com
LOOKERSDK_CLIENT_ID=<api3-client-id>
LOOKERSDK_CLIENT_SECRET=<api3-client-secret>
LOOKER_OAUTH_CLIENT_ID=<oauth-client-id>
LOOKER_OAUTH_CLIENT_SECRET=<oauth-client-secret>

# MCP Config
MCP_SERVER_URL=https://<your-mcp-server-url>/mcp
MCP_SERVER_MODEL=gemini-3-flash-preview

# Gemini Enterprise / Agentspace Registration Settings
AGENT_ID=<AGENT_ID>
AUTH_ID=<AUTH_ID>
GE_ENGINE_ID=<GE_ENGINE_ID>
REASONING_ENGINE_ID=<REASONING_ENGINE_ID>
```

### 3. First-Time Setup Order

If this is your first time setting up the project, you must follow this exact order of operations:
1. **Looker OAuth Client Setup:** `make register-oauth-client`
2. **GE OAuth Setup:** `make setup-oauth`
3. **Deploy ADK Agent:** `make deploy` (Once deployed, add the output `REASONING_ENGINE_ID` to your `.env` file)
4. **Register Agent in GE:** `make register-adk`

### 4. Build & Deploy

You can deploy the agent to Vertex AI Reasoning Engine by running:
```bash
make deploy
```
*Note: Ensure you have populated `.env` and authenticated with gcloud before deploying. After deployment, the script prints the `REASONING_ENGINE_ID` that was generated. You MUST copy this ID and place it into your `.env` file for registration.*

### 5. Registration & Patching

Once the agent is deployed and you have updated the `REASONING_ENGINE_ID` in your `.env` file, you can register or patch it to Gemini Enterprise/AgentSpace.

To register a completely new agent:
```bash
make register-adk
```

To update an already registered agent with a new reasoning engine (patching):
```bash
make patch-adk
```

## OAuth Setup

To configure Gemini Enterprise OAuth for Looker:
```bash
make setup-oauth
```

### OAuth Flow & Token Access

1. **Authentication**: Gemini Enterprise (GE) initiates an OAuth flow with Looker using the configured `LOOKER_OAUTH_CLIENT_ID`.
2. **Context Injection**: Once authenticated, GE successfully retrieves a Looker access token and passes it to the deployed Vertex AI Reasoning Engine (ADK Agent). The token is automatically injected into the ADK agent's `InvocationContext` (available in `ctx.state` or `ctx.session.state`).
3. **Token Retrieval**: The token is injected into the state under a key that corresponds to the `AUTH_ID` environment variable configured during agent registration. The ADK agent retrieves this token at runtime by looking up `os.getenv("AUTH_ID")` (e.g., in `ca_query.py` or `agent.py's` header configuration routines).
