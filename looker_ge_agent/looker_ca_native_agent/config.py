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

"""Centralized environment configuration module."""

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings parsed and validated from the environment."""

    @property
    def auth_id_key(self) -> str:
        """The state key identifying where the bearer auth token is stored."""
        return os.getenv("AUTH_ID", "token")

    @property
    def lookersdk_base_url(self) -> str:
        """The base URL for the Looker API instance."""
        return os.getenv("LOOKERSDK_BASE_URL", "")

    @property
    def looker_ca_agent_id(self) -> str:
        """The Looker CA native agent ID used for session creations."""
        return os.getenv("LOOKER_CA_AGENT_ID") or os.getenv("AGENT_ID", "")

    @property
    def verify_ssl(self) -> bool:
        """Whether to verify SSL certs on the Looker SDK connection."""
        val = os.getenv("LOOKERSDK_VERIFY_SSL", "True")
        return val.lower() in ("true", "1", "yes")

    @property
    def local_dev_token(self) -> str | None:
        """Optional token override specifically for local testing purposes.
        
        Read from local env or a secure dev key if populated.
        """
        return os.getenv("LOOKERSDK_ACCESS_TOKEN") or os.getenv("LOCAL_DEV_TOKEN")


settings = Settings()
