# Looker to Gemini Enterprise A2A Integration (MCP Edition)

This guide walks through the token flow and deployment steps required to connect a Google Python ADK Agent (using the Looker MCP Toolset) as an A2A Agent inside Gemini Enterprise.

In this architecture, Gemini Enterprise handles Looker OAuth directly via a PKCE flow and passes the token down to the ADK Agent, which then forwards it to a specialized MCP server.

## Token Flow

The end-to-end token flow ensures the user's Looker identity is passed securely from Gemini Enterprise down to Looker tools:

1. **User Auth**: The user prompts the agent in Gemini Enterprise. If they haven't authenticated to Looker, Gemini Enterprise initiates an OAuth PKCE flow against the Looker instance.
2. **A2A Invocation**: Gemini Enterprise calls the public A2A Cloud Run endpoint for the agent. It injects the Looker OAuth Bearer token into the `Authorization` header.
3. **Token Extraction**: In the agent's Cloud Run service (`a2a_main.py`), the `HeaderLoggerMiddleware` extracts the Bearer token and saves it to an async context variable (`request_bearer_token`).
4. **MCP Tool Call**: The Looker MCP Agent (`looker_mcp_agent/agent.py`) retrieves this token and injects it into the `X-Looker-Token` header.
5. **GCP Identity**: Simultaneously, the agent generates a GCP ID token and injects it into the `Authorization: Bearer` header for secure communication with the MCP server.
6. **Tool Execution**: The MCP server validates the identity, uses the Looker token to perform actions, and returns results which are streamed back to Gemini Enterprise.

---

## Deployment Steps

### 1. Looker OAuth Client Setup
1. In Looker: **Admin > Platform Services > OAuth**.
2. **Create Application** with **PKCE enabled**.
3. Redirect URI: `https://vertexaisearch.cloud.google.com/oauth-redirect`.
4. Note the **OAuth Client ID**.

### 2. Gemini Enterprise Authorization Resource Setup
Use the `Makefile` and `.env` to create the Authorization Resource:

```bash
# Update .env with your IDs
PROJECT_ID="<your-project-id>"
AUTH_ID="looker-pkce-auth"
LOOKER_CLIENT_ID="<OAuth Client ID>"
LOOKER_INSTANCE_URL="https://your-instance.cloud.looker.com"

# Run the setup
make setup-oauth
```

### 3. A2A Agent Deployment
Deploy the service to Cloud Run:

```bash
make deploy-a2a
```
*Note: The service must be `--allow-unauthenticated` as we handle auth via the passed bearer token.*

### 4. Agent Registration
Register the agent with the Discovery Engine:

```bash
# Build, deploy, and register in one command
make deploy-register-a2a
```

Once successful, the agent is live in Gemini Enterprise!
