"""Smoke test: python server.py in one terminal, python test_client.py in another."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://turf-riverbank-passably.ngrok-free.dev/mcp"


async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("tools:", [t.name for t in (await s.list_tools()).tools])
            calls = [
                ("log_task", {"who": "Sam", "task": "booked dentist", "effort": 2, "invisible": True}),
                ("log_task", {"who": "Sam", "task": "planned meals", "effort": 3, "invisible": True}),
                ("log_task", {"who": "Alex", "task": "took out trash", "effort": 1}),
                ("get_balance", {}),
                ("suggest_handoff", {}),
                ("weekly_recap", {}),
            ]
            for name, args in calls:
                res = await s.call_tool(name, args)
                print(name, "->", res.content[0].text)

asyncio.run(main())
