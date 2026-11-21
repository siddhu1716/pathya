"""Kitchen Expert: a list (from a call, a voice note or typing) -> Swiggy Instamart cart
-> one human tap -> order. Items Instamart can't supply get a separate Zepto card (availability, not price).
Ordering rules live in swiggy.py and zepto.py (tested); this file wires them in."""
import os
import time

from app.experts.base import CallPlan, Card, Expert
from app.experts.kitchen import planner as pl
from app.experts.kitchen import swiggy as sw
from app.experts.kitchen import zepto as zp

LIST_CALL = """You are QuickPick, an AI assistant, talking with {who} for {user}'s family to take this week's grocery list.
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


MENU_CALL = """You are QuickPick, an AI assistant, calling {who} for {user}'s family about tomorrow's cooking.
Your first sentence: "{greeting}" After it, speak {lang}, simply and politely; if they answer in another language,
continue in theirs. Tomorrow's menu: {menu}.
Read the menu, at most three dishes at a time. Ask whether anything is missing in the kitchen to cook it.
Call save_missing with every missing item and quantity in their words (an empty list if nothing is missing).
Never discuss prices, payment, health or diets. Finish with end_call."""


class KitchenExpert(Expert):
    name, title = "kitchen", "Kitchen Expert"
    handles = "groceries, milk, vegetables, kitchen supplies, the weekly list, reorders, meal-plan ingredients"
    call_kinds = {"list", "menu"}

    def __init__(self, store, household, agent_im, ops, zepto=None):
        self.store, self.hh, self.agent_im, self.ops, self.zepto = store, household, agent_im, ops, zepto

    def weekly_call(self, person, run_at=None):
        p = self.hh["people"][person]
        return self.store.add_job(self.name, "list", person, {"person": person, "to": p["phone"]}, run_at)

    def answered(self, person, call_sid):
        """A household member phoned QuickPick: a list call that has already 'run' (never dialled)."""
        jid = self.store.add_job(self.name, "list", person, {"person": person, "direction": "inbound"}, run_at=4102444800)
        self.store.start_job(jid)
        self.store.end_job(jid, True, {"call_sid": call_sid})
        return jid

    def call_plan(self, job):
        if job["kind"] == "menu":
            return self._menu_plan(job)
        p, user = self.hh["people"][job["payload"]["person"]], self.hh["user"]["name"]
        usual = [f"{u['typical']} x {u['name']}" for u in pl.usuals(self.store, 3)]
        if job["payload"].get("direction") == "inbound":
            greeting = f"Namaskaram {p['name']}, I am QuickPick, an AI assistant answering for {user}. What does the kitchen need?"
        else:
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
        if job.get("kind") == "menu":
            missing = saved.get("missing") or []
            if not missing:
                return Card(self.name, "info", "The cook has everything for tomorrow",
                            [saved.get("summary") or "Nothing missing."], question="", choices=[{"id": "ok", "label": "OK"}])
            return await self.handle(", ".join(missing), ref=job["id"])
        items = saved.get("items") or []
        return await self.handle(", ".join(items), ref=job["id"]) if items else None

    # ---- meal plans, the cook's menu call, nutrition ----
    def menu_call(self, person, menu, run_at=None):
        p = self.hh["people"][person]
        return self.store.add_job(self.name, "menu", person, {"person": person, "to": p["phone"], "menu": menu}, run_at)

    def _menu_plan(self, job):
        pay = job["payload"]
        p, user = self.hh["people"][pay["person"]], self.hh["user"]["name"]
        menu = "; ".join(f"{m['slot']}: {m['dish']}" for m in pay["menu"].get("meals", [])) or "not set"
        greeting = f"Namaskaram {p['name']}, I am QuickPick, an AI assistant calling for {user} about tomorrow's menu."
        plan = CallPlan(MENU_CALL.format(who=p["name"], user=user, greeting=greeting, lang=p.get("language", "Telugu"),
                                         menu=menu), greeting, max_minutes=4)

        def save_missing(items: list[str], notes: str) -> str:
            """Save what is missing in the kitchen for tomorrow's menu, with quantities, in the cook's words."""
            plan.saved.update(missing=items, notes=notes)
            return "Saved. Read the missing items back, at most three at a time."

        def end_call(summary: str) -> str:
            """Finish the call with a one-line English summary."""
            plan.saved["summary"] = summary
            return "Say goodbye now."

        plan.tools = [save_missing, end_call]
        return plan

    def cook(self):
        return next((k for k, p in self.hh["people"].items() if p.get("role") == "cook"), None)

    def plan_card(self, plan, days):
        cook = self.cook()
        need = [i for i in plan.get("ingredients", []) if not i.get("have_it")]
        lines = [f"{d['day']}: " + " · ".join(m["dish"] for m in d["meals"]) for d in plan.get("days", [])]
        avg = lambda k: round(sum(d.get(k, 0) for d in plan["days"]) / max(1, len(plan["days"])))
        choices = [{"id": "order", "label": f"Order {len(need)} missing ingredients"}] if need else []
        if cook and plan.get("days"):
            choices.append({"id": "brief", "label": f"Call {self.hh['people'][cook]['name']} with tomorrow's menu"})
        choices.append({"id": "keep", "label": "Just keep the plan"})
        return Card(self.name, "plan", f"Meal plan: next {days} day{'s' if days > 1 else ''}", lines,
                    question="What next?", choices=choices,
                    warnings=[f"Estimated per person per day: {avg('kcal')} kcal, protein {avg('protein_g')} g. "
                              "Estimates only, not dietary advice."] + ([plan["notes"]] if plan.get("notes") else []),
                    payload={"plan": plan, "need": need})

    def nutrition_card(self, plan, nut):
        from app.core import safety
        from app.experts.health.expert import wa_link
        text = pl.brief_text(self.hh, plan, nut)
        verdict = safety.check(text)
        who = self.hh.get("nutritionist") or {}
        warnings = {"blocked": ["The safety check held part of this brief. Review it before sharing."],
                    "unchecked": ["Safety check is off (set GUARDRAIL_ID)."]}.get(verdict.status, [])
        choices = [{"id": "share", "label": f"WhatsApp draft to {who.get('name', 'your nutritionist')}"}] if who.get("phone") else []
        return Card(self.name, "brief", f"Nutrition brief for {who.get('name', 'your nutritionist')}", verdict.text.split("\n"),
                    question="Share it?" if choices else "Add a nutritionist to household.yaml to share it.",
                    choices=choices + [{"id": "ok", "label": "Keep"}], warnings=warnings,
                    payload={"text": verdict.text, "safety": verdict.status,
                             "wa": wa_link(who["phone"], verdict.text) if who.get("phone") else None})

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
        if card["kind"] == "plan":
            if choice == "order":
                text = ", ".join(f"{i['quantity']} {i['item']}" for i in p["need"])
                self.store.add_card((await self.handle(text)).to_dict())
                return {"ok": True, "message": "Cart ready: see the new card."}
            if choice == "brief":
                tomorrow = (p["plan"].get("days") or [{}])[min(1, len(p["plan"].get("days", [])) - 1)]
                jid = self.menu_call(self.cook(), tomorrow)
                return {"ok": True, "message": "Calling the cook with the menu.", "jobs": [jid]}
            return {"ok": True, "message": "Plan kept."}
        if card["kind"] == "brief":
            return {"ok": True, "open": p.get("wa")} if choice == "share" else {"ok": True}
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

    async def track(self, o):
        """One gentle status check for a placed order (the tracker calls this about once a minute).
        Returns (status, eta, detail, delivered). Unknown response shapes fall back to the store's own text."""
        if o["store"] == "zepto":
            d, msg = await sw.call(self.zepto, "get_order_detail", {"orderId": o["id"]})
        else:
            d, msg = await sw.call(self.ops, "get_delivery_status", {"orderId": o["id"], "addressId": o["address_id"]})
        d = d if isinstance(d, dict) else {}
        status = (d.get("statusText") or d.get("orderStatus") or d.get("status") or for_people(msg).split("\n")[0])[:120]
        eta = d.get("etaText") or d.get("eta")
        by = d.get("deliveryBy")
        if not eta and isinstance(by, (int, float)) and by > 0:
            mins = round(((by / 1000 if by > 1e11 else by) - time.time()) / 60)
            eta = f"{mins} mins" if mins > 0 else "any minute"
        delivered = bool(d.get("isDelivered") or d.get("delivered")) or "delivered" in str(status).lower()
        return status, eta, d, delivered
