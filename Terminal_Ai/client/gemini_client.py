"""Native Gemini client using the official google-genai SDK.

This module is used when the configured model name starts with 'gemini-'.
It translates CharanCLI's OpenAI-style message format and tool schemas into
Gemini's native format, then converts Gemini responses back into StreamEvents.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from .response import (
    StreamEvent,
    StreamEventType,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
)

logger = logging.getLogger(__name__)


def _is_gemini_model(model_name: str) -> bool:
    return model_name.lower().startswith("gemini")


def _convert_messages_to_gemini(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert OpenAI-style messages to Gemini contents format.

    Returns (system_instruction, contents).
    """
    system_instruction: str | None = None
    contents: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            # Gemini handles system prompt separately
            if isinstance(content, str):
                system_instruction = content
            elif isinstance(content, list):
                system_instruction = " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            continue

        if role == "assistant":
            gemini_role = "model"
        elif role == "tool":
            # Tool result — attach to the previous model turn as function response
            tool_call_id = msg.get("tool_call_id", "")
            tool_content = msg.get("content", "")
            contents.append(
                {
                    "role": "user",  # Gemini expects function responses from "user" side
                    "parts": [
                        {
                            "functionResponse": {
                                "name": tool_call_id,
                                "response": {"result": tool_content},
                            }
                        }
                    ],
                }
            )
            continue
        else:
            gemini_role = "user"

        # Build parts from content
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            if content:
                parts.append({"text": content})
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        # Basic image passthrough — skipped for now
                        pass

        # If assistant had tool calls, include them
        tool_calls = msg.get("tool_calls")
        if tool_calls and role == "assistant":
            for tc in tool_calls:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                parts.append(
                    {
                        "functionCall": {
                            "name": fn.get("name", ""),
                            "args": args,
                        }
                    }
                )

        if parts:
            contents.append({"role": gemini_role, "parts": parts})

    return system_instruction, contents


def _clean_schema_for_gemini(schema: Any) -> Any:
    """Recursively strip fields that the Gemini API rejects from JSON schemas.

    Gemini's FunctionDeclaration only supports a subset of JSON Schema.
    Rejected fields include: additionalProperties, $defs, definitions,
    title, default, anyOf ($ref resolution not needed since _build_tools already handles it).
    """
    if not isinstance(schema, dict):
        return schema

    # Fields Gemini does NOT accept
    BLOCKED = {
        "additionalProperties",
        "$defs",
        "definitions",
        "$schema",
        "title",
        "default",
        "examples",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "contentMediaType",
        "contentEncoding",
    }

    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key in BLOCKED:
            continue
        # Resolve anyOf (Optional[X] → X)
        if key == "anyOf" and isinstance(value, list):
            non_null = [v for v in value if isinstance(v, dict) and v.get("type") != "null"]
            if non_null:
                # Merge first non-null variant into parent (skip adding anyOf)
                for k, v in non_null[0].items():
                    if k not in cleaned:
                        cleaned[k] = _clean_schema_for_gemini(v)
            continue
        # Recurse into nested objects / arrays
        if isinstance(value, dict):
            cleaned[key] = _clean_schema_for_gemini(value)
        elif isinstance(value, list):
            cleaned[key] = [_clean_schema_for_gemini(item) for item in value]
        else:
            cleaned[key] = value

    return cleaned


def _convert_tools_to_gemini(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-style tool schemas to Gemini FunctionDeclaration format."""
    declarations = []
    for tool in tools:
        fn = tool.get("function", tool)  # support both wrapped and bare
        params = fn.get("parameters", {"type": "object", "properties": {}})
        # Deep-clean the schema so Gemini accepts it
        params = _clean_schema_for_gemini(params)
        # Ensure required structure
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        declarations.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": params,
            }
        )
    return declarations



class GeminiClient:
    """Wraps the google-genai SDK to produce CharanCLI StreamEvents."""

    def __init__(self, api_key: str, model_name: str) -> None:
        try:
            from google import genai
            from google.genai import types as gentypes
        except ImportError as e:
            raise ImportError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from e

        self._genai = genai
        self._types = gentypes
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run inference and yield StreamEvents matching CharanCLI's protocol."""
        types = self._types
        system_instruction, contents = _convert_messages_to_gemini(messages)

        # Build config
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        # Build tools
        gemini_tools = None
        if tools:
            declarations = _convert_tools_to_gemini(tools)
            gemini_tool = types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(**d) for d in declarations
                ]
            )
            gemini_tools = [gemini_tool]
            config_kwargs["tools"] = gemini_tools

        gen_config = types.GenerateContentConfig(**config_kwargs)

        # Convert contents to Gemini Content objects
        gemini_contents = []
        for c in contents:
            role = c["role"]
            parts_raw = c["parts"]
            gemini_parts = []
            for p in parts_raw:
                if "text" in p:
                    gemini_parts.append(types.Part.from_text(text=p["text"]))
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    gemini_parts.append(
                        types.Part.from_function_call(
                            name=fc["name"], args=fc.get("args", {})
                        )
                    )
                elif "functionResponse" in p:
                    fr = p["functionResponse"]
                    gemini_parts.append(
                        types.Part.from_function_response(
                            name=fr["name"], response=fr.get("response", {})
                        )
                    )
            if gemini_parts:
                gemini_contents.append(types.Content(role=role, parts=gemini_parts))

        # Run in thread to avoid blocking event loop (SDK is sync)
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self._model_name,
                    contents=gemini_contents,
                    config=gen_config,
                ),
            )
        except Exception as e:
            yield StreamEvent(type=StreamEventType.ERROR, error=str(e))
            return

        # Parse response
        usage: TokenUsage | None = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
                total_tokens=getattr(um, "total_token_count", 0) or 0,
            )

        # Check candidates
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            # No candidates — error
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error=f"Gemini returned no candidates. Finish reason: {getattr(response, 'prompt_feedback', None)}",
            )
            return

        candidate = candidates[0]
        finish_reason = str(getattr(candidate, "finish_reason", "stop"))

        content_parts = []
        if hasattr(candidate, "content") and candidate.content:
            content_parts = getattr(candidate.content, "parts", []) or []

        tool_call_idx = 0
        for part in content_parts:
            # Text part
            text = getattr(part, "text", None)
            if text:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(content=text),
                    usage=usage,
                    final_reason=finish_reason,
                )

            # Function call part
            fc = getattr(part, "function_call", None)
            if fc is not None:
                fn_name = getattr(fc, "name", "") or ""
                fn_args = getattr(fc, "args", {}) or {}
                call_id = f"gemini_call_{tool_call_idx}"
                tool_call_idx += 1

                args_str = json.dumps(dict(fn_args))

                yield StreamEvent(
                    type=StreamEventType.TOOL_CALL_START,
                    tool_call_delta=ToolCallDelta(call_id=call_id, name=fn_name),
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_CALL_DELTA,
                    tool_call_delta=ToolCallDelta(
                        call_id=call_id, name=fn_name, arguments_delta=args_str
                    ),
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_CALL_COMPLETE,
                    tool_call=ToolCall(
                        call_id=call_id, name=fn_name, arguments=args_str
                    ),
                )

        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=TextDelta(content="", is_final=True),
            usage=usage,
            final_reason=finish_reason,
        )

    async def close(self) -> None:
        pass  # google-genai client doesn't require explicit closing
