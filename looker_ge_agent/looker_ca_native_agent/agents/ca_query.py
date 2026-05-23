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

"""Conversational Analytics query agent and native Looker Python SDK streaming bridge."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from looker_sdk.sdk.api40 import models as models40
from typing_extensions import override

from ..config import settings
from ..constants import (
    CURRENT_SYSTEM_MESSAGES_STATE_KEY,
    DATA_MESSAGE_DISPLAY_MAX_ROWS,
    DATA_RESULT_STATE_KEY,
    DATA_TABLE_DISPLAY_MAX_ROWS,
    RAW_RESULTS,
    SUMMARY_STATE_KEY,
    VEGA_LITE_SPEC_STATE_KEY,
)
from ..utils.auth import resolve_auth_token, resolve_conversation_id
from ..utils.formatters import (
    _build_data_message_trim_notice,
    _format_code_block_json,
    _format_simple_markdown_table,
    _to_plain_rows,
    _truncate_data_message_for_display,
)
from ..utils.sdk_client import get_looker_sdk

logger = logging.getLogger(__name__)


def _clear_response_shape_state(ctx: InvocationContext) -> None:
    """Clears routing-related state to avoid stale data across turns."""
    keys_to_clear = (
        DATA_RESULT_STATE_KEY,
        SUMMARY_STATE_KEY,
    )
    for key in keys_to_clear:
        ctx.session.state.pop(key, None)
    ctx.session.state[VEGA_LITE_SPEC_STATE_KEY] = ""


async def stream_nlq(question: str, ctx: InvocationContext) -> AsyncGenerator[str, None]:
    """Streams CA API responses via Looker SDK and persists turn's messages to state."""
    logger.info("Starting stream_nlq for question: %r", question)
    _clear_response_shape_state(ctx)

    # Dynamically resolve dynamic Auth token and conversation tracking ID using utility helpers
    token = resolve_auth_token(ctx)
    if not token:
        logger.error("No Bearer token provided or resolved in the request context.")
        yield json.dumps({
            "error": "No Bearer token provided in the Authorization header. A valid token is required to access the Looker API.",
            "code": "UNAUTHENTICATED",
        })
        return

    conversation_id = resolve_conversation_id(ctx)
    if not conversation_id:
        logger.error("No contextID (conversation ID) was found in ADK state. before_agent_run callback may have failed.")
        yield json.dumps({
            "error": "No persistent Looker Conversational Analytics conversation ID (contextID) was found.",
            "code": "INTERNAL_ERROR",
        })
        return

    base_url = settings.lookersdk_base_url
    if not base_url:
        logger.error("LOOKERSDK_BASE_URL environment variable is not set.")
        yield json.dumps({
            "error": "LOOKERSDK_BASE_URL environment variable is missing.",
            "code": "INTERNAL_ERROR",
        })
        return

    # Prepare request parameters
    request_body = models40.ConversationalAnalyticsChatRequest(
        conversation_id=conversation_id,
        user_message=question,
    )


    current_system_messages = []

    try:
        # Initialize dynamically configured Looker SDK client
        sdk = get_looker_sdk(base_url, token)
        
        # Invoke streaming wrapper
        stream = sdk.stream.conversational_analytics_chat(body=request_body)

        for chunk in stream:
            # A chunk contains timestamp and systemMessage keys
            system_message = chunk.get("systemMessage")
            if not system_message:
                continue

            # Accumulate raw systemMessage payload for persistence in after_agent_run callback
            current_system_messages.append(chunk)

            # Process Data node
            data_message = system_message.get("data")
            if isinstance(data_message, dict) and data_message:
                display_data_message = _truncate_data_message_for_display(data_message)
                yield _format_code_block_json(display_data_message)

                trim_notice = _build_data_message_trim_notice(display_data_message)
                if trim_notice:
                    yield trim_notice
                await asyncio.sleep(0)

                query_payload = data_message.get("query")
                result_payload = data_message.get("result")
                query_question = (
                    query_payload.get("question")
                    if isinstance(query_payload, dict)
                    else None
                )

                if isinstance(query_question, str) and query_question:
                    yield f"Analyzing your question: {query_question}\n"
                    await asyncio.sleep(0)
                elif isinstance(result_payload, dict):
                    payload_rows = result_payload.get("data")
                    normalized_data_rows = (
                        _to_plain_rows(payload_rows)
                        if isinstance(payload_rows, list)
                        else []
                    )
                    ctx.session.state[DATA_RESULT_STATE_KEY] = normalized_data_rows

                    yield f"The query returned {len(normalized_data_rows)} row(s)\n\n"
                    yield _format_simple_markdown_table(
                        normalized_data_rows[:DATA_TABLE_DISPLAY_MAX_ROWS]
                    )

                    if len(normalized_data_rows) > DATA_TABLE_DISPLAY_MAX_ROWS:
                        yield (
                            f"_Showing first {DATA_TABLE_DISPLAY_MAX_ROWS} rows out of "
                            f"{len(normalized_data_rows)}._\n"
                        )
                    await asyncio.sleep(0)
                    if RAW_RESULTS:
                        logger.info("RAW_RESULTS is True, stopping stream yield after formatting data message.")
                        # Write current system messages to state before exiting
                        ctx.session.state[CURRENT_SYSTEM_MESSAGES_STATE_KEY] = current_system_messages
                        return

            # Process Chart node (for visualization rendering sub-agent)
            chart_message = system_message.get("chart")
            if isinstance(chart_message, dict) and chart_message:
                ctx.session.state[VEGA_LITE_SPEC_STATE_KEY] = chart_message
                await asyncio.sleep(0)

            # Process Text node
            text_message = system_message.get("text")
            if isinstance(text_message, dict) and text_message.get("parts"):
                parts = text_message.get("parts")
                if isinstance(parts, list) and parts:
                    summary_text = parts[0]
                    if isinstance(summary_text, str) and summary_text.strip():
                        ctx.session.state[SUMMARY_STATE_KEY] = summary_text.strip()
                        yield summary_text.strip() + "\n"
                        await asyncio.sleep(0)

    except Exception as err:
        logger.exception("Unexpected exception while streaming from Looker Conversational Analytics: %s", err)
        yield json.dumps({"error": f"An error occurred during streaming: {err}", "code": "STREAM_ERROR"})
        return

    # Persist turned system messages to state so after_agent_run hook can save them back to Looker
    logger.info("Stream successfully completed. Storing %d system messages in state.", len(current_system_messages))
    ctx.session.state[CURRENT_SYSTEM_MESSAGES_STATE_KEY] = current_system_messages



def _extract_user_question(ctx: InvocationContext) -> str | None:
    """Extracts plain-text question from the invocation's user content."""
    user_content = ctx.user_content
    if not user_content or not user_content.parts:
        return None

    text_parts: list[str] = []
    for part in user_content.parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    if not text_parts:
        return None
    return "\n".join(text_parts)


class ConversationalAnalyticsQueryAgent(BaseAgent):
    """Runs NLQ requests against CA API and streams results back into the chat."""

    name: str
    description: str = ""

    def __init__(
        self,
        name: str,
        description: str = "",
    ) -> None:
        init_data: dict[str, Any] = {
            "name": name,
            "description": description,
        }
        super().__init__(**init_data)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        question = _extract_user_question(ctx)
        if not question:
            error_content = types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            "I couldn't read your question. "
                            "Please send a text prompt."
                        )
                    )
                ],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=True,
                invocation_id=ctx.invocation_id,
                content=error_content,
            )
            return

        status_message = types.Content(
            role="model",
            parts=[types.Part(text="Invoking the Conversational Analytics API...\n")],
        )
        yield Event(
            author=self.name,
            partial=False,
            turn_complete=False,
            invocation_id=ctx.invocation_id,
            content=status_message,
        )

        async for data_chunk in stream_nlq(question, ctx):
            streamed_response_chunk = types.Content(
                role="model",
                parts=[types.Part(text=data_chunk)],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=False,
                invocation_id=ctx.invocation_id,
                content=streamed_response_chunk,
            )

        yield Event(
            author=self.name,
            partial=False,
            turn_complete=True,
            invocation_id=ctx.invocation_id,
        )


def build_conversational_analytics_query_agent(
    name: str = "conversational_analytics_query_agent",
) -> ConversationalAnalyticsQueryAgent:
    """Factory for the CA query sub-agent."""
    return ConversationalAnalyticsQueryAgent(
        name=name,
        description="Always forwards each user request directly to the Conversational Analytics API.",
    )
