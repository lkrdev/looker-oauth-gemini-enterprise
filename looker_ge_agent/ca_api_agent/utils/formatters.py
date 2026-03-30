"""Utility functions for formatting CA API data responses."""
import json
from typing import Any
from google.protobuf import json_format

from ca_api_agent.constants import DATA_MESSAGE_DISPLAY_MAX_ROWS, DATA_TABLE_DISPLAY_MAX_ROWS

def _message_to_dict(message: Any) -> dict[str, Any]:
    proto_message = getattr(message, "_pb", message)
    return json_format.MessageToDict(
        proto_message,
        preserving_proto_field_name=True,
    )

def _to_plain_rows(rows: list[Any]) -> list[dict[str, Any]]:
    plain_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            plain_rows.append(row)
            continue
        if hasattr(row, "items"):
            try:
                item_dict = dict(row.items())
                if item_dict:
                    plain_rows.append(item_dict)
                    continue
            except Exception:
                pass
        try:
            row_dict = _message_to_dict(row)
        except Exception:
            row_dict = {}
        if isinstance(row_dict, dict):
            if set(row_dict.keys()) == {"fields"} and isinstance(
                row_dict["fields"], dict
            ):
                row_dict = row_dict["fields"]
            if row_dict:
                plain_rows.append(row_dict)
                continue
        plain_rows.append({"value": str(row)})
    return plain_rows

def _truncate_data_message_for_display(data_message: dict[str, Any]) -> dict[str, Any]:
    result = data_message.get("result")
    if not isinstance(result, dict):
        return data_message

    display_data_message = dict(data_message)
    display_result = dict(result)
    trimmed_row_counts: dict[str, int] = {}

    for field_name in ("data", "formatted_data"):
        rows = result.get(field_name)
        if not isinstance(rows, list):
            continue
        if len(rows) <= DATA_MESSAGE_DISPLAY_MAX_ROWS:
            continue
        display_result[field_name] = rows[:DATA_MESSAGE_DISPLAY_MAX_ROWS]
        trimmed_row_counts[field_name] = len(rows) - DATA_MESSAGE_DISPLAY_MAX_ROWS

    if not trimmed_row_counts:
        return data_message

    display_result["display_trimmed_row_counts"] = trimmed_row_counts
    display_data_message["result"] = display_result
    return display_data_message

def _build_data_message_trim_notice(display_data_message: dict[str, Any]) -> str | None:
    result = display_data_message.get("result")
    if not isinstance(result, dict):
        return None

    trimmed_row_counts = result.get("display_trimmed_row_counts")
    if not isinstance(trimmed_row_counts, dict) or not trimmed_row_counts:
        return None

    trimmed_fields = ", ".join(
        f"{field}: {count} row(s) omitted"
        for field, count in trimmed_row_counts.items()
    )
    return (
        f"_DataMessage JSON was trimmed to {DATA_MESSAGE_DISPLAY_MAX_ROWS} rows per field "
        f"({trimmed_fields})._\n"
    )

def _format_code_block_json(payload: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(payload, indent=2)}\n```\n"

def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)

def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

def _format_simple_markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows returned._\n"

    headers: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    if not headers:
        return "_No tabular columns returned._\n"

    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    body_lines: list[str] = []
    for row in rows:
        cells = [
            _escape_markdown_cell(_stringify_cell(row.get(header)))
            for header in headers
        ]
        body_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_line, separator_line, *body_lines]) + "\n"
