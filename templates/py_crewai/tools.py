"""Arcade <-> CrewAI tool adapter.

Fetches tool definitions from the Arcade platform and wraps them as CrewAI
BaseTool instances so they can be passed directly to a CrewAI Agent.
"""

from typing import Any

from arcadepy import Arcade
from arcadepy.types import ToolDefinition
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, create_model


TYPE_MAP: dict[str, type] = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "json": dict,
}


def _python_type(val_type: str) -> type:
    t = TYPE_MAP.get(val_type)
    if t is None:
        raise ValueError(f"Unsupported Arcade value type: {val_type}")
    return t


def _build_args_model(tool_def: ToolDefinition) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for param in tool_def.input.parameters or []:
        param_type = _python_type(param.value_schema.val_type)
        if param_type is list and param.value_schema.inner_val_type:
            inner = _python_type(param.value_schema.inner_val_type)
            param_type = list[inner]  # type: ignore[valid-type]
        default = ... if param.required else None
        fields[param.name] = (
            param_type,
            Field(default=default, description=param.description or ""),
        )
    return create_model(f"{tool_def.name}Input", **fields)


class ArcadeTool(BaseTool):
    """A CrewAI tool backed by an Arcade tool definition."""

    name: str
    description: str
    args_schema: type[BaseModel]

    # Internal fields (not exposed to CrewAI)
    arcade_tool_name: str = ""
    user_id: str = ""
    _client: Arcade | None = None

    def _auth_tool(self):
        auth = self._client.tools.authorize(
            tool_name=self.arcade_tool_name,
            user_id=self.user_id,
        )
        if auth.status != "completed":
            print(f"Authorization required. Visit: {auth.url}")
            self._client.auth.wait_for_completion(auth)

    def _run(self, **kwargs: Any) -> str:
        if self._client is None:
            self._client = Arcade()

        self._auth_tool()

        print(f"Calling {self.arcade_tool_name}...")

        result = self._client.tools.execute(
            tool_name=self.arcade_tool_name,
            input=kwargs,
            user_id=self.user_id,
        )

        if not result.success:
            return f"Tool error: {result.output.error.message}"

        print(f"Call to {self.arcade_tool_name} successful, the agent will now process the result...")
        return result.output.value


def get_arcade_tools(
    client: Arcade,
    *,
    tools: list[str] | None = None,
    mcp_servers: list[str] | None = None,
    user_id: str = "",
) -> list[ArcadeTool]:
    """Fetch Arcade tool definitions and return them as CrewAI tools.

    Args:
        client:   A *synchronous* Arcade client.
        tools:    Specific tool names, e.g. ["Google.ListEmails"].
        mcp_servers: Toolkit names, e.g. ["Google"].
        user_id:  User ID forwarded for authorization & execution.
    """
    if not tools and not mcp_servers:
        raise ValueError("Provide at least one tool name or toolkit name")

    definitions: list[ToolDefinition] = []

    if tools:
        for name in tools:
            definitions.append(client.tools.get(name=name))

    if mcp_servers:
        for tk in mcp_servers:
            page = client.tools.list(toolkit=tk)
            definitions.extend(page.items)

    result: list[ArcadeTool] = []
    for defn in definitions:
        sanitized_name = defn.qualified_name.replace(".", "_")
        t = ArcadeTool(
            client=client,
            name=sanitized_name,
            description=defn.description,
            args_schema=_build_args_model(defn),
            arcade_tool_name=defn.qualified_name,
            user_id=user_id,
        )
        result.append(t)

    return result
