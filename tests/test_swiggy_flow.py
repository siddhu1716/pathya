import os
import sys, types, asyncio, json
ag = types.ModuleType("agents"); ag.Agent = object; ag.Runner = object
mcp = types.ModuleType("agents.mcp"); mcp.MCPServerStdio = object; mcp.create_static_tool_filter = lambda **k: k
sys.modules["agents"] = ag; sys.modules["agents.mcp"] = mcp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.experts.kitchen import swiggy as k

class T:  # text block
    def __init__(s, t): s.type, s.text = "text", t
class R:  # CallToolResult stand-in
    def __init__(s, sc=None, text="", err=False): s.structuredContent, s.content, s.isError = sc, [T(text)], err

CART = {"items": [{"itemName": "Heritage Toned Milk", "itemVariant": "500 ml", "quantity": 2, "discountedFinalPrice": 56}],
        "billBreakdown": {"toPay": {"label": "To pay", "value": "₹131"}},
        "selectedAddressDetails": {"address": "RMZ The Loft, Raidurg"}, "cartWarning": {"statusCode": 1, "message": "Min order ₹99"}}
class Fake:
    def __init__(s, script): s.script, s.calls = script, []
    async def call_tool(s, name, args):
        s.calls.append((name, args)); v = s.script[name]
        return v.pop(0) if isinstance(v, list) else v

async def run():
    # read(): envelope unwrapping + error raising
    d, m = k.read(R(text=json.dumps({"success": True, "data": {"a": 1}, "message": "Instamart order placed successfully"})))
    assert d == {"a": 1} and m == "Instamart order placed successfully"
    try: k.read(R(sc={"success": False, "error": {"message": "Address not serviceable"}})); assert False
    except RuntimeError as e: assert "serviceable" in str(e)
    assert k.rupees("₹1,031.50") == 1031.5
    print(k.summary(CART, {"addressLine": "x"}, {"allMethods": [{"id": "cod", "displayName": "Cash"}]}))
    # COD path
    f = Fake({"get_cart": R(sc=CART), "checkout": R(sc={"orderId": "O1", "status": "PLACED", "paymentMethod": "COD"}, text="Instamart order placed successfully")})
    d, m = await k.place(f, "A1", 131); assert d["orderId"] == "O1" and m.startswith("Instamart")
    assert f.calls[-1] == ("checkout", {"addressId": "A1", "paymentMethod": "Cash"})
    # cart changed since approval -> refuse
    try: await k.place(Fake({"get_cart": R(sc=CART)}), "A1", 120); assert False
    except RuntimeError as e: assert "changed" in str(e)
    # over cap -> refuse
    big = json.loads(json.dumps(CART)); big["billBreakdown"]["toPay"]["value"] = "₹1,200"
    try: await k.place(Fake({"get_cart": R(sc=big)}), "A1", 1200); assert False
    except RuntimeError as e: assert "cap" in str(e)
    # checkout error -> looks up active orders, no retry
    f = Fake({"get_cart": R(sc=CART), "checkout": R(sc={"success": False, "error": {"message": "502"}}), "get_orders": R(sc={"orders": [{"orderId": "O9"}]})})
    try: await k.place(f, "A1", 131); assert False
    except RuntimeError as e: assert "O9" in str(e) and [c[0] for c in f.calls].count("checkout") == 1
    # UPI: pending -> success, already confirmed by Swiggy -> no confirm_order call
    order = {"orderId": "O2", "paasId": "P2", "pollingIntervalInMs": 10, "maxTimeToPollForInMs": 2000}
    f = Fake({"check_payment_status": [R(sc={"terminal": False}), R(sc={"terminal": True, "isTerminalSuccess": True, "confirmed": True}, text="Instamart order placed successfully")]})
    ok, m = await k.finish_upi(f, order); assert ok and "confirm_order" not in [c[0] for c in f.calls]
    # UPI: success but not confirmed -> confirm once with orderId + paasId
    f = Fake({"check_payment_status": R(sc={"terminal": True, "isTerminalSuccess": True}), "confirm_order": R(sc={"orderId": "O2", "result": "success"}, text="Instamart order placed successfully")})
    ok, m = await k.finish_upi(f, order); assert ok and f.calls[-1] == ("confirm_order", {"paasId": "P2", "orderId": "O2"})
    # UPI: failed -> never confirm
    f = Fake({"check_payment_status": R(sc={"terminal": True, "isTerminalFailure": True, "status": "failed"})})
    ok, m = await k.finish_upi(f, order); assert not ok and "confirm_order" not in [c[0] for c in f.calls]
    # UPI: window runs out while pending -> confirm once
    f = Fake({"check_payment_status": R(sc={"terminal": False}), "confirm_order": R(sc={"result": "pending"})})
    ok, m = await k.finish_upi(f, {**order, "maxTimeToPollForInMs": 50}); assert not ok and [c[0] for c in f.calls].count("confirm_order") == 1
    print("ALL FLOW CHECKS PASSED")
asyncio.run(run())
