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

"""Callbacks implementation for looker_ca_native_agent."""

import datetime
import logging
import pprint
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from looker_sdk.sdk.api40 import models as models40

from ..config import settings
from ..constants import CURRENT_SYSTEM_MESSAGES_STATE_KEY
from ..utils.auth import resolve_auth_token, resolve_conversation_id
from ..utils.sdk_client import get_looker_sdk

logger = logging.getLogger(__name__)


def inspect_callback_context(callback_context: CallbackContext) -> None:
    """Serializes and logs the attributes and state of the callback context for diagnostics."""
    logger.info("==== DEBUG: INTROSPECTING CALLBACK_CONTEXT ====")
    try:
        details: dict[str, Any] = {
            "invocation_id": getattr(callback_context, "invocation_id", None),
            "agent_name": getattr(callback_context, "agent_name", None),
            "user_id": getattr(callback_context, "user_id", None),
            "state": dict(callback_context.session.state) if getattr(callback_context, "session", None) else None,
            "session_id": getattr(getattr(callback_context, "session", None), "id", None),
        }

        user_content = getattr(callback_context, "user_content", None)
        if user_content:
            details["user_content"] = (
                user_content.model_dump()
                if hasattr(user_content, "model_dump")
                else str(user_content)
            )

        # Collect all public non-callable attributes
        attributes = []
        for attr in dir(callback_context):
            if not attr.startswith("_") and not callable(getattr(callback_context, attr)):
                attributes.append(attr)
        details["all_public_fields"] = attributes

        logger.info("Introspected callback_context fields:\n%s", pprint.pformat(details))
    except Exception as err:
        logger.error("Diagnostic context introspection failed: %s", err, exc_info=True)
    logger.info("================================================")


def before_agent_run(callback_context: CallbackContext) -> Optional[types.Content]:
    """Ensures the conversation session exists in Looker before running the query agent."""
    # 1. Inspect the context variables
    inspect_callback_context(callback_context)

    conversation_id = resolve_conversation_id(callback_context)
    if conversation_id:
        logger.info("Found existing conversation ID in state: %s", conversation_id)
        return None

    token = resolve_auth_token(callback_context)
    base_url = settings.lookersdk_base_url
    agent_id = settings.looker_ca_agent_id

    if not token:
        logger.error("Authentication token could not be resolved. Skipping conversation creation.")
        return None
    if not base_url:
        logger.error("LOOKERSDK_BASE_URL environment variable is not set.")
        return None
    if not agent_id:
        logger.error("LOOKER_CA_AGENT_ID or AGENT_ID environment variable is not set.")
        return None

    logger.info("Initializing Looker SDK to create a new conversation for agent: %s", agent_id)
    try:
        sdk = get_looker_sdk(base_url, token)
        new_conv = models40.WriteConversation(
            name="Conversational Analytics Session",
            agent_id=agent_id,
            category="conversation",
        )
        conv = sdk.create_conversation(body=new_conv)
        if conv and conv.id:
            callback_context.state["contextID"] = conv.id
            logger.info("Successfully created Looker conversation. Persistent ID stored in state: %s", conv.id)
        else:
            logger.error("Looker SDK create_conversation returned empty or invalid response: %r", conv)
    except Exception as err:
        logger.exception("Unexpected exception while creating Looker conversation: %s", err)

    return None


def after_agent_run(callback_context: CallbackContext) -> Optional[types.Content]:
    """Persists the turn's full message history back to the Looker conversation."""
    conversation_id = resolve_conversation_id(callback_context)
    system_messages = callback_context.state.get(CURRENT_SYSTEM_MESSAGES_STATE_KEY)

    if not conversation_id:
        logger.warning("No contextID found in state. Skipping conversation message persistence.")
        return None
    if not system_messages:
        logger.warning("No system messages accumulated during turn. Skipping message persistence.")
        return None

    token = resolve_auth_token(callback_context)
    base_url = settings.lookersdk_base_url

    if not token or not base_url:
        logger.error("Missing authentication token or LOOKERSDK_BASE_URL. Cannot persist messages.")
        return None

    # Extract user message content
    user_query = ""
    if callback_context.user_content and callback_context.user_content.parts:
        user_query = callback_context.user_content.parts[0].text or ""

    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    persist_messages: list[dict[str, Any]] = [
        {
            "type": "user",
            "message": {
                "userMessage": {
                    "text": user_query
                },
                "timestamp": timestamp,
            },
        }
    ]

    for msg in system_messages:
        persist_messages.append({
            "type": "system",
            "message": msg,
        })

    logger.info(
        "Attempting to persist conversation history (%d messages) for conversation ID: %s",
        len(persist_messages),
        conversation_id,
    )
    try:
        sdk = get_looker_sdk(base_url, token)
        persist_payload = models40.WriteConversationMessages(
            messages=persist_messages
        )
        sdk.create_conversation_message(
            conversation_id=conversation_id,
            body=persist_payload,
        )
        logger.info("Successfully persisted conversation messages back to Looker.")
    except Exception as err:
        logger.exception("Failed to persist conversation messages to Looker API: %s", err)

    # Clean up temporary messages cache from state
    if getattr(callback_context, "session", None) is not None:
        callback_context.session.state.pop(CURRENT_SYSTEM_MESSAGES_STATE_KEY, None)
    return None
