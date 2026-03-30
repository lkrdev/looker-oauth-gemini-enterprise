# Makefile for ADK Agent Deployment and Registration

# Load environment variables if .env exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: help deploy setup-oauth register-adk patch-adk register-oauth-client

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

deploy: ## Build and deploy the agent to Vertex AI Reasoning Engine
	./deploy.sh

setup-oauth: ## Configure Gemini Enterprise OAuth for Looker
	python3 scripts/ge_oauth_deployment.py

register-oauth-client: ## Create a Looker OAuth Client API App
	python3 scripts/create_looker_oauth_client.py

register-adk:  ## Register an ADK Reasoning Engine Agent
	@if [ -z "$$REASONING_ENGINE_ID" ]; then echo "Error: REASONING_ENGINE_ID is required"; exit 1; fi
	python3 scripts/register_adk_agent.py --action create --agent-id "$${AGENT_ID:-looker_mcp_agent}" --auth-id "$${AUTH_ID:-looker-pkce-auth}" --reasoning-engine-id "$$REASONING_ENGINE_ID"

patch-adk: ## Update an existing ADK Reasoning Engine Agent
	@if [ -z "$$REASONING_ENGINE_ID" ]; then echo "Error: REASONING_ENGINE_ID is required"; exit 1; fi
	python3 scripts/register_adk_agent.py --action patch --agent-id "$${AGENT_ID:-looker_mcp_agent}" --auth-id "$${AUTH_ID:-looker-pkce-auth}" --reasoning-engine-id "$$REASONING_ENGINE_ID"
