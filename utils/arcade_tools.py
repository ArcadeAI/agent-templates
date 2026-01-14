from arcadepy import AsyncArcade
import asyncio
import json
from collections import defaultdict
from rich import print
from dotenv import load_dotenv

load_dotenv()


async def get_all_tools_from_mcp_server(
    mcp_server: str,
    limit: int = 100,
    client: AsyncArcade | None = None,
):
    if client is None:
        client = AsyncArcade()
    tools = await client.tools.list(limit=limit, toolkit=mcp_server)
    all_tools = tools.items
    total_count = tools.total_count
    total_pages = total_count // limit
    if total_count % limit != 0:
        total_pages += 1
    for page in range(1, total_pages):
        tools = await client.tools.list(offset=page * limit, limit=limit, toolkit=mcp_server)
        all_tools.extend(tools.items)
    return all_tools



async def main():
    client = AsyncArcade()
    limit = 100
    tools = await client.tools.list(limit=limit)
    downloaded_tools = []
    total_count = tools.total_count
    offset = tools.offset
    all_toolkits = set()
    total_pages = total_count // limit
    if total_count % limit != 0:
        total_pages += 1
    page = 0
    mcp_server_to_tool = defaultdict(list)
    while page < total_pages:
        print("--------------------------------")
        print(f"Downloading page: {page}")
        print(f"Offset: {offset}")
        print(f"Limit: {limit}")
        print(f"Total count: {total_count}")
        page += 1
        tools = await client.tools.list(offset=offset, limit=limit)
        offset += len(tools.items)
        for tool in tools.items:
            downloaded_tools.append(tool)
            all_toolkits.add(tool.toolkit.name)
            mcp_server_to_tool[tool.toolkit.name].append(tool.name)
    print(len(downloaded_tools))
    print(len(all_toolkits))
    # write mcp_server_to_tool to a json file
    with open("mcp_server_to_tool.json", "w") as f:
        json.dump(mcp_server_to_tool, f)


if __name__ == "__main__":
    asyncio.run(main())