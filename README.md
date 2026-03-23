# Looker MCP Agent (A2A Streaming)

This repository contains a specialized AI agent designed to interact with Looker using the **Model Context Protocol (MCP)** and the **A2A (Agent-to-A2A)** streaming protocol.

## Architecture Overview

The application is built on the **Google Python ADK** and exposes a Looker-integrated agent that utilizes a remote MCP server for tool execution.

### Core Components:
- **`looker_mcp_agent/`**: Contains the core agent logic, authentication context, and middleware.
- **`a2a_main.py`**: The entry point for the application, handling A2A compliance and server execution.
- **`scripts/`**: Deployment and utility scripts for GCP and Gemini Enterprise registration.

## Developer Quickstart

### 1. Prerequisites
- Python 3.12+
- `uv` for dependency management.
- Access to a Looker instance and a deployed MCP server (Toolbox).

### 2. Environment Setup
Create a `.env` file in the root directory:

```bash
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=us-central1

# Looker OAuth Credentials
LOOKERSDK_BASE_URL=https://<your-instance>.cloud.looker.com
LOOKERSDK_CLIENT_ID=<oauth-client-id>
LOOKERSDK_CLIENT_SECRET=<oauth-client-secret>

# MCP Config
MCP_SERVER_URL=https://<your-mcp-server-url>/mcp
MCP_SERVER_MODEL=gemini-3-flash-preview
MCP_THINKING_BUDGET=1024

# A2A Config
A2A_AGENT_URL=https://<your-deployed-service-url>
```

### 3. Local Development
Install dependencies and start the ADK server:

```bash
uv sync
uv run a2a_main.py
```

## Deployment

### Makefile Commands
The project includes a `Makefile` to simplify common tasks:

- **`make deploy-a2a`**: Builds the Docker image and deploys to Google Cloud Run.
- **`make register-a2a`**: Registers the deployed service as an agent in Gemini Enterprise.
- **`make deploy-register-a2a`**: Performs both steps sequentially.

## Authentication Flow

1. **Inbound**: The `HeaderLoggerMiddleware` extracts the Bearer token from the incoming A2A request.
2. **Context**: The token is stored in a `ContextVar` (`request_bearer_token`).
3. **Outbound**: The `looker_mcp_agent` retrieves this token and injects it into the `X-Looker-Token` header when calling the MCP server.
4. **GCP Identity**: The agent also generates a GCP ID token for secure communication with the MCP server via the `Authorization: Bearer <ID_TOKEN>` header.
