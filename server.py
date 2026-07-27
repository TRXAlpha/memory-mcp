import os
import contextlib
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from graphiti_core import Graphiti
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv()

AUTH_TOKEN = os.environ["MCP_AUTH_TOKEN"]

graphiti = Graphiti(
    os.environ["NEO4J_URI"],
    os.environ["NEO4J_USER"],
    os.environ["NEO4J_PASSWORD"],
)

mcp = FastMCP(
    "agent-memory",
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


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


# FastMCP's streamable_http_app needs its session_manager task group
# started under a live lifespan. Mounting it into FastAPI doesn't do
# this automatically -> must wire the sub-app's lifespan into the
# parent app's lifespan manually, or requests 500 with
# "Task group is not initialized."
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def check_auth(request: Request, call_next):
    if request.headers.get("Authorization") != f"Bearer {AUTH_TOKEN}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


app.mount("/", mcp.streamable_http_app())
