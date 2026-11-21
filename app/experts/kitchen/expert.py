"""Kitchen Expert: a list (from a call, a voice note or typing) -> Swiggy Instamart cart
-> one human tap -> order. Items Instamart can't supply get a separate Zepto card (availability, not price).
Ordering rules live in swiggy.py and zepto.py (tested); this file wires them in."""
import os

from app.experts.base import CallPlan, Card, Expert
from app.experts.kitchen import swiggy as sw
from app.experts.kitchen import zepto as zp

LIST_CALL = """You are QuickPick, an AI assistant, calling {who} for {user}'s family to take this week's grocery list.
Your first sentence: "{greeting}" After it, speak {lang}, simply and politely (mixing in common English words
is fine); if they answer in another language, continue in theirs.
Ask what the kitchen needs this week; ask for quantities when missing.
You may remind them of at most three usual items: {usual}.
Call save_list with one entry per item, quantity included, in their words (for example "2 litres paalu").
Read the list back, at most three items at a time, fix corrections, then call save_list again with the final list.
Never discuss prices or payment. Finish with end_call."""


def dry_run():
    return os.getenv("DRY_RUN", "1") == "1"          # default: no real checkout while building


def for_people(msg):
    """Swiggy's message exactly as sent, minus the instructions it appends for AI clients
    ("[IMPORTANT: Display the above message exactly as-is ...]", "⚠️ A rich UI widget ...")."""
    for marker in ("[IMPORTANT", "⚠️ A rich UI widget"):
        if marker in msg:
            msg = msg.split(marker, 1)[0]
    return msg.strip()


class KitchenExpert(Expert):
    name, title = "kitchen", "Kitchen Expert"
    handles = "groceries, milk, vegetables, kitchen supplies, the weekly list, reorders, meal-plan ingredients"
    call_kinds = {"list"}

    def __init__(self, store, household, agent_im, ops, zepto=None):
        self.store, self.hh, self.agent_im, self.ops, self.zepto = store, household, agent_im, ops, zepto

    def weekly_call(self, person, run_at=None):
        p = self.hh["people"][person]
        return self.store.add_job(self.name, "list", person, {"person": person, "to": p["phone"]}, run_at)

    def call_plan(self, job):
        p, user = self.hh["people"][job["payload"]["person"]], self.hh["user"]["name"]
        usual = [str(f["value"]) for f in self.store.facts(prefix="usual:")][:3]
        greeting = f"Namaskaram {p['name']}, I am QuickPick, an AI assistant calling for {user} about this week's groceries."
        plan = CallPlan(LIST_CALL.format(who=p["name"], user=user, greeting=greeting,
                                         lang=p.get("language", "Telugu"), usual=", ".join(usual) or "none"),
                        greeting, max_minutes=5)

        def save_list(items: list[str], notes: str) -> str:
            """Save the grocery list: one entry per item, with quantity, in the person's words."""
            plan.saved.update(items=items, notes=notes)
            return "Saved. Read it back, at most three items at a time."

        def end_call(summary: str) -> str:
            """Finish the call with a one-line English summary."""
            plan.saved["summary"] = summary
            return "Say goodbye now."

        plan.tools = [save_list, end_call]
        return plan

    async def after_call(self, job, saved):
        items = saved.get("items") or []
        return await self.handle(", ".join(items), ref=job["id"]) if items else None

    async def handle(self, text, ref=None):
        advice = [str(f["value"]) for f in self.store.facts(prefix="advice:")]
        advice_note = ("Doctor's advice in this home (use it only to choose between products, "
                       "for example low-sodium salt; never add items because of it): " + "; ".join(advice)) if advice else ""
        if advice_note:
            text += "\n" + advice_note
        addr = await sw.pick_address(self.ops, self.hh.get("address_hint"))
        result = await sw.build_cart(self.agent_im, text, addr["id"])
        note, missing = (result.note, list(result.missing)) if hasattr(result, "note") else (str(result), [])
        cart, _ = await sw.call(self.ops, "get_cart")
        pay, _ = await sw.call(self.ops, "get_payment_options")
        missing += [i.get("itemName") for i in cart.get("unserviceableItems") or [] if i.get("itemName")]
        card = self.card(cart, pay, addr, note, ref)
        if missing and self.zepto is not None:
            card.warnings.append(await self.zepto_backup(missing, advice_note, ref))
        return card

    async def zepto_backup(self, missing, advice_note="", ref=None):
        """Items Instamart could not supply -> a separate Zepto card. Availability only, never a price comparison."""
        try:
            addr, quote, not_found = await zp.build(self.zepto, missing, self.hh.get("address_hint"), advice_note)
        except Exception as err:
            return f"Not on Instamart: {', '.join(missing)}. Zepto backup failed: {err}"
        if not quote:
            return f"Not on Instamart or Zepto: {', '.join(missing)}."
        lines = [f"{i.get('name')} x{i.get('quantity')} - Rs {(i.get('price') or 0) / 100:.0f}"
                 for i in quote["cart"].get("items", [])]
        warnings = [f"Not found on Zepto either: {', '.join(not_found)}"] if not_found else []
        if not quote["cod"]:
            warnings.append("Zepto did not offer cash on delivery for this cart.")
        total = f"₹{quote['total']:.0f}"
        self.store.add_card(Card(self.name, "order", "Zepto cart (items Instamart didn't have)", lines,
                                 total=total, address=addr.get("addressLine"),
                                 question="Do you want to proceed with placing this order to this address?",
                                 choices=[{"id": "COD", "label": "Cash on delivery"}] if quote["cod"] else [],
                                 warnings=warnings,
                                 payload={"store": "zepto", "address_id": addr["id"],
                                          "approved_total": quote["total"], "ref": ref}).to_dict())
        return f"Not on Instamart: {', '.join(missing)}. A separate Zepto card is ready for them."

    def card(self, cart, pay, addr, note="", ref=None):
        total = cart["billBreakdown"]["toPay"]["value"]
        choices = [{"id": "COD", "label": "Cash on delivery"}] if (pay.get("cod") or {}).get("available") else []
        for m in ((pay.get("platforms") or {}).get("mobile") or {}).get("methods", []):
            choices.append({"id": "UPI:" + m["id"], "label": "UPI - " + (m.get("displayName") or m["id"])})
        warnings = [w for w in (cart.get("addressWarning"), (cart.get("cartWarning") or {}).get("message")) if w]
        warnings += [f"Not available here: {i.get('itemName')}" for i in cart.get("unserviceableItems") or []]
        stores = {i.get("storeId") for i in cart.get("items", []) if i.get("storeId")}
        if len(stores) > 1:
            warnings.append(f"This cart comes from {len(stores)} stores and will arrive as {len(stores)} orders.")
        if not choices:
            warnings.append("Swiggy returned no payment options for this cart.")
        if note:
            warnings.append(f"Agent: {note}")
        lines = [" ".join(str(x) for x in (i.get("itemName"), i.get("itemVariant"), f"x{i.get('quantity')}",
                                            f"- Rs {i.get('discountedFinalPrice')}") if x) for i in cart.get("items", [])]
        where = (cart.get("selectedAddressDetails") or {}).get("address") or addr.get("addressLine")
        return Card(self.name, "order", "Swiggy Instamart cart", lines, total=total, address=where,
                    question="Do you want to proceed with placing this order to this address?",
                    choices=choices, warnings=warnings,
                    payload={"address_id": addr["id"], "approved_total": sw.rupees(total), "ref": ref})

    async def execute(self, card, choice):
        p = card["payload"]
        upi_app = choice.split(":", 1)[1] if choice.startswith("UPI:") else None
        if dry_run():
            return {"ok": True, "dry_run": True,
                    "message": f"DRY RUN: would place {card['total']} by {'UPI' if upi_app else 'cash on delivery'}."}
        if p.get("store") == "zepto":
            if choice != "COD":
                raise RuntimeError("Zepto orders here are cash on delivery only.")
            order, msg = await zp.place(self.zepto, p["address_id"], p["approved_total"])
            return {"ok": True, "message": msg.strip(), "order": order}
        order, msg = await sw.place(self.ops, p["address_id"], p["approved_total"], upi_app)
        out = {"ok": True, "message": for_people(msg), "order": order, "cancel": sw.CANCEL}
        if order.get("status") == "PENDING_PAYMENT":
            out["pay_url"] = order["bridgeUrl"]       # open it; run settle() in the background
        else:
            out["eta"] = await self.etas(order, p["address_id"])
        return out

    async def settle(self, order):
        """UPI only: wait for the payment inside Swiggy's window; confirm only if needed."""
        ok, msg = await sw.finish_upi(self.ops, order)
        return ok, for_people(msg)

    async def eta(self, order_id, address_id):
        return await sw.eta(self.ops, order_id, address_id)

    async def etas(self, order, address_id):
        """Multi-store carts come back as several orders; an ETA lookup failure never fails the order."""
        out = {}
        for o in order.get("orders") or [order]:
            if o.get("orderId"):
                try:
                    out[o["orderId"]] = await self.eta(o["orderId"], address_id)
                except Exception as err:
                    out[o["orderId"]] = f"ETA unavailable ({err})"
        return out
