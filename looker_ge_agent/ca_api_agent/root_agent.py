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

"""Root agent for deterministic CA-first orchestration with optional sub-agents."""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, cast

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr
from typing_extensions import override

from .agents import (
    DATA_RESULT_STATE_KEY,
    build_conversational_analytics_query_agent,
    build_visualization_agent,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionalSubAgentSpec:
    """Configuration for deterministic optional sub-agent routing."""

    key: str
    description: str
    agent: BaseAgent
    run_when: Callable[[InvocationContext], bool]


class RootAgent(BaseAgent):
    """Always runs CA first, then conditionally runs optional sub-agents."""

    name: str
    description: str = ""
    query_agent: BaseAgent
    _optional_sub_agents: list[OptionalSubAgentSpec] = PrivateAttr(default_factory=list)

    def __init__(
        self,
        name: str,
        description: str,
        query_agent: BaseAgent,
        optional_sub_agents: list[OptionalSubAgentSpec],
    ) -> None:
        init_data: dict[str, Any] = {
            "name": name,
            "description": description,
            "query_agent": query_agent,
        }
        super().__init__(**init_data)
        self._optional_sub_agents = optional_sub_agents

    @staticmethod
    def _has_non_empty_state(ctx: InvocationContext, key: str) -> bool:
        value = ctx.session.state.get(key)
        logger.info("Evaluating state for key '%s': value is type=%s, content=%r", key, type(value).__name__, value)
        if value is None:
            return False
        if isinstance(value, (str, bytes, list, tuple, set, dict)):
            return len(value) > 0
        return bool(value)

    def _select_optional_sub_agents(
        self, ctx: InvocationContext
    ) -> list[OptionalSubAgentSpec]:
        selected: list[OptionalSubAgentSpec] = []
        logger.info("Checking %d configured optional sub-agents...", len(self._optional_sub_agents))

        for spec in self._optional_sub_agents:
            if not isinstance(spec, OptionalSubAgentSpec):
                logger.error("Invalid sub-agent spec type: %s. Did you forget to wrap the agent in OptionalSubAgentSpec?", type(spec))
                continue
                
            logger.info("Evaluating sub-agent spec '%s'", spec.key)
            try:
                if spec.run_when(ctx):
                    logger.info("run_when condition for '%s' returned TRUE", spec.key)
                    selected.append(spec)
                else:
                    logger.info("run_when condition for '%s' returned FALSE", spec.key)
            except Exception as err:  # pragma: no cover - defensive route guard
                logger.exception("Failed while evaluating routing rule for '%s': %s", spec.key, err)
        return selected

    @staticmethod
    def _as_non_terminal(event: Event) -> Event:
        """Returns a copy of the event marked as non-terminal for orchestration streaming."""
        if not event.turn_complete:
            return event
        copy_fn = getattr(event, "model_copy", None)
        if callable(copy_fn):
            return cast(Event, copy_fn(update={"turn_complete": False}))
        event.turn_complete = False
        return event

    @staticmethod
    def _strip_code_blocks(text: str) -> str:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        # Fix squashed "Saved as artifact" text chunks
        text = re.sub(r"(\w+)\.Saved as artifact:", r"\1.\n\nSaved as artifact:", text)
        return text

    @staticmethod
    def _sanitize_visualization_content(
        content: types.Content | None,
    ) -> types.Content | None:
        if not content or not content.parts:
            return content

        sanitized_parts: list[types.Part] = []
        for part in content.parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                mime_type = getattr(inline_data, "mime_type", None) or "image/png"
                if mime_type.startswith("image/"):
                    sanitized_parts.append(part)
                    continue

            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                cleaned = RootAgent._strip_code_blocks(text).strip()
                if cleaned:
                    sanitized_parts.append(types.Part(text=cleaned))

        if not sanitized_parts:
            return None
        return types.Content(role=content.role, parts=sanitized_parts)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info("root_agent started _run_async_impl, running query_agent...")
        async for event in self.query_agent.run_async(ctx):
            yield self._as_non_terminal(event)
        logger.info("query_agent completed.")

        logger.info("Evaluating optional sub-agents based on context state: %s", ctx.session.state)
        selected_agents = self._select_optional_sub_agents(ctx)
        if selected_agents:
            logger.info(
                "Optional sub-agents selected: %s",
                ", ".join(spec.key for spec in selected_agents),
            )
        else:
            logger.info("No optional sub-agents selected for this request.")

        for spec in selected_agents:
            logger.info("Triggering optional sub-agent: %s", spec.key)
            status_content = types.Content(
                role="model",
                parts=[types.Part(text=f"Running optional step: {spec.description}\n")],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=False,
                invocation_id=ctx.invocation_id,
                content=status_content,
            )

            detected_pngs = []
            accumulated_text = ""
            try:
                logger.info("Starting spec.agent.run_async for '%s'", spec.key)
                async for event in spec.agent.run_async(ctx):
                    forward_event = event
                    if spec.key == "visualization":
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                text = getattr(part, "text", None)
                                if isinstance(text, str):
                                    accumulated_text += text
                            
                            # Search full accumulated text for the pattern
                            match = re.search(r"Saved as artifact:\s*([a-zA-Z0-9_-]+\.png)", accumulated_text)
                            if match:
                                png_name = match.group(1)
                                if png_name not in detected_pngs:
                                    detected_pngs.append(png_name)
                                    logger.info("Regex-detected new PNG artifact in accumulated text: %s", png_name)

                        sanitized_content = self._sanitize_visualization_content(
                            event.content
                        )
                        if sanitized_content is None:
                            continue
                        copy_fn = getattr(event, "model_copy", None)
                        if callable(copy_fn):
                            forward_event = cast(
                                Event, copy_fn(update={"content": sanitized_content})
                            )
                        else:
                            event.content = sanitized_content
                            forward_event = event
                    yield self._as_non_terminal(forward_event)

                # Post-process: load and yield any regex-detected PNG artifacts!
                if spec.key == "visualization":
                    for png_name in detected_pngs:
                        try:
                            logger.info("Loading regex-detected PNG artifact: %s...", png_name)
                            artifact_part = await ctx.load_artifact(png_name)
                            if artifact_part and artifact_part.inline_data:
                                # Ensure correct image/png MIME type
                                artifact_part.inline_data.mime_type = "image/png"
                                image_event = Event(
                                    author=self.name,
                                    partial=False,
                                    turn_complete=False,
                                    invocation_id=ctx.invocation_id,
                                    content=types.Content(role="model", parts=[artifact_part])
                                )
                                yield self._as_non_terminal(image_event)
                        except Exception as e:
                            logger.error("Failed loading regex-detected artifact %s: %s", png_name, e)

            except Exception as err:  # pragma: no cover - defensive runtime guard
                logger.exception("Optional sub-agent '%s' failed.", spec.key)
                error_content = types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=(
                                f"Optional step '{spec.key}' failed with error: {err}. "
                                "Continuing with available results."
                            )
                        )
                    ],
                )
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=False,
                    invocation_id=ctx.invocation_id,
                    content=error_content,
                )

        yield Event(
            author=self.name,
            partial=False,
            turn_complete=True,
            invocation_id=ctx.invocation_id,
        )


data_query_agent = build_conversational_analytics_query_agent()
visualization_agent = build_visualization_agent()

# Add new optional sub-agents here to extend orchestration behavior.
optional_sub_agents = [
    OptionalSubAgentSpec(
        key="visualization",
        description="data-result-driven visualization rendering",
        agent=visualization_agent,
        run_when=lambda ctx: RootAgent._has_non_empty_state(ctx, DATA_RESULT_STATE_KEY),
    ),
]

root_agent = RootAgent(
    name="root_agent",
    description=(
        "Top-level deterministic root agent. It always runs the CA query agent, then "
        "conditionally runs optional sub-agents based on response shape."
    ),
    query_agent=data_query_agent,
    optional_sub_agents=optional_sub_agents,
)

__all__ = ["root_agent"]
