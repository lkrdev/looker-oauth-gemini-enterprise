# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Package exports for the Looker GE agent."""

import os
from dotenv import load_dotenv

# Load environment variables (e.g. from .env file)
load_dotenv()

# Supported agent types:
# - "mcp": Looker MCP Agent (looker_mcp_agent)
# - "ca_api": direct Gemini Data Analytics CA API Agent (ca_api_agent)
# - "ca_native": Looker Conversational Analytics Native SDK Agent (looker_ca_native_agent)
agent_type = os.getenv("DEPLOY_AGENT_TYPE", "ca_native").lower()

if agent_type == "mcp":
    from looker_ge_agent.looker_mcp_agent.agent import root_agent
elif agent_type == "ca_api":
    from looker_ge_agent.ca_api_agent.agent import root_agent
else:
    from looker_ge_agent.looker_ca_native_agent.agent import root_agent

__all__ = ["root_agent"]
