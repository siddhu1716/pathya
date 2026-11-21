import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Phase 1 gate: one real Instamart order from your own code.
python scripts/first_order.py "2 packets milk, 1 curd, half kg tomatoes"   (answer 'no' the first time)"""
import asyncio, sys
from dotenv import load_dotenv

load_dotenv()                                  # before importing swiggy: it reads env vars at import time
sys.stdout.reconfigure(encoding="utf-8")       # Windows consoles can't print "₹" otherwise
from app.experts.kitchen.swiggy import (AGENT_TOOLS, CANCEL, bridge, build_cart, call, eta, finish_upi,
                     pick_address, place, rupees, summary)

YES = {"yes", "y", "confirm", "proceed"}


async def main(shopping):
    async with bridge("im-agent", AGENT_TOOLS) as agent_im, bridge("im-ops") as ops:
        addr = await pick_address(ops)
        print("Agent is building the cart...")
        note = await build_cart(agent_im, shopping, addr["id"])
        cart, _ = await call(ops, "get_cart")
        pay, _ = await call(ops, "get_payment_options")
        print(summary(cart, addr, pay), "\nAgent:", note)
        if input("Do you want to proceed with placing this order to this address? (yes/no) ").strip().lower() not in YES:
            return print("Not placed.")
        apps = ((pay.get("platforms") or {}).get("mobile") or {}).get("methods", [])
        cod = (pay.get("cod") or {}).get("available")
        upi_app = None
        if input(f"Pay with {'[c]ash on delivery or ' if cod else ''}[u]PI? ").strip().lower().startswith("u") or not cod:
            if not apps:
                return print("No UPI apps returned for this cart.")
            for n, a in enumerate(apps):
                print(f"  {n}: {a.get('displayName') or a['id']}")
            upi_app = apps[int(input("UPI app number: "))]["id"]
        order, msg = await place(ops, addr["id"], rupees(cart["billBreakdown"]["toPay"]["value"]), upi_app)
        ok = True
        if order.get("status") == "PENDING_PAYMENT":
            print("Pay here (scan on the laptop, or open on your phone):", order["bridgeUrl"])
            ok, msg = await finish_upi(ops, order)
        print(msg)                                            # Swiggy's own words, as-is
        if ok:
            for o in order.get("orders") or [order]:          # multi-store carts come back as several orders
                if o.get("orderId"):
                    print(o["orderId"], "-", await eta(ops, o["orderId"], addr["id"]))
        print(CANCEL)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "2 packets milk, 1 curd, half kg tomatoes"))
