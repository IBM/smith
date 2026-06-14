from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from app import getEvents

# Initialize MCP server
mcp = FastMCP("call-for-papers-mcp")

@mcp.tool()
async def get_events(keywords: str, topic: str, limit: int = 10) -> Dict[str, Any]:
    """Search for conferences matching specific keywords.

    Args:
        keywords: Free-text search terms passed to WikiCFP (e.g. "deep learning", "NLP").
        topic: The research-domain category this search belongs to. Must be
            EXACTLY one of these three approved values (verbatim, including
            capitalization): "Artificial intelligence", "Cybersecurity and
            privacy", "Software engineering". Used for policy-level topic
            scoping against the agent's approved topics.
        limit: Maximum number of events to return.
    """
    return getEvents(keywords, limit)

if __name__ == "__main__":
    mcp.run(transport="stdio")
