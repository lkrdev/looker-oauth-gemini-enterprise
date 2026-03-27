import os
import sys
import json
import argparse
import requests

def main():
    """
    Registers an OAuth Client Application using the Looker REST API.
    
    This script requires four environment variables:
    - LOOKERSDK_BASE_URL: The base Looker URL (e.g., https://myinstance.cloud.looker.com)
    - LOOKERSDK_CLIENT_ID: API3 Client ID for authentication
    - LOOKERSDK_CLIENT_SECRET: API3 Client Secret for authentication
    - LOOKER_OAUTH_CLIENT_ID: The desired GUID for the new OAuth App
    """
    parser = argparse.ArgumentParser(description="Create a Looker OAuth Client App via REST API")
    args = parser.parse_args()

    base_url = os.environ.get("LOOKERSDK_BASE_URL")
    if not base_url:
        print("Error: LOOKERSDK_BASE_URL environment variable is missing.")
        sys.exit(1)
        
    client_id = os.environ.get("LOOKERSDK_CLIENT_ID")
    client_secret = os.environ.get("LOOKERSDK_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: LOOKERSDK_CLIENT_ID and LOOKERSDK_CLIENT_SECRET must be set for authentication.")
        sys.exit(1)
        
    oauth_client_id = os.environ.get("LOOKER_OAUTH_CLIENT_ID")
    if not oauth_client_id:
        print("Error: LOOKER_OAUTH_CLIENT_ID must be set.")
        sys.exit(1)

    # Clean the base URL and ensure it has the API 4.0 path extension
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/api/4.0"):
        api_url = f"{base_url}/api/4.0"
    else:
        api_url = base_url

    print(f"Authenticating with Looker at {api_url}/login...")
    login_payload = {
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    # Send credentials to /login to establish session and get bearer token
    login_response = requests.post(f"{api_url}/login", data=login_payload)
    if login_response.status_code != 200:
        print(f"Failed to authenticate: {login_response.status_code} {login_response.text}")
        sys.exit(1)
        
    token_data = login_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        print("Authentication successful, but no access_token returned.")
        sys.exit(1)

    print(f"Authentication successful. Creating OAuth Client App with GUID: {oauth_client_id}...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # The configuration you explicitly requested for the OAuth app
    app_payload = {
        "redirect_uri": "https://vertexaisearch.cloud.google.com/oauth-redirect",
        "display_name": "Looker Agent",
        "description": "a Looker Agent that connects to an MCP server or Conversational Analytics API",
        "enabled": True
    }
    
    # Hitting the specific client GUID instantiation route
    register_url = f"{api_url}/oauth_client_apps/{oauth_client_id}"
    register_response = requests.post(register_url, headers=headers, json=app_payload)
    
    if register_response.status_code >= 400:
        print(f"Error ({register_response.status_code}): {register_response.text}")
        sys.exit(1)
        
    print("Successfully registered OAuth Client App:")
    print(json.dumps(register_response.json(), indent=2))

if __name__ == "__main__":
    main()
