from arcadepy import AsyncArcade
import asyncio
import json
from dotenv import load_dotenv
from rich import print
from utils.arcade_tools import get_all_tools_from_mcp_server
from pydantic import BaseModel, Field, create_model
from typing import Any
from openai import OpenAI
from pathlib import Path

load_dotenv()

ALL_OPTIMIZED_TOOLKITS = [
    "Asana",
    "Clickup",
    "Confluence",
    "Dropbox",
    "E2B",
    "Firecrawl",
    "GoogleCalendar",
    "Gmail",
    "Github",
    "GoogleContacts",
    "GoogleDocs",
    "GoogleDrive",
    "GoogleHotels",
    "GoogleFlights",
    "GoogleFinance",
    "GoogleJobs",
    "GoogleMaps",
    "GoogleNews",
    "GoogleShopping",
    "GoogleSheets",
    "GoogleSearch",
    "GoogleSlides",
    "Hubspot",
    "Imgflip",
    "Sharepoint",
    "Linkedin",
    "Linear",
    "MicrosoftTeams",
    "NotionToolkit",
    "OutlookCalendar",
    "Salesforce",
    "Reddit",
    "OutlookMail",
    "Slack",
    # "Spotify", # Spotify is annoying for API usage, so let's not use it for now, also audio is complex and we don't have a template for it yet
    "Stripe",
    "Walmart",
    "X",
    "Youtube",
    "Zendesk",
    "Zoom",
]

def create_ts_langchain_config(toolkit: str, system_prompt: str, agent_description: str, hitl_assignment: dict):
    return {
        "arcade_toolkit_list": [
            toolkit
        ],
        "tools_with_human_confirmation": hitl_assignment,
        "agent_instruction": system_prompt,
        "agent_description": agent_description
    }

def create_scoring_schema(tools: list):
    """
    Create a dynamic Pydantic model where each tool is a field name.
    This prevents ID hallucination since the LLM can only fill in values for pre-defined fields.
    """
    fields = {}
    for tool in tools:
        fields[f'{tool.toolkit.name}_{tool.name}'] = (
            bool,
            Field(
                description=f"Whether the tool {tool.toolkit.name}_{tool.name} should require human in the loop approval to be used",
            )
        )
        # TODO(Mateo): Add a field for the document category. Note: OpenAI supports up to 1000 enum values for all fields combined.
        # fields[f'category_{tweet["id"]}'] = (
        #     DocumentCategory,
        #     Field(description=f"The document category for tweet {tweet['id']}")
        # )

    HumanInTheLoopApprovalSchema = create_model("HumanInTheLoopApprovalSchema", **fields)

    return HumanInTheLoopApprovalSchema


def invoke_openai_model(model: str, prompt: str, schema: Any | None = None) -> str:
    client = OpenAI()
    if schema:
        response = client.chat.completions.parse(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            response_format=schema
        )
        return response.choices[0].message.parsed
    else:
        response = client.responses.create(
            model=model,
            input=prompt
        )
        return response.output_text


def format_tools_for_prompt(tools: list) -> str:
    template = """
---
tool name: {toolkit_name}_{tool_name}
description: {tool_description}
{tool_parameters}"""

    parameter_template = """
    - parameter name: {parameter_name}
    - parameter description: {parameter_description}
    - parameter type: {parameter_type}
    - parameter required: {parameter_required}
"""


    formatted_tools = ""
    for tool in tools:
        toolkit_name = tool.toolkit.name
        if len(tool.input.parameters) > 0:
            tool_parameters = "parameters: \n"
        else:
            tool_parameters = "parameters: None\n"

        for parameter in tool.input.parameters:
            tool_parameters += parameter_template.format(parameter_name=parameter.name, parameter_description=parameter.description, parameter_type=parameter.value_schema.val_type, parameter_required=parameter.required)
        formatted_tools += template.format(toolkit_name=toolkit_name, tool_name=tool.name, tool_description=tool.description, tool_parameters=tool_parameters)
    formatted_tools += "---\n"
    return formatted_tools

async def main():
    client = AsyncArcade()

    prompt_template = """
    You are an expert in buildin AI agents. These are the tools that you can use to build the agent:
    {tools}.

    With that information, your task is to create a prompt for an AI agent that will use these tools effectively. The architecture of the agent
    is a ReAct agent, so bear that in mind when creating the prompt. The prompt should be in Markdown format and include the following sections:
    - Introduction: A brief introduction to the agent and its purpose.
    - Instructions: The instructions for the agent to follow.
    - Workflows: A list of the workflows that the agent will follow, and the specific sequence of tools to be used in each workflow

    You may use code blocks with triple backticks if needed to demonstrate examples.
    """

    hitl_template = """
    You are an expert in building AI agents. These are the tools that you can use to build the agent, and whether they require human in the loop approval to be used:
    {tools}.

    With that information, your task is to determine whether each tool requires human in the loop approval to be used.
    To determine this, analyze the tool description and parameters and assess whether the tool may have undesired side effects or risks. Such as:
    - The tool may be used to send messages to external systems or users, which may be unwanted, or harmful.
    - The tool may be used to delete or modify data, which may be unwanted, or harmful.
    """
    for toolkit in ALL_OPTIMIZED_TOOLKITS:
        print(f"Processing {toolkit}...")
        print("Getting tools...")
        tools = await get_all_tools_from_mcp_server(toolkit, limit=100, client=client)
        print(f"Tools for {toolkit}: {len(tools)}")
        formatted_tools = format_tools_for_prompt(tools)

        prompt = prompt_template.format(tools=formatted_tools)
        hitl = hitl_template.format(tools=formatted_tools)
        print("Invoking OpenAI model for prompt...")
        prompt_response = invoke_openai_model(model="gpt-4o-mini", prompt=prompt)
        print("Invoking OpenAI model for hitl...")
        hitl_response = invoke_openai_model(model="gpt-4o-mini", prompt=hitl, schema=create_scoring_schema(tools))
        # Get a dict of the response and filter for True values
        hitl_tools = [key for key, value in hitl_response.model_dump().items() if value is True]
        print(f"Hitl tools for {toolkit}: {hitl_tools}")
        config = create_ts_langchain_config(toolkit, prompt_response, f"An agent that uses {toolkit} tools provided to perform any task", hitl_tools)
        # Write the config to a json file
        print(f"Writing config to agent-configurations/ts_langchain/ts-langchain-{toolkit}.json")
        with open(f"agent-configurations/ts_langchain/ts-langchain-{toolkit}.json", "w") as f:
            json.dump(config, f)



if __name__ == "__main__":
    asyncio.run(main())
