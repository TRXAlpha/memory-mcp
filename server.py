import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from graphiti_core import Graphiti
from mcp.server.fastmcp import FastMCP

load_dotenv()

AUTH_TOKEN = os.environ["MCP_AUTH_TOKEN"]

graphiti = Graphiti(
    os.environ["NEO4J_URI"],
    os.environ["NEO4J_USER"],
    os.environ["NEO4J_PASSWORD"],
)

mcp = FastMCP("agent-memory")

@mcp.tool()
async def write_memory(text: str, source_description: str = "agent_decision") -> str:
    """Log a decision, event, or fact into the graph memory."""
    await graphiti.add_episode(
        name=source_description,
        episode_body=text,
        source_description=source_description,
    )
    return "stored"

@mcp.tool()
async def query_graph(query: str) -> str:
    """Search graph memory for relevant facts/decisions/context."""
    results = await graphiti.search(query)
    return "\n".join(str(r) for r in results[:10])

@mcp.tool()
async def get_related(entity: str) -> str:
    """Get nodes/relations connected to a given entity."""
    results = await graphiti.search(entity)
    return "\n".join(str(r) for r in results[:15])

app = FastAPI()

@app.middleware("http")
async def check_auth(request, call_next):
    if request.headers.get("Authorization") != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(401, "unauthorized")
    return await call_next(request)

app.mount("/", mcp.sse_app())
