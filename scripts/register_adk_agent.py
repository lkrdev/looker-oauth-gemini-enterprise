import os
import json
import subprocess
import argparse
import google.auth
from google.auth.transport.requests import Request
import requests

from constants import DISCOVERY_ENGINE_BASE_URL


def get_project_number(project_id):
    """
    Retrieves the numerical Google Cloud project number for a given project ID.
    
    Args:
        project_id (str): The Google Cloud project ID.
        
    Returns:
        str: The corresponding project number, or the project_id if it fails.
    """
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not fetch project number for {project_id} (missing permissions?). Returning project_id instead.")
        return project_id

def main():
    """
    Registers or updates an ADK Reasoning Engine Agent with Gemini Enterprise (Agentspace).

    This script acts as the deployment bridge, associating a provisioned 
    Reasoning Engine ID with Agentspace by creating or patching an agent configuration.
    """
    parser = argparse.ArgumentParser(description="Register a standard ADK agent (Reasoning Engine based) with Gemini Enterprise (Agentspace)")
    parser.add_argument("--action", choices=["create", "patch"], default="create", help="Whether to create or patch the agent")
    parser.add_argument("--auth-id", help="Authorization ID", default=os.environ.get("AUTH_ID", "<your-auth-id>"))
    parser.add_argument("--engine-id", help="Agentspace Engine ID", default=os.environ.get("GE_ENGINE_ID", "<your-engine-id>"))
    parser.add_argument("--agent-id", help="The name of the agent to register", default=os.environ.get("AGENT_ID", "<your-agent-id>"))
    parser.add_argument("--display-name", help="Display name for GE registration", default=os.environ.get("AGENT_DISPLAY_NAME", os.environ.get("AGENT_ID", "Looker Agent")))
    parser.add_argument("--reasoning-engine-id", help="The reasoning engine ID (e.g. projects/.../locations/.../reasoningEngines/...)", required=True)
    parser.add_argument("--project-id", help="Optional GCP project ID to override default auth", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    args = parser.parse_args()

    print("Fetching GCP credentials...")
    try:
        credentials, project_id = google.auth.default()
        if args.project_id:
            project_id = args.project_id
        if not project_id:
            result = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=True)
            project_id = result.stdout.strip()
        
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        print(f"Error fetching GCP credentials: {e}")
        print("Please ensure you are authenticated (e.g., 'gcloud auth login' and 'gcloud auth application-default login').")
        return

    # Try to extract the project number from reasoning_engine_id: projects/NUMBER/locations/...
    project_number = None
    if args.reasoning_engine_id.startswith("projects/"):
        parts = args.reasoning_engine_id.split("/")
        if len(parts) > 1 and parts[1].isdigit():
            project_number = parts[1]
            print(f"Extracted project number {project_number} directly from reasoning engine ID.")

    if not project_number:
        project_number = get_project_number(project_id)

    # Format agent payload
    payload = {
        "displayName": args.display_name,
        "description": "An ADK Reasoning Engine Agent",
        "icon": {
            "uri": os.environ.get("AGENT_ICON_URI", "https://raw.githubusercontent.com/brettguenther/looker-custom-embed-navigation-extension/refs/heads/main/looker-color-img.svg")
        },
        "authorizationConfig": {
            "agentAuthorization": f"projects/{project_number}/locations/global/authorizations/{args.auth_id}",
            "toolAuthorizations": [
                f"projects/{project_number}/locations/global/authorizations/{args.auth_id}"
            ]
        },
        "adkAgentDefinition": {
            "provisionedReasoningEngine": {
                "reasoningEngine": args.reasoning_engine_id
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    base_url = f"{DISCOVERY_ENGINE_BASE_URL}/{project_number}/locations/global/collections/default_collection/engines/{args.engine_id}/assistants/default_assistant/agents"

    print(f"{args.action.capitalize()}ing ADK agent '{args.agent_id}' using reasoning engine '{args.reasoning_engine_id}' in project '{project_id}' ({project_number})...")
    
    if args.action == "create":
        # POST to agents endpoint (agents?agentId=...)
        url = f"{base_url}?agentId={args.agent_id}"
        response = requests.post(url, headers=headers, json=payload)
    else:
        # PATCH to agents/{agent_id} endpoint
        # The name must be in the payload for patching
        payload["name"] = f"projects/{project_number}/locations/global/collections/default_collection/engines/{args.engine_id}/assistants/default_assistant/agents/{args.agent_id}"
        url = f"{base_url}/{args.agent_id}?updateMask=adkAgentDefinition,authorizationConfig,displayName,icon"
        response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code >= 400:
        print(f"Error ({response.status_code}): {response.text}")
        response.raise_for_status()

    print("Success:")
    print(json.dumps(response.json(), indent=2))
    
    # Write back the generated JSON payload for debugging/audit purposes
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_payload_path = os.path.join(base_dir, "agentspace_payload.json")
    with open(out_payload_path, "w") as f:
        json.dump(payload, f, indent=2)

if __name__ == "__main__":
    main()
