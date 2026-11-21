"""Pathya Kitchen - Zepto backup for items Swiggy Instamart could not supply.
Stricter than the Instamart path: the model gets NO Zepto tools. Code searches and fills the cart; the model only
picks variants from the search results it is shown (structured output), and every pick is checked against them.
Ordering (create_order) happens only in place(), only after a human tapped the card, and is never retried.
No price comparison: Zepto is used only for items Instamart did not have."""
import os
import re

from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from pydantic import BaseModel

from app.experts.kitchen.swiggy import CAP, call, rupees

URL = os.getenv("ZEPTO_MCP_URL", "https://mcp.zepto.co.in/mcp")
DEVICE = "quickpick"                                     # Zepto's fallback cart key
MODEL = os.getenv("OPENAI_MODEL")


def bridge(name="zepto-ops"):
    """Zepto only accepts sign-in redirects on "localhost" (mcp-remote defaults to 127.0.0.1)."""
    return MCPServerStdio(name=name, params={"command": "npx", "args": ["-y", "mcp-remote", URL, "--host", "localhost"]},
                          client_session_timeout_seconds=90)


async def select_address(z, hint=None):
    """Picks the saved address matching ADDRESS_HINT; this also sets Zepto's store for the session."""
    hint = (hint if hint is not None else os.getenv("ADDRESS_HINT", "")).lower()
    d, _ = await call(z, "list_saved_addresses")
    a = next((a for a in d.get("addresses", [])
              if hint and hint in f"{a.get('label', '')} {a.get('addressLine', '')}".lower()), None)
    if not a:
        raise RuntimeError(f"No saved Zepto address matches '{hint}'. Add it in the Zepto app first.")
    await call(z, "select_saved_address", {"addressId": a["id"]})
    return a


class Pick(BaseModel):
    item: str
    productVariantId: str
    storeProductId: str
    quantity: int


class Picks(BaseModel):
    picks: list[Pick]
    not_found: list[str]


class Queries(BaseModel):
    queries: list[str]


QUERIES = """Turn each grocery item (Telugu, Hindi or English, with quantities) into a short English product search
query, one per item, same order. No quantities or units. Examples: "2 litres paalu" -> "milk",
"half kg bellam" -> "jaggery", "1 bunch kottimeera" -> "coriander leaves", "perugu" -> "curd"."""


async def to_queries(items):
    agent = Agent(name="Zepto search terms", instructions=QUERIES, output_type=Queries,
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, "\n".join(items), max_turns=1)
    qs = run.final_output.queries
    return qs if len(qs) == len(items) else items


PICK = """Choose Zepto products for an Indian household's grocery items. You only choose; you cannot order.
For each item pick ONE product from that item's search results: in stock, closest to the size asked
(kottimeera = coriander leaves, not seeds; paalu = milk; perugu = curd). Quantity = packs needed.
Use the productVariantId and storeProductId exactly as shown. If nothing fits, put the item in not_found.
{advice}"""


async def pick(items, sections, advice=""):
    shown = [{"searched_for": s.get("query"), "products": [
        {k: p.get(k) for k in ("productVariantId", "storeProductId", "name", "packSize", "price", "availableQuantity")}
        for p in s.get("products", [])[:8]]} for s in sections]
    agent = Agent(name="Zepto picker", instructions=PICK.format(advice=advice), output_type=Picks,
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, f"Items: {items}\nSearch results: {shown}", max_turns=2)
    return checked(run.final_output, sections)


def checked(result, sections):
    """Keep only picks whose IDs really appeared in the search results and are in stock."""
    real = {(p["productVariantId"], p["storeProductId"]): p for s in sections for p in s.get("products", [])}
    good, dropped = [], list(result.not_found)
    for p in result.picks:
        product = real.get((p.productVariantId, p.storeProductId))
        if product and (product.get("availableQuantity") or 0) > 0 and 0 < p.quantity <= 10:
            good.append({"productVariantId": p.productVariantId, "storeProductId": p.storeProductId,
                         "quantity": p.quantity, "name": product.get("name", p.item)})
        else:
            dropped.append(p.item)
    return good, dropped


async def fill_cart(z, picks):
    """update_cart upserts, so items already in the Zepto cart are set to 0 first: the cart holds only our picks."""
    cart, _ = await call(z, "view_cart")
    keep = {p["productVariantId"] for p in picks}
    stale = [{"productVariantId": i["productVariantId"], "storeProductId": i["storeProductId"], "quantity": 0}
             for i in cart.get("items", []) if i["productVariantId"] not in keep]
    await call(z, "update_cart", {"deviceId": DEVICE, "cartItems": stale + picks})


async def quote(z):
    """The cart lines, the total Zepto will charge (fees included) and whether cash on delivery is offered."""
    cart, _ = await call(z, "view_cart")
    _, msg = await call(z, "get_payment_methods")
    m = re.search(r"Order Total:\s*₹\s*([\d,\.]+)", msg)
    if not m:
        raise RuntimeError("Zepto did not return an order total.")
    available = msg.split("Unavailable methods", 1)[0]
    return cart, rupees(m.group(1)), "(COD)" in available


async def build(z, items, hint=None, advice=""):
    addr = await select_address(z, hint)
    await call(z, "get_past_order_items")                 # Zepto asks for this before any search
    sections, _ = await call(z, "search_multiple_products", {"queries": await to_queries(items)})
    picks, not_found = await pick(items, sections.get("sections", []), advice)
    if not picks:
        return addr, None, not_found
    await fill_cart(z, picks)
    cart, total, cod = await quote(z)
    return addr, {"cart": cart, "total": total, "cod": cod}, not_found


async def place(z, address_id, approved_total):
    """Call ONLY after a human tapped cash on delivery on this exact cart. Preview first; never retry."""
    _, total, cod = await quote(z)                        # stock and prices can change
    if abs(total - approved_total) > 0.5:
        raise RuntimeError(f"Zepto cart changed to Rs {total:.0f}. Show it again before placing.")
    if total > CAP:
        raise RuntimeError(f"Zepto cart is Rs {total:.0f}, over the Rs {CAP:.0f} cap.")
    if not cod:
        raise RuntimeError("Zepto no longer offers cash on delivery for this cart.")
    await call(z, "create_order", {"confirmOrder": False, "userAddressId": address_id})   # Zepto's own preview step
    try:
        return await call(z, "create_order", {"confirmOrder": True, "userAddressId": address_id})
    except Exception as err:                              # not idempotent: never retry blindly
        recent, msg = await call(z, "list_order_history", {"limit": 3})
        raise RuntimeError(f"Zepto order failed ({err}). Recent orders: {msg[:300]} Check them before trying again.")
