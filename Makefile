# Makefile for ADK Agent Deployment and Registration

# Load environment variables if .env exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: help deploy-a2a register-a2a patch-a2a deploy-register-a2a setup-oauth

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

deploy-a2a: ## Build and deploy the A2A agent to Cloud Run
	./scripts/deploy_a2a.sh

register-a2a: ## Register the deployed Cloud Run URL with Gemini Enterprise as an Agent
	python3 scripts/register_agent.py --action create

patch-a2a: ## Update an existing A2A agent's configuration in Gemini Enterprise
	python3 scripts/register_agent.py --action patch

deploy-register-a2a: deploy-a2a register-a2a ## Deploy to Cloud Run and then Register

setup-oauth: ## Configure Gemini Enterprise OAuth for Looker
	python3 scripts/ge_oauth_deployment.py

