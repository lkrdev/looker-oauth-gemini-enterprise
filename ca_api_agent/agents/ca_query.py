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

"""Conversational Analytics query agent and CA API streaming bridge."""

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from ca_api_agent.auth_context import request_bearer_token
from google.api_core import exceptions as api_exceptions
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.genai import types
from google.protobuf import json_format
from typing_extensions import override

from ca_api_agent.constants import DATA_MESSAGE_DISPLAY_MAX_ROWS, DATA_TABLE_DISPLAY_MAX_ROWS, DATA_RESULT_STATE_KEY, SUMMARY_STATE_KEY
from ca_api_agent.utils.formatters import _message_to_dict, _to_plain_rows, _truncate_data_message_for_display, _build_data_message_trim_notice, _format_code_block_json, _format_simple_markdown_table

load_dotenv()
logger = logging.getLogger(__name__)

DATA_RESULT_STATE_KEY = "temp:data_result"
SUMMARY_STATE_KEY = "temp:summary_data"






def _clear_response_shape_state(ctx: InvocationContext) -> None:
    """Clears routing-related state to avoid stale data across turns."""
    keys_to_clear = (
        DATA_RESULT_STATE_KEY,
        SUMMARY_STATE_KEY,
    )
    for key in keys_to_clear:
        ctx.session.state.pop(key, None)


def _build_inline_context(token: str) -> geminidataanalytics.Context:

    return geminidataanalytics.Context(
        system_instruction=(
            "Answer user questions to the best of your ability. "
            "Do not return charts."
        ),
        # To use BigQuery instead of Looker, uncomment the following block and replace with your table(s)
        # datasource_references = geminidataanalytics.DatasourceReferences(
        #     bq=geminidataanalytics.BigQueryTableReferences(table_references=[
        #         geminidataanalytics.BigQueryTableReference(
        #             project_id="project-name", dataset_id="dataset-name", table_id="table-name"
        #         ), 
        #         geminidataanalytics.BigQueryTableReference(
        #         project_id="project-name", dataset_id="dataset-name", table_id="table-name"
        #         )
        #     ])
        # ),
        datasource_references=geminidataanalytics.DatasourceReferences(
            looker=geminidataanalytics.LookerExploreReferences(
                explore_references=[
                    geminidataanalytics.LookerExploreReference(
                        looker_instance_uri=os.getenv("LOOKERSDK_BASE_URL"),
                        lookml_model=os.getenv("LOOKML_MODEL"),
                        explore=os.getenv("LOOKML_EXPLORE"),
                    )
                ],
                credentials=geminidataanalytics.Credentials(
                    oauth=geminidataanalytics.OAuthCredentials(
                        token=geminidataanalytics.OAuthCredentials.TokenBased(
                            access_token=token
                        )
                    )
                ),
            )
        ),
    )


async def stream_nlq(question: str, ctx: InvocationContext) -> AsyncGenerator[str, None]:
    """Streams CA API responses and persists structured result data to session state."""
    logger.info({"request": question})
    _clear_response_shape_state(ctx)

    token = request_bearer_token.get()
    if not token:
        logger.error("No Bearer token provided in the request context.")
        yield json.dumps({
            "error": "No Bearer token provided in the Authorization header. A valid token is required to access the Looker API.",
            "code": "UNAUTHENTICATED"
        })
        return

    project = (
        f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}"
        f"/locations/{os.getenv('GOOGLE_CLOUD_LOCATION')}"
    )

    user_message = geminidataanalytics.Message(
        user_message=geminidataanalytics.UserMessage(text=question)
    )
    request_messages = [user_message]

    chat_request = geminidataanalytics.ChatRequest(
        parent=project,
        messages=request_messages,
        inline_context=_build_inline_context(token),
    )

    try:
        client = geminidataanalytics.DataChatServiceAsyncClient()
        stream = await client.chat(request=chat_request)

        async for response in stream:
            if not response.system_message:
                continue

            system_message = response.system_message
            if system_message.data:
                system_message_data_node = system_message.data
                data_message = _message_to_dict(system_message_data_node)
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
                    if not normalized_data_rows:
                        result = getattr(system_message_data_node, "result", None)
                        raw_rows = list(result.data) if result and result.data else []
                        normalized_data_rows = _to_plain_rows(raw_rows)
                    ctx.session.state[DATA_RESULT_STATE_KEY] = normalized_data_rows
                    
                    yield f"The query returned {len(normalized_data_rows)} row(s)\n"
                    yield _format_simple_markdown_table(
                        normalized_data_rows[:DATA_TABLE_DISPLAY_MAX_ROWS]
                    )
                    
                    if len(normalized_data_rows) > DATA_TABLE_DISPLAY_MAX_ROWS:
                        yield (
                            f"_Showing first {DATA_TABLE_DISPLAY_MAX_ROWS} rows out of "
                            f"{len(normalized_data_rows)}._\n"
                        )
                    await asyncio.sleep(0)

            # chart rendering is handled by visualization sub-agent
            if system_message.chart:
                ctx.session.state["temp:vega_lite_spec"] = json_format.MessageToDict(system_message.chart)
                await asyncio.sleep(0)

            if system_message.text and system_message.text.parts:
                summary_part = system_message.text.parts[0]
                summary_text = getattr(summary_part, "text", None) or ""
                if summary_text:
                    ctx.session.state[SUMMARY_STATE_KEY] = summary_text
                    yield summary_text + "\n"
                    await asyncio.sleep(0)
    except api_exceptions.Unauthenticated as err:
        logger.error("Unauthenticated error from CA API: %s", err)
        yield json.dumps({
            "error": "The provided Bearer token is invalid or expired. Please re-authenticate.",
            "code": "UNAUTHENTICATED"
        })
    except api_exceptions.PermissionDenied as err:
        logger.error("PermissionDenied error from CA API: %s", err)
        yield json.dumps({
            "error": "The provided Bearer token does not have permission to access the requested resource.",
            "code": "PERMISSION_DENIED"
        })
    except api_exceptions.GoogleAPICallError as err:
        code_fn = getattr(err, "code", None)
        code = code_fn() if callable(code_fn) else None
        error_code = str(getattr(code, "name", "UNKNOWN"))
        error_message = str(getattr(err, "message", str(err)))
        logger.error("Error from CA API: %s - %s", error_code, error_message)
        yield json.dumps({"error": error_message, "code": error_code})
    except Exception as err:  # pragma: no cover - defensive catch for service errors
        logger.exception("Unexpected error from CA API")
        yield json.dumps({"error": str(err)})


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
            parts=[types.Part(text="Invoking the Conversational Analytics API...")],
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
