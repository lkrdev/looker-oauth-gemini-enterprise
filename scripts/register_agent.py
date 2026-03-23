import os
import json
import subprocess
import argparse
import google.auth
from google.auth.transport.requests import Request
import requests

def get_cloud_run_url(service_name, region):
    print(f"Fetching Cloud Run URL for service '{service_name}' in region '{region}'...")
    try:
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", service_name, "--region", region, "--format=value(status.url)"],
            capture_output=True, text=True, check=True
        )
        url = result.stdout.strip()
        if not url:
            raise ValueError("URL is empty.")
        return url
    except Exception as e:
        print(f"Error getting Cloud Run URL: {e}")
        if isinstance(e, subprocess.CalledProcessError):
            print(f"gcloud error: {e.stderr}")
        return None

def get_project_number(project_id):
    result = subprocess.run(
        ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser(description="Register an ADK agent with Gemini Enterprise (Agentspace)")
    parser.add_argument("--action", choices=["create", "patch"], default="create", help="Whether to create or patch the agent")
    parser.add_argument("--service-name", help="Cloud run service name", default=os.environ.get("SERVICE_NAME", "looker-a2a-agent"))
    parser.add_argument("--region", help="Cloud run region", default=os.environ.get("REGION", "us-central1"))
    parser.add_argument("--auth-id", help="Authorization ID", default="looker-pkce-auth-new")
    parser.add_argument("--engine-id", help="Agentspace Engine ID", default="gemini-enterprise-17653237_1765323744630")
    parser.add_argument("--agent-id", help="The name of the agent to register", default="orchestrator_agent")
    args = parser.parse_args()

    print("Fetching default project and GCP credentials...")
    try:
        credentials, project_id = google.auth.default()
        if not project_id:
            result = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=True)
            project_id = result.stdout.strip()
        
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        print(f"Error fetching GCP credentials: {e}")
        print("Please ensure you are authenticated (e.g., 'gcloud auth login' and 'gcloud auth application-default login').")
        return

    project_number = get_project_number(project_id)

    cloud_run_url = get_cloud_run_url(args.service_name, args.region)
    if not cloud_run_url:
        print("Failed to fetch Cloud Run URL. Aborting.")
        return
    print(f"Using Cloud Run URL: {cloud_run_url}")

    # Read raw_agent_card.json from project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_card_path = os.path.join(base_dir, "raw_agent_card.json")

    print(f"Reading agent card from {raw_card_path}")
    try:
        with open(raw_card_path, "r") as f:
            agent_card = json.load(f)
    except FileNotFoundError:
        print(f"Could not find {raw_card_path}. Make sure it exists in the root directory.")
        return

    # Modify agent card
    if "capabilities" not in agent_card:
        agent_card["capabilities"] = {}
    agent_card["capabilities"]["streaming"] = True
    agent_card["url"] = cloud_run_url

    card_string = json.dumps(agent_card, indent=2)

    # Format agent payload
    payload = {
        "displayName": args.agent_id,
        "description": "An ADK Agent",
        "authorizationConfig": {
            "agentAuthorization": f"projects/{project_number}/locations/global/authorizations/{args.auth_id}"
        },
        "a2aAgentDefinition": {
            "jsonAgentCard": card_string
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    base_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_number}/locations/global/collections/default_collection/engines/{args.engine_id}/assistants/default_assistant/agents"

    print(f"{args.action.capitalize()}ing agent '{args.agent_id}' in project '{project_id}' ({project_number})...")
    
    if args.action == "create":
        # POST to agents endpoint (agents?agentId=...)
        url = f"{base_url}?agentId={args.agent_id}"
        response = requests.post(url, headers=headers, json=payload)
    else:
        # PATCH to agents/{agent_id} endpoint
        # The name must be in the payload for patching
        payload["name"] = f"projects/{project_number}/locations/global/collections/default_collection/engines/{args.engine_id}/assistants/default_assistant/agents/{args.agent_id}"
        url = f"{base_url}/{args.agent_id}"
        response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code >= 400:
        print(f"Error ({response.status_code}): {response.text}")
        response.raise_for_status()

    print("Success:")
    print(json.dumps(response.json(), indent=2))
    
    # Write back the generated JSON for debugging/audit purposes
    out_card_path = os.path.join(base_dir, "agent_card.json")
    with open(out_card_path, "w") as f:
        f.write(card_string)
    out_payload_path = os.path.join(base_dir, "agentspace_payload.json")
    with open(out_payload_path, "w") as f:
        json.dump(payload, f, indent=2)

if __name__ == "__main__":
    main()
