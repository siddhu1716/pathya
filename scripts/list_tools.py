"""Read-only: sign in (first run opens the browser for phone + OTP) and print every tool an MCP server offers.
python scripts/list_tools.py swiggy-im | zepto | swiggy-food | swiggy-dineout   (add --schema for input schemas)
Saves the list to docs/mcp_tools/<name>.json so the code can be written against the real tool names."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from agents.mcp import MCPServerStdio

SERVERS = {
    "swiggy-im": "https://mcp.swiggy.com/im",
    "swiggy-food": "https://mcp.swiggy.com/food",
    "swiggy-dineout": "https://mcp.swiggy.com/dineout",
    "zepto": "https://mcp.zepto.co.in/mcp",
}
# Zepto's sign-in only accepts redirect URIs on "localhost"; mcp-remote defaults to 127.0.0.1 (403 at registration).
EXTRA_ARGS = {"zepto": ["--host", "localhost"]}


async def main(name, schema):
    server = MCPServerStdio(name=name, params={"command": "npx",
                                               "args": ["-y", "mcp-remote", SERVERS[name], *EXTRA_ARGS.get(name, [])]},
                            client_session_timeout_seconds=120)
    async with server:
        tools = await server.list_tools()
    rows = [{"name": t.name, "description": (t.description or "").strip(),
             "input_schema": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)} for t in tools]
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "mcp_tools")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    for r in rows:
        print(f"- {r['name']}: {r['description'].splitlines()[0] if r['description'] else ''}")
        if schema:
            print(json.dumps(r["input_schema"], indent=2, ensure_ascii=False))
    print(f"\n{len(rows)} tools. Saved to docs/mcp_tools/{name}.json")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in SERVERS:
        sys.exit(f"usage: python scripts/list_tools.py {{{'|'.join(SERVERS)}}} [--schema]")
    asyncio.run(main(sys.argv[1], "--schema" in sys.argv))
