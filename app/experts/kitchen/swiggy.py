"""QuickPick Kitchen - Swiggy Instamart core (Phase 1).
The model can look things up and fill the cart. It cannot place an order:
checkout is plain code, called only after a human says yes to the exact cart."""
import asyncio, json, os, re, time

from agents import Agent, Runner
from agents.mcp import MCPServerStdio, create_static_tool_filter
from pydantic import BaseModel

IM_URL = os.getenv("INSTAMART_MCP_URL", "https://mcp.swiggy.com/im")
MODEL = os.getenv("OPENAI_MODEL")                # empty = SDK default
CAP = float(os.getenv("CART_CAP", "1000"))       # our own safety cap, in rupees
CANCEL = "To cancel your order, please call Swiggy customer care at 080-67466729."
AGENT_TOOLS = ["get_addresses", "your_go_to_items", "search_products", "update_cart", "get_cart"]


def bridge(name, allowed=None):
    """Swiggy's documented mcp-remote bridge; sign-in is cached after the first run."""
    return MCPServerStdio(
        name=name,
        params={"command": "npx", "args": ["-y", "mcp-remote", IM_URL]},
        client_session_timeout_seconds=60,       # check_payment_status holds ~19 s
        cache_tools_list=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed) if allowed else None,
    )


def read(result):
    """Return (data, message). Data comes from structuredContent; failures raise."""
    text = next((c.text for c in (result.content or []) if getattr(c, "type", "") == "text"), "")
    sc = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None) or {}
    if not sc and text.lstrip().startswith("{"):
        try:
            sc = json.loads(text)
        except ValueError:
            sc = {}
    failed = getattr(result, "isError", False) or getattr(result, "is_error", False)
    if failed or (isinstance(sc, dict) and sc.get("success") is False):
        err = sc.get("error") if isinstance(sc, dict) else None
        raise RuntimeError(err.get("message") if isinstance(err, dict) else (err or text or "Swiggy call failed"))
    message = sc.get("message", "") if isinstance(sc, dict) else ""
    if isinstance(sc, dict) and isinstance(sc.get("data"), dict):
        sc = {**{k: v for k, v in sc.items() if k not in ("success", "data", "message")}, **sc["data"]}
    return sc, (message or text)


async def call(server, tool, args=None):
    return read(await server.call_tool(tool, args or {}))


def rupees(value):
    return float(re.sub(r"[^\d.]", "", str(value)) or 0)


async def pick_address(ops, hint=None):
    hint = (hint if hint is not None else os.getenv("ADDRESS_HINT", "")).lower()
    d, _ = await call(ops, "get_addresses")
    addrs = d.get("addresses", [])
    default_id = (d.get("resolution") or {}).get("defaultAddressId")
    hit = lambda a: hint and hint in f"{a.get('addressCategory', '')} {a.get('addressLine', '')}".lower()
    a = (next((a for a in addrs if hit(a)), None)
         or next((a for a in addrs if a.get("id") == default_id), None)
         or (addrs[0] if addrs else None))
    if not a:
        raise RuntimeError("No saved Swiggy address. Add one in the Swiggy app first.")
    return a


RULES = """You fill a Swiggy Instamart cart for an Indian household. You cannot place orders.
Delivery addressId: {aid}. Keep the total under Rs {cap:.0f}.
1. Call your_go_to_items first and prefer the family's usual products.
2. For anything else, call search_products with a short English query.
   Lists may be Telugu, Hindi or English: paalu = milk, perugu = curd, kandi pappu = toor dal,
   ullipayalu = onions, tamatalu = tomatoes, kottimeera = coriander.
3. Choose in-stock variations closest to the size asked for.
4. update_cart REPLACES the whole cart: send every item in ONE call with selectedAddressId
   and items [{{spinId, skuId, quantity}}].
5. Call get_cart, then answer with `note`: one or two lines on anything substituted or not found, and
   `missing`: every requested item that is NOT in the cart (not found or out of stock), in the family's words."""


class CartResult(BaseModel):
    note: str
    missing: list[str]


async def build_cart(agent_im, shopping_list, address_id):
    """Returns CartResult(note, missing). The model never sees checkout or payment tools."""
    agent = Agent(name="Kitchen cart builder",
                  instructions=RULES.format(aid=address_id, cap=CAP),
                  mcp_servers=[agent_im], output_type=CartResult,
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, shopping_list, max_turns=25)
    return run.final_output


def summary(cart, address, pay):
    rows = [f"  {i.get('itemName')} {i.get('itemVariant') or ''} x{i.get('quantity')}  Rs {i.get('discountedFinalPrice')}"
            for i in cart.get("items", [])]
    where = (cart.get("selectedAddressDetails") or {}).get("address") or address.get("addressLine")
    notes = [cart.get("addressWarning"), (cart.get("cartWarning") or {}).get("message")]
    notes += [f"Not available here: {i.get('itemName')}" for i in cart.get("unserviceableItems") or []]
    methods = [m.get("displayName") or m.get("id") for m in pay.get("allMethods", [])]
    return "\n".join(["Swiggy Instamart cart", *rows,
                      f"To pay: {cart['billBreakdown']['toPay']['value']}",
                      f"Your order will be delivered to: {where}",
                      f"Payment options: {', '.join(methods) or 'none returned'}",
                      *[f"Note: {n}" for n in notes if n]])


async def place(ops, address_id, approved_total, upi_app=None):
    """Call ONLY after the human said yes to this exact cart and address."""
    cart, _ = await call(ops, "get_cart")                     # stock and prices can change
    total = rupees(cart["billBreakdown"]["toPay"]["value"])
    if abs(total - approved_total) > 0.5:
        raise RuntimeError(f"Cart changed to Rs {total:.0f}. Show it again before placing.")
    if total > CAP:
        raise RuntimeError(f"Cart is Rs {total:.0f}, over the Rs {CAP:.0f} cap.")
    # Cash on delivery: get_payment_options labels it "COD", but checkout only accepts "Cash".
    args = {"addressId": address_id, "paymentMethod": "UPI" if upi_app else "Cash"}
    if upi_app:
        args["intentApp"] = upi_app                           # id copied exactly from get_payment_options
    try:
        return await call(ops, "checkout", args)
    except Exception as err:                                  # checkout is NOT idempotent: never retry blindly
        active, _ = await call(ops, "get_orders", {"activeOnly": True, "count": 3})
        ids = [o.get("orderId") for o in active.get("orders", [])]
        raise RuntimeError(f"Checkout failed ({err}). Active orders now: {ids}. Check them before trying again.")


async def finish_upi(ops, order):
    """Poll gently inside Swiggy's window; confirm only when Swiggy hasn't already."""
    deadline = time.monotonic() + order.get("maxTimeToPollForInMs", 300_000) / 1000
    ids = {"paasId": order["paasId"], "orderId": order["orderId"]}
    status, msg = {}, ""
    while time.monotonic() < deadline:
        status, msg = await call(ops, "check_payment_status", ids)
        if status.get("terminal"):
            break
        await asyncio.sleep(order.get("pollingIntervalInMs", 5000) / 1000)
    if status.get("terminal") and not status.get("isTerminalSuccess"):
        return False, msg or "Payment did not go through. Nothing was placed."
    if status.get("confirmed"):
        return True, msg
    done, msg = await call(ops, "confirm_order", ids)        # success not yet confirmed, or window ran out
    return done.get("result") == "success", msg


async def eta(ops, order_id, address_id):
    s, msg = await call(ops, "get_delivery_status", {"orderId": order_id, "addressId": address_id})
    return s.get("etaText") or s.get("statusText") or msg
