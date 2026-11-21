"""Order tracker: about once a minute, one status check per active order, written to the orders table and,
when the status changes, to the timeline. Gentle on purpose: Swiggy and Zepto rate-limit (HTTP 429), so a
rate-limit error pauses all tracking for 5 minutes. Orders older than 4 hours are no longer tracked."""
import asyncio
import time

BACKOFF_S = 300
MAX_AGE_S = 4 * 3600


def order_ids(order):
    """Multi-store carts come back as several orders."""
    out = []
    for o in (order or {}).get("orders") or [order or {}]:
        oid = o.get("orderId") or o.get("order_id") or o.get("id")
        if oid:
            out.append(str(oid))
    return out


def record(store, aid, card, result):
    """After a successful tap on an order card: one orders row per store order (dry runs are marked)."""
    p = card.get("payload") or {}
    shop = p.get("store", "swiggy")
    common = dict(card=aid, ref=p.get("ref"), items=card.get("lines", []), total=card.get("total"),
                  address=card.get("address"), address_id=p.get("address_id"))
    if result.get("dry_run"):
        store.add_order(f"dry-{aid}", "dry run", status="DRY RUN: not placed", **common)
        _remember(store, card, "dry run")
        return [f"dry-{aid}"]
    ids = order_ids(result.get("order"))
    eta = result.get("eta") or {}
    for oid in ids:
        store.add_order(oid, shop, status="placed", eta=eta.get(oid), **common)
    _remember(store, card, shop)
    return ids


def _remember(store, card, shop):
    """Household memory: what this home buys (planner.remember_order)."""
    from app.experts.kitchen.planner import remember_order
    remember_order(store, card.get("lines", []), shop)


async def tick(store, kitchen, now=None, state=None):
    state = state if state is not None else {}
    now = time.time() if now is None else now
    if now < state.get("paused_until", 0):
        return []
    changed = []
    for o in store.orders(active=True):
        if now - o["placed"] > MAX_AGE_S:
            continue
        try:
            status, eta, detail, delivered = await kitchen.track(o)
        except Exception as err:
            if "429" in str(err) or "too many" in str(err).lower():
                state["paused_until"] = now + BACKOFF_S
                store.log("orders", o["id"], "tracking paused for 5 min (store rate limit)")
                return changed
            continue
        if store.update_order(o["id"], status=status, eta=eta, detail=detail, delivered=delivered):
            changed.append(o["id"])
            store.log("orders", o["id"], f"{o['store']}: {status}" + (f" (ETA {eta})" if eta and not delivered else ""))
    return changed


async def run_forever(store, kitchen, every=60):
    state = {}
    while True:
        try:
            await tick(store, kitchen, state=state)
        except Exception as err:                         # tracking never takes the app down
            store.log("orders", "tracker", f"tracker error: {err}")
        await asyncio.sleep(every)
