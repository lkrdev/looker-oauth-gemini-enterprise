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

"""Authentication and state context resolution utilities."""

import logging
from typing import Any, Union
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext

from ..config import settings

logger = logging.getLogger(__name__)


def _extract_key_from_context(
    ctx: Union[InvocationContext, CallbackContext], key: str
) -> Any:
    """Safely extracts a key from the state or session state of an ADK context."""
    # 1. Check direct attributes
    state = getattr(ctx, "state", None)
    if isinstance(state, dict) and key in state:
        return state.get(key)

    # 2. Check session state
    session = getattr(ctx, "session", None)
    if session and hasattr(session, "state") and isinstance(session.state, dict):
        return session.state.get(key)

    return None


def resolve_auth_token(ctx: Union[InvocationContext, CallbackContext]) -> str | None:
    """Resolves the Bearer authorization token dynamically from context.
    
    If missing from the context state, falls back to the developer's local
    environment token override (if provided) to facilitate local testing.
    """
    auth_key = settings.auth_id_key
    token = _extract_key_from_context(ctx, auth_key)

    if token:
        logger.debug("Bearer token resolved successfully from ADK context state.")
        return str(token)

    # Secure local developer override fallback for local testing
    dev_token = settings.local_dev_token
    if dev_token:
        logger.warning(
            "DEVELOPMENT WARNING: Bearer token not found in ADK context state. "
            "Using local development token override from environment."
        )
        return dev_token

    logger.error("Authentication bearer token could not be resolved from context state or local environment.")
    return None


def resolve_conversation_id(ctx: Union[InvocationContext, CallbackContext]) -> str | None:
    """Resolves the persistent Looker Conversational Analytics contextID (conversation ID)."""
    conv_id = _extract_key_from_context(ctx, "contextID")
    if conv_id:
        return str(conv_id)
    return None
