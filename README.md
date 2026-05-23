# Looker Agents in Gemini Enterprise

This repository contains 3 sample agents designed to interact with Looker using either the Conversational Analytics API in GCP, **Model Context Protocol (MCP)** through the OSS MCP Toolbox for Databases (default) OR the Looker Native Conversational Analytics API. The agent is deployed as a **Vertex AI Agent Engine** agent.

## Architecture Overview

The application is built on the **Google Python ADK** and exposes a Looker-integrated agent.

### Core Components:
- **`looker_ge_agent/`**: Acts as the main entrypoint module. It dynamically exposes the `root_agent` based on the `DEPLOY_AGENT_TYPE` environment variable, allowing developers to switch between the agent configurations without modifying code.
  - **`looker_ca_native_agent/`**: Contains the Looker Conversational Analytics Native SDK agent.
  - **`ca_api_agent/`**: Contains the direct Gemini Data Analytics CA API agent.
  - **`looker_mcp_agent/`**: Contains the Model Context Protocol (MCP) Looker agent.
- **`deploy.sh` & `deployment/deploy.py`**: Deployment scripts for building the agent and deploying it to Vertex AI Reasoning Engine.
- **`scripts/`**: Utility scripts for GCP and Gemini Enterprise (AgentSpace) registration.
- **`archive/`**: Contains older legacy A2A streaming architectural implementations.

### Agent Types

You can switch between three different agent types by setting the `DEPLOY_AGENT_TYPE` environment variable in your `.env` file:

1. **Looker CA Native SDK Agent (`DEPLOY_AGENT_TYPE=ca_native` - Default)**
   - **Description**: Leverages Looker's Conversational Analytics streaming API using the Python Looker SDK under the hood.
   - **Key Configurations**: Uses `LOOKER_CA_AGENT_ID` (preconfigured on the Looker side). Supports exiting the streaming pipeline early after formatting raw data (via `RAW_RESULTS=True` in `constants.py`).
   - **Relevant Directory**: `looker_ge_agent/looker_ca_native_agent/`

2. **Looker Direct CA API Agent (`DEPLOY_AGENT_TYPE=ca_api`)**
   - **Description**: Communicates directly with the Google Cloud Gemini Data Analytics API.
   - **Key Configurations**: Builds an inline context using explicit `LOOKML_MODEL` and `LOOKML_EXPLORE` parameters to request direct data execution.
   - **Relevant Directory**: `looker_ge_agent/ca_api_agent/`

3. **Looker MCP Agent (`DEPLOY_AGENT_TYPE=mcp`)**
   - **Description**: Interacts with Looker via the Model Context Protocol (MCP) to run database queries and explore endpoints.
   - **Key Configurations**: Connects to a remote/external MCP server via `MCP_SERVER_URL` using `MCP_SERVER_MODEL` and `MCP_THINKING_BUDGET` definitions.
   - **Relevant Directory**: `looker_ge_agent/looker_mcp_agent/`


## Developer Quickstart

### 1. Prerequisites

#### **Global Requirements (All Agent Types)**
- **Python 3.12+**
- **`uv`** for dependency and virtual environment management.
- **`gcloud` CLI** installed, configured, and authenticated to your target GCP project.
- **Gemini Enterprise (AgentSpace) Instance** configured with deployment access.
- **Access to a Looker Instance** (requires Looker instance credentials or configured OAuth connection).

#### **Agent-Specific Requirements**

* **Looker CA Native SDK Agent (`DEPLOY_AGENT_TYPE=ca_native` - Default)**
  - **Looker CA Native Agent Setup**: A preconfigured native agent ID (`LOOKER_CA_AGENT_ID`) set up in your Looker instance's Conversational Analytics panel.

* **Looker Direct CA API Agent (`DEPLOY_AGENT_TYPE=ca_api`)**
  - **GCP Gemini Data Analytics API**: Direct access to GCP's `DataChatService` enabled under the Google Cloud project.

* **Looker MCP Agent (`DEPLOY_AGENT_TYPE=mcp`)**
  - **Deployed MCP Server**: A deployed instance of the [MCP Toolbox for Databases (OSS)](https://github.com/googleapis/genai-toolbox) or another SQL database MCP server.
  - **Service Account Permissions**: If the MCP server is deployed to Cloud Run and is private, your Reasoning Engine's GCP Service Account needs the **Cloud Run Invoker** (`roles/run.invoker`) role.
  - **OAuth Header Configuration**: Ensure your Looker source in the MCP Toolbox `tools.yaml` file accepts the token injected by the ADK agent:
    ```yaml
    looker-source:
      kind: looker
      base_url: https://myinstance.cloud.looker.com
      use_client_oauth: X-Looker-Token
      verify_ssl: true
      timeout: 600s
    ```

### 2. Environment Setup
Create a `.env` file in the root directory (copy the fields required from the previous configuration):

```bash
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=<your-project-id>-adk-staging

# Agent Deployment Selector
# Choices: "ca_native" (default - Looker CA Native SDK Agent), "ca_api" (direct CA API Agent), or "mcp" (Looker MCP Agent)
DEPLOY_AGENT_TYPE=ca_native

# Looker Connection & Credentials
LOOKERSDK_BASE_URL=https://<your-instance>.cloud.looker.com
LOOKERSDK_VERIFY_SSL=True
LOOKERSDK_CLIENT_ID=<api3-client-id>
LOOKERSDK_CLIENT_SECRET=<api3-client-secret>
LOOKER_OAUTH_CLIENT_ID=<oauth-client-id>
LOOKER_OAUTH_CLIENT_SECRET=<oauth-client-secret>

# Looker Conversational Analytics (CA) Settings
LOOKML_MODEL=<lookml-model-name> # e.g., thelook
LOOKML_EXPLORE=<lookml-explore-name> # e.g., order_items
LOOKER_CA_AGENT_ID=<ca-agent-id> # Alternate/specific ID for Conversational Analytics native agent sessions

# MCP Config
MCP_SERVER_URL=https://<your-mcp-server-url>/mcp
MCP_SERVER_MODEL=gemini-3-flash-preview
MCP_THINKING_BUDGET=1024

# Gemini Enterprise / Agentspace Registration Settings
AGENT_ID=<AGENT_ID>
AGENT_DISPLAY_NAME=Looker Agent # User-friendly name in Gemini Enterprise UI
# AGENT_ICON_URI=https://path-to-logo.svg/png # Optional public SVG/PNG or GCS URI for custom icon
AUTH_ID=<AUTH_ID>
GE_ENGINE_ID=<GE_ENGINE_ID>
REASONING_ENGINE_ID=<REASONING_ENGINE_ID>

# Telemetry / Observability Settings (defaults to true)
GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
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

## Observability, Telemetry & Custom Metadata

### Telemetry & Tracing
OpenTelemetry instrumentation is enabled by default inside the deployed Reasoning Engine, populating standard "Traces" and "Logs" in the Vertex AI GCP console. You can toggle these variables inside your `.env`:
* **`GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY`** (defaults to `true`): Set to `false` to disable active OpenTelemetry status metrics.
* **`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`** (defaults to `true`): Set to `false` to prevent raw prompt text and message body parameters from being stored inside logs (sensitive contents filter).

### Custom Display Name & Icon in Gemini Enterprise
You can override default/technical identifiers in the chat UI by configuring presentation metadata:
* **`AGENT_DISPLAY_NAME`**: Set to a user-friendly name (e.g., `Looker Analyst`) to display in place of the generic `AGENT_ID` in the chat window.
* **`AGENT_ICON_URI`**: (Optional) Set to a public SVG/PNG link or a GCS path to customize the agent's profile icon. If omitted, no icon parameter is sent, and Gemini Enterprise's default avatar is applied.
* Both properties are dynamically managed and updated on GAE whenever you execute a `make patch-adk` or `make register-adk` action.

## OAuth Setup

To configure Gemini Enterprise OAuth for Looker:
```bash
make setup-oauth
```

### OAuth Flow & Token Access

1. **Authentication**: Gemini Enterprise (GE) initiates an OAuth flow with Looker using the configured `LOOKER_OAUTH_CLIENT_ID`.
2. **Context Injection**: Once authenticated, GE successfully retrieves a Looker access token and passes it to the deployed Vertex AI Reasoning Engine (ADK Agent). The token is automatically injected into the ADK agent's `Context` (available in `state` or `session.state`).
3. **Token Retrieval**: The token is injected into the state under a key that corresponds to the `AUTH_ID` environment variable configured during agent registration. The ADK agent retrieves this token at runtime by looking up `os.getenv("AUTH_ID")` (e.g., in `ca_query.py` or `agent.py's` header configuration routines).
