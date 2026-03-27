import os
from dotenv import load_dotenv

load_dotenv()

DISCOVERY_ENGINE_BASE_URL = os.getenv(
    "DISCOVERY_ENGINE_BASE_URL",
    "https://discoveryengine.googleapis.com/v1alpha/projects"
)
