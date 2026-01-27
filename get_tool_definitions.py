import asyncio
import json
from dotenv import load_dotenv
from utils.arcade_tools import (
    get_all_tools_from_mcp_server,
    serializable_tool_definition
)

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


async def main():
    mcp_servers_definitions = {}
    for toolkit in ALL_OPTIMIZED_TOOLKITS:
        tools = await get_all_tools_from_mcp_server(toolkit)
        mcp_servers_definitions[toolkit] = [await serializable_tool_definition(t) for t in tools]

    with open("tool-definitions.json", "w") as f:
        json.dump(mcp_servers_definitions, f)

if __name__ == "__main__":
    asyncio.run(main())
