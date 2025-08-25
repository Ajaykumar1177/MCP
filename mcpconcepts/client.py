import asyncio
from fastmcp import Client

async def main():
    math_client = Client("http://127.0.0.1:8000/mcp")  # math_server
    text_client = Client("http://127.0.0.1:8001/mcp")  # text_server

    async with math_client, text_client:
        # Call math tool
        math_result = await math_client.call_tool("multiply", {"a": 6, "b": 7})
        print("Math Result:", math_result.content[0].text)

        # Call text tool
        text_result = await text_client.call_tool("reverse", {"text": "hello"})
        print("Text Result:", text_result.content[0].text)

asyncio.run(main())
