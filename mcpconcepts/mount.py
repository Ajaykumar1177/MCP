from fastmcp import FastMCP

agent = FastMCP("Agent Server")

# Mount other servers
agent.import_server("http://localhost:8000")  # math
agent.import_server("http://localhost:8001")  # text

if __name__ == "__main__":
    agent.run()
