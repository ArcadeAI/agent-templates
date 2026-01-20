import asyncio
import os
from typing import Any
from arcadepy import AsyncArcade
from arcadepy.types import ToolDefinition
from pydantic import BaseModel, Field, create_model


# Mapping of Arcade value types to Python types
TYPE_MAPPING = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "json": dict,
}


def get_python_type(val_type: str) -> Any:
    """Map Arcade value types to Python types.

    Args:
        val_type: The value type as a string.

    Returns:
        Corresponding Python type.
    """
    _type = TYPE_MAPPING.get(val_type)
    if _type is None:
        raise ValueError(f"Invalid value type: {val_type}")
    return _type


def tool_definition_to_pydantic_model(tool_def: ToolDefinition) -> type[BaseModel]:
    """Convert a ToolDefinition's inputs into a Pydantic BaseModel.

    Args:
        tool_def: The ToolDefinition object to convert.

    Returns:
        A Pydantic BaseModel class representing the tool's input schema.
    """
    try:
        fields: dict[str, Any] = {}
        for param in tool_def.input.parameters or []:
            param_type = get_python_type(param.value_schema.val_type)
            if param_type == list and param.value_schema.inner_val_type:  # noqa: E721
                inner_type: type[Any] = get_python_type(param.value_schema.inner_val_type)
                param_type = list[inner_type]  # type: ignore[valid-type]
            param_description = param.description or "No description provided."
            default = ... if param.required else None
            fields[param.name] = (
                param_type,
                Field(default=default, description=param_description),
            )
        return create_model(f"{tool_def.name}Args", **fields)
    except ValueError as e:
        raise ValueError(
            f"Error converting {tool_def.name} parameters into pydantic model: {e}"
        )


def get_arcade_client(
    base_url: str = "https://api.arcade.dev",
    api_key: str = os.getenv("ARCADE_API_KEY", None),
    **kwargs: dict[str, Any],
) -> AsyncArcade:
    """
    Returns an AsyncArcade client.
    """
    if api_key is None:
        raise ValueError("ARCADE_API_KEY is not set")
    return AsyncArcade(base_url=base_url, api_key=api_key, **kwargs)


async def _get_arcade_tool_formats(
    client: AsyncArcade,
    tools: list[str] | None = None,
    toolkits: list[str] | None = None,
    raise_on_empty: bool = True,
) -> list[ToolDefinition]:
    """
    Asynchronously fetches tool definitions for each toolkit using client.tools.list,
    and returns a list of formatted tools respecting OpenAI's formatting.

    Args:
        client: AsyncArcade client
        tools: Optional list of specific tool names to include.
        toolkits: Optional list of toolkit names to include all tools from.
        raise_on_empty: Whether to raise an error if no tools or toolkits are provided.

    Returns:
        A list of formatted tools respecting OpenAI's formatting.
    """
    if not tools and not toolkits:
        if raise_on_empty:
            raise ValueError(
                "No tools or toolkits provided to retrieve tool definitions")
        return {}

    all_tool_formats: list[ToolDefinition] = []
    # Retrieve individual tools if specified
    if tools:
        tasks = [client.tools.get(name=tool_id)
                 for tool_id in tools]
        responses = await asyncio.gather(*tasks)
        for response in responses:
            all_tool_formats.append(response)

    # Retrieve tools from specified toolkits
    if toolkits:
        # Create a task for each toolkit to fetch its
        # tool definitions concurrently.
        tasks = [client.tools.list(toolkit=tk)
                 for tk in toolkits]
        responses = await asyncio.gather(*tasks)

        # Combine the tool definitions from each response.
        for response in responses:
            # Here we assume the returned response has an "items" attribute
            # containing a list of ToolDefinition objects.
            all_tool_formats.extend(response.items)

    return all_tool_formats
