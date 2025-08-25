import asyncio
from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8002/mcp"
RESOURCE_URI = "res://hello.txt"
PROMPT_NAME = "greeting"

async def main():
    client = Client(SERVER_URL)
    async with client:
        # List resources
        res_list = await client.list_resources()
        print("Resources:", [getattr(r, "uri", str(r)) for r in res_list])

        # Read resource
        res_read = await client.read_resource(RESOURCE_URI)
        # fastmcp may return:
        # - a list[TextContent]
        # - an object with .contents
        # - an object with .resource.contents
        if isinstance(res_read, list):
            text = res_read[0].text
        else:
            contents = getattr(res_read, "contents", None)
            if contents is None:
                resource_obj = getattr(res_read, "resource", None)
                contents = getattr(resource_obj, "contents", None)
            text = contents[0].text
        print(f"\nRead {RESOURCE_URI}:\n{text}")

        # List prompts
        pr_list = await client.list_prompts()
        print("\nPrompts:", [getattr(p, "name", str(p)) for p in pr_list])

        # Get prompt
        prompt = await client.get_prompt(PROMPT_NAME, {"name": "Ajay"}) 
        # fastmcp returns a Prompt object with messages/content
        pm = getattr(prompt, "messages", None) or getattr(prompt, "prompt", None)
        # Normalize to the object that has .messages
        carrier = pm if (pm and hasattr(pm, "messages")) else prompt
        first_content = carrier.messages[0].content
        if isinstance(first_content, list):
            prompt_text = first_content[0].text
        else:
            # already a TextContent
            prompt_text = first_content.text
        print(f"\nPrompt '{PROMPT_NAME}' content:\n{prompt_text}")

if __name__ == "__main__":
    asyncio.run(main())
