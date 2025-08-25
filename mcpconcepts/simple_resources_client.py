import asyncio
from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8003/mcp"
HELLO_URI = "res://hello.txt"
TIME_URI = "res://time.json"


def _extract_text_from_resource(res_read) -> str:
    """Normalize possible fastmcp resource read shapes to text."""
    # fastmcp may return:
    # - a list[TextContent]
    # - an object with .contents
    # - an object with .resource.contents
    if isinstance(res_read, list):
        return res_read[0].text
    contents = getattr(res_read, "contents", None)
    if contents is None:
        resource_obj = getattr(res_read, "resource", None)
        contents = getattr(resource_obj, "contents", None)
    return contents[0].text


async def main():
    client = Client(SERVER_URL)
    async with client:
        # List resources
        res_list = await client.list_resources()
        print("Resources:", [getattr(r, "uri", str(r)) for r in res_list])

        # Read static text resource
        hello_read = await client.read_resource(HELLO_URI)
        hello_text = _extract_text_from_resource(hello_read)
        print(f"\nRead {HELLO_URI}:\n{hello_text}")

        # Read dynamic time resource
        time_read = await client.read_resource(TIME_URI)
        time_text = _extract_text_from_resource(time_read)
        print(f"\nRead {TIME_URI}:\n{time_text}")


if __name__ == "__main__":
    asyncio.run(main())
