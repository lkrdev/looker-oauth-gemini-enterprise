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

"""Looker Python SDK Client dynamic builder and custom streaming wrapper."""

import json
import logging
from typing import Any, Generator

import looker_sdk
from looker_sdk import api_settings
from looker_sdk.rtl import auth_token
from looker_sdk.sdk.api40 import models as models40

from ..config import settings

logger = logging.getLogger(__name__)


class CustomApiSettings(api_settings.ApiSettings):
    """Custom settings loader to programmatically configure Looker Python SDK."""

    def __init__(self, base_url: str, *args: Any, **kw_args: Any) -> None:
        self._custom_base_url = base_url
        super().__init__(*args, **kw_args)

    def read_config(self) -> api_settings.SettingsConfig:
        config = super().read_config()
        config["base_url"] = self._custom_base_url
        config["client_id"] = "dummy_client_id"
        config["client_secret"] = "dummy_client_secret"
        config["verify_ssl"] = str(settings.verify_ssl)
        return config



class StreamWrapper:
    """Custom streaming wrapper leveraging the SDK's RequestsTransport session."""

    def __init__(self, sdk: looker_sdk.sdk.api40.methods.Looker40SDK) -> None:
        self.sdk = sdk

    def conversational_analytics_chat(
        self, body: models40.ConversationalAnalyticsChatRequest
    ) -> Generator[dict[str, Any], None, None]:
        """Performs streaming POST request to Conversational Analytics chat API.

        Returns a Generator yielding parsed message chunks (SSE events).
        """
        base_url = self.sdk.auth.settings.base_url
        url = f"{base_url}/api/4.0/conversational_analytics/chat"
        token = self.sdk.auth.token.access_token

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Construct dictionary payload from the request body
        payload = {
            "conversation_id": body.conversation_id,
            "user_message": body.user_message,
        }

        logger.info("Sending streaming POST request to: %s", url)
        try:
            response = self.sdk.transport.session.post(
                url,
                json=payload,
                headers=headers,
                stream=True,
            )
            response.raise_for_status()
        except Exception as err:
            logger.error("HTTP connection request failed for Conversational Analytics chat: %s", err)
            raise

        logger.info("Successfully connected to Conversational Analytics stream. Parsing chunks chunk-safely...")
        bracket_count = 0
        current_object_chars = []
        in_string = False
        escape_char = False

        def char_generator() -> Generator[str, None, None]:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    for char in decoded_chunk:
                        yield char

        for char in char_generator():
            if not in_string:
                if char == "[":
                    if bracket_count == 0 and not current_object_chars:
                        continue
                elif char == "]":
                    if bracket_count == 0:
                        continue
                elif char == ",":
                    if bracket_count == 0 and not current_object_chars:
                        continue
                if not current_object_chars and char.isspace():
                    continue

            current_object_chars.append(char)

            if char == '"' and not escape_char:
                in_string = not in_string

            if in_string:
                if char == '\\' and not escape_char:
                    escape_char = True
                else:
                    escape_char = False
            else:
                if char == "{":
                    bracket_count += 1
                elif char == "}":
                    bracket_count -= 1

            if bracket_count == 0 and current_object_chars:
                full_json_str = "".join(current_object_chars).strip()
                if full_json_str:
                    try:
                        yield json.loads(full_json_str)
                    except Exception as err:
                        logger.warning("Failed to parse accumulated stream JSON: %r. Error: %s", full_json_str, err)
                current_object_chars = []


def get_looker_sdk(base_url: str, token: str) -> looker_sdk.sdk.api40.methods.Looker40SDK:
    """Initializes and configures a Looker SDK instance dynamically with a Bearer token."""
    logger.info("Initializing Looker SDK client dynamically for base URL: %s", base_url)
    settings = CustomApiSettings(base_url=base_url)
    sdk = looker_sdk.init40(config_settings=settings)

    # Inject pre-authenticated AuthToken to bypass standard OAuth client credentials flow
    access_token_obj = auth_token.AccessToken(
        access_token=token,
        token_type="Bearer",
        expires_in=3600,
    )
    sdk.auth.token = auth_token.AuthToken(token=access_token_obj)

    # Attach custom StreamWrapper dynamically
    sdk.stream = StreamWrapper(sdk)
    return sdk
