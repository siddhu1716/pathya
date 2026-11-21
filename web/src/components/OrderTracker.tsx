import { Bike, CheckCircle2, Clock, MapPin, Package, PhoneCall, ShoppingBag, Timer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { clock, Order, span } from "@/lib/api";
import { cn } from "@/lib/utils";

const STORE: Record<string, { label: string; className: string }> = {
  swiggy: { label: "Swiggy Instamart", className: "bg-orange-500 text-white" },
  zepto: { label: "Zepto", className: "bg-purple-600 text-white" },
  "dry run": { label: "Dry run", className: "bg-muted text-muted-foreground" },
};

function stage(o: Order) {
  if (o.delivered) return 3;
  const s = (o.status ?? "").toLowerCase();
  if (/(out for|on the way|picked|rider|partner|arriv|transit|dispatch)/.test(s)) return 2;
  if (/(pack|prepar|confirm|accept)/.test(s)) return 1;
  return o.store === "dry run" ? -1 : 0;
}

const STEPS = [
  { label: "Placed", icon: ShoppingBag },
  { label: "Packing", icon: Package },
  { label: "On the way", icon: Bike },
  { label: "Delivered", icon: CheckCircle2 },
];

export function OrderTracker({ order, compact = false }: { order: Order; compact?: boolean }) {
  const st = STORE[order.store] ?? { label: order.store, className: "bg-secondary" };
  const at = stage(order);
  const j = order.journey ?? { placed: order.placed };
  return (
    <Card className={cn("overflow-hidden fade-in", at === 3 && "border-success/40")}>
      <CardContent className="p-4 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <Badge className={st.className}>{st.label}</Badge>
            <p className="mt-2 text-lg font-semibold leading-tight">
              {at === 3 ? "Delivered" : order.store === "dry run" ? "Not placed (dry run)" : order.status || "Placed"}
            </p>
            {order.eta && at < 3 && order.store !== "dry run" && (
              <p className="text-sm text-muted-foreground flex items-center gap-1"><Timer className="w-4 h-4" /> Arriving in {order.eta}</p>
            )}
          </div>
          <div className="text-right">
            {order.total && <p className="text-lg font-bold">{order.total}</p>}
            <p className="text-xs text-muted-foreground">{clock(order.placed)}</p>
          </div>
        </div>

        {order.store !== "dry run" && (
          <div className="grid grid-cols-4 gap-1">
            {STEPS.map((s, i) => (
              <div key={s.label} className="flex flex-col items-center text-center gap-1">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center transition-smooth",
                  i <= at ? "bg-success text-white" : "bg-muted text-muted-foreground",
                  i === at && at < 3 && "voice-pulse")}>
                  <s.icon className="w-4 h-4" />
                </div>
                <span className={cn("text-[11px]", i <= at ? "font-medium" : "text-muted-foreground")}>{s.label}</span>
              </div>
            ))}
          </div>
        )}

        {!compact && (
          <>
            <ul className="text-sm space-y-0.5">
              {order.items.map((it, i) => <li key={i}>• {it}</li>)}
            </ul>
            {order.address && (
              <p className="text-sm text-muted-foreground flex gap-1"><MapPin className="w-4 h-4 shrink-0 mt-0.5" /> {order.address}</p>
            )}
            <Journey j={j} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Journey({ j }: { j: Order["journey"] }) {
  const steps = [
    { label: "Call", at: j.call_started, icon: PhoneCall },
    { label: "Cart ready", at: j.card_ready, icon: ShoppingBag },
    { label: "Tapped", at: j.tapped, icon: CheckCircle2 },
    { label: "Delivered", at: j.delivered ?? undefined, icon: Bike },
  ].filter((s) => s.at);
  if (steps.length < 2) return null;
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2">
      <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1"><Clock className="w-3 h-3" /> Journey</p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {steps.map((s, i) => (
          <span key={s.label} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted-foreground">→ {span(steps[i - 1].at, s.at)} →</span>}
            <s.icon className="w-3 h-3" /> {s.label} <span className="text-muted-foreground">{clock(s.at!)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
