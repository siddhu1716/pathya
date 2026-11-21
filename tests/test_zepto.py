"""Zepto backup checks with a fake Zepto MCP (no network, no real orders)."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.store import Store
from app.experts.kitchen import swiggy as sw
from app.experts.kitchen import zepto as zp
from app.experts.kitchen.expert import KitchenExpert


class T:
    def __init__(self, x): self.type, self.text = "text", x


class R:
    def __init__(self, sc=None, x="", err=False): self.structuredContent, self.content, self.isError = sc, [T(x)], err


PAY = R({}, "💳 Available Payment Methods\n\nOrder Total: ₹50\n\n1. **Cash on Delivery** (COD)\n\n"
            "Unavailable methods:\n- Zepto Cash (Wallet)")
NO_COD = R({}, "Order Total: ₹50\n\n1. **Pay Online** (PAYMENT_LINK)\n\nUnavailable methods:\n- Cash on Delivery (COD)")
CART = R({"items": [{"productVariantId": "pv1", "storeProductId": "sp1", "name": "Coriander Leaves", "quantity": 1,
                     "price": 2000}]}, "cart")


class Zepto:
    def __init__(self, script): self.script, self.calls = script, []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        v = self.script[name]
        return v.pop(0) if isinstance(v, list) else v


def names(z): return [n for n, _ in z.calls]


SECTIONS = [{"query": "kottimeera", "products": [
    {"productVariantId": "pv1", "storeProductId": "sp1", "name": "Coriander Leaves", "availableQuantity": 5},
    {"productVariantId": "pv2", "storeProductId": "sp2", "name": "Coriander Seeds", "availableQuantity": 0}]}]


def test_picks_must_come_from_search_results_and_be_in_stock():
    res = zp.Picks(picks=[zp.Pick(item="kottimeera", productVariantId="pv1", storeProductId="sp1", quantity=1),
                          zp.Pick(item="seeds", productVariantId="pv2", storeProductId="sp2", quantity=1),
                          zp.Pick(item="made up", productVariantId="pvX", storeProductId="spX", quantity=1)],
                   not_found=["jaggery"])
    good, dropped = zp.checked(res, SECTIONS)
    assert [g["productVariantId"] for g in good] == ["pv1"] and dropped == ["jaggery", "seeds", "made up"]


def test_quote_reads_total_and_cash_option():
    _, total, cod = asyncio.run(zp.quote(Zepto({"view_cart": CART, "get_payment_methods": PAY})))
    assert total == 50 and cod
    assert asyncio.run(zp.quote(Zepto({"view_cart": CART, "get_payment_methods": NO_COD})))[2] is False


def test_place_rechecks_total_and_never_retries():
    z = Zepto({"view_cart": CART, "get_payment_methods": PAY})
    with pytest.raises(RuntimeError, match="changed"):
        asyncio.run(zp.place(z, "a1", 40))
    assert "create_order" not in names(z)

    ok = Zepto({"view_cart": CART, "get_payment_methods": PAY,
                "create_order": [R({}, "Preview"), R({"orderId": "Z1"}, "Order placed")]})
    order, msg = asyncio.run(zp.place(ok, "a1", 50))
    assert order["orderId"] == "Z1" and [a["confirmOrder"] for n, a in ok.calls if n == "create_order"] == [False, True]

    bad = Zepto({"view_cart": CART, "get_payment_methods": PAY, "list_order_history": R({}, "1. Z9 placed"),
                 "create_order": [R({}, "Preview"), R({"success": False, "error": {"message": "502"}})]})
    with pytest.raises(RuntimeError, match="Z9"):
        asyncio.run(zp.place(bad, "a1", 50))
    assert names(bad).count("create_order") == 2                   # one preview, one attempt, no retry


def test_fill_cart_clears_other_items():
    z = Zepto({"view_cart": R({"items": [{"productVariantId": "old", "storeProductId": "so"}]}), "update_cart": R({}, "ok")})
    asyncio.run(zp.fill_cart(z, [{"productVariantId": "pv1", "storeProductId": "sp1", "quantity": 1, "name": "x"}]))
    sent = z.calls[-1][1]["cartItems"]
    assert {"productVariantId": "old", "storeProductId": "so", "quantity": 0} in sent and sent[-1]["productVariantId"] == "pv1"


def test_kitchen_makes_zepto_card_for_missing_items(monkeypatch):
    hh = {"user": {"name": "Shiva"}, "people": {}, "clinics": {}, "address_hint": "Loft"}
    store = Store(":memory:")

    async def fake_pick_address(ops, hint=None): return {"id": "addr1", "addressLine": "RMZ The Loft"}

    async def fake_build_cart(agent_im, text, aid): return sw.CartResult(note="No kottimeera.", missing=["kottimeera"])

    async def fake_zepto_build(z, items, hint=None, advice=""):
        assert items == ["kottimeera"]
        return {"id": "za1", "addressLine": "Equal HQ"}, {"cart": {"items": [{"name": "Coriander Leaves", "quantity": 1,
                                                                               "price": 2000}]}, "total": 50.0, "cod": True}, []

    monkeypatch.setattr(sw, "pick_address", fake_pick_address)
    monkeypatch.setattr(sw, "build_cart", fake_build_cart)
    monkeypatch.setattr(zp, "build", fake_zepto_build)
    ops = Zepto({"get_cart": R({"items": [], "billBreakdown": {"toPay": {"value": "₹99"}}}),
                 "get_payment_options": R({"cod": {"available": True}})})
    k = KitchenExpert(store, hh, None, ops, zepto=object())
    card = asyncio.run(k.handle("milk, kottimeera"))
    assert any("Zepto card is ready" in w for w in card.warnings)
    zc = store.cards()[0]["card"]
    assert zc["payload"]["store"] == "zepto" and zc["total"] == "₹50" and zc["lines"] == ["Coriander Leaves x1 - Rs 20"]
    assert zc["question"] == "Do you want to proceed with placing this order to this address?"
    monkeypatch.setenv("DRY_RUN", "1")
    assert asyncio.run(k.execute(zc, "COD"))["dry_run"]
