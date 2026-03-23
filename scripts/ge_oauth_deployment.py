import os
import json
import urllib.parse
import argparse
import google.auth
from google.auth.transport.requests import Request
import requests

def main():
    parser = argparse.ArgumentParser(description="Configure Gemini Enterprise OAuth for Looker")
    parser.add_argument("--project-id", help="GCP Project ID", default=os.environ.get("PROJECT_ID", "looker-demo-392616"))
    parser.add_argument("--auth-id", help="Authorization ID", default=os.environ.get("AUTH_ID", "looker-pkce-auth-new"))
    parser.add_argument("--client-id", help="Looker Client ID", default=os.environ.get("LOOKER_CLIENT_ID", "ge-integration"))
    parser.add_argument("--client-secret", help="Looker Client Secret", default=os.environ.get("LOOKER_CLIENT_SECRET", "LOOKER_DOES_NOT_USE_SECRET_IN_THIS_FLOW"))
    parser.add_argument("--instance-url", help="Looker Instance URL", default=os.environ.get("LOOKER_INSTANCE_URL", "https://googledemo2.cloud.looker.com"))
    parser.add_argument("--scopes", help="Space-separated OAuth scopes", default=os.environ.get("SCOPES", "cors_api"))
    args = parser.parse_args()

    scopes_encoded = urllib.parse.quote(args.scopes)
    authorization_uri = f"{args.instance_url}/auth?client_id={args.client_id}&scope={scopes_encoded}&response_type=code&code_challenge_method=S256"
    token_uri = f"{args.instance_url}/api/token"

    print("Fetching GCP credentials...")
    try:
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        print(f"Error fetching GCP credentials: {e}")
        print("Please ensure you are authenticated (e.g., 'gcloud auth login' and 'gcloud auth application-default login').")
        return

    url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{args.project_id}/locations/global/authorizations?authorizationId={args.auth_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    payload = {
        "name": f"projects/{args.project_id}/locations/global/authorizations/{args.auth_id}",
        "serverSideOauth2": {
            "clientId": args.client_id,
            "clientSecret": args.client_secret,
            "authorizationUri": authorization_uri,
            "tokenUri": token_uri,
            "pkce_verification_enabled": True
        }
    }

    print(f"Registering OAuth config '{args.auth_id}' in project '{args.project_id}'...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code >= 400:
        print(f"Error ({response.status_code}): {response.text}")
        response.raise_for_status()

    print("Success:")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    main()
