import { MapPin } from "lucide-react";
import { Dot, Panel, Pill } from "@/components/kit";
import { clock, Order, span } from "@/lib/api";
import { cn } from "@/lib/utils";

const STORE: Record<string, string> = { swiggy: "Instamart", zepto: "Zepto", "dry run": "Dry run" };

function stage(o: Order) {
  if (o.delivered) return 3;
  const s = (o.status ?? "").toLowerCase();
  if (/(out for|on the way|picked|rider|partner|arriv|transit|dispatch)/.test(s)) return 2;
  if (/(pack|prepar|confirm|accept)/.test(s)) return 1;
  return 0;
}

const STEPS = ["Placed", "Packing", "On the way", "Delivered"];

export function OrderTracker({ order, compact = false }: { order: Order; compact?: boolean }) {
  const dry = order.store === "dry run";
  const at = stage(order);
  const j = order.journey ?? { placed: order.placed };
  return (
    <Panel className="p-4 space-y-4 fade-in">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <span className="label flex items-center gap-2">
            <Dot tone={dry ? "muted" : at === 3 ? "ok" : "warn"} pulse={!dry && at < 3} /> {STORE[order.store] ?? order.store}
          </span>
          <p className="text-lg font-medium leading-tight">
            {dry ? "Not placed (dry run)" : at === 3 ? "Delivered" : order.status || "Placed"}
          </p>
          {order.eta && !dry && at < 3 && <p className="text-[13px] text-muted-foreground">Arriving in {order.eta}</p>}
        </div>
        <div className="text-right shrink-0">
          {order.total && <p className="text-lg font-medium tabular-nums">{order.total}</p>}
          <p className="font-mono text-[11px] text-muted-foreground">{clock(order.placed)}</p>
        </div>
      </div>

      {!dry && (
        <div>
          <div className="flex gap-1">
            {STEPS.map((s, i) => (
              <div key={s} className={cn("h-1 flex-1 rounded-full", i <= at ? "bg-success" : "bg-white/10")} />
            ))}
          </div>
          <div className="flex justify-between mt-2">
            {STEPS.map((s, i) => (
              <span key={s} className={cn("font-mono text-[10px] uppercase tracking-wider", i <= at ? "text-foreground" : "text-muted-foreground")}>{s}</span>
            ))}
          </div>
        </div>
      )}

      {!compact && (
        <>
          <ul className="text-[14px] text-foreground/85 space-y-1 border-t pt-3">
            {order.items.map((it, i) => <li key={i}>{it}</li>)}
          </ul>
          {order.address && (
            <p className="text-[13px] text-muted-foreground flex gap-1.5"><MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {order.address}</p>
          )}
          <Journey j={j} />
        </>
      )}
    </Panel>
  );
}

function Journey({ j }: { j: Order["journey"] }) {
  const steps = [
    { label: "Call", at: j.call_started },
    { label: "Cart", at: j.card_ready },
    { label: "Tap", at: j.tapped },
    { label: "Delivered", at: j.delivered ?? undefined },
  ].filter((s) => s.at);
  if (steps.length < 2) return null;
  return (
    <div className="border-t pt-3 space-y-2">
      <p className="label">Journey</p>
      <div className="flex flex-wrap gap-2">
        {steps.map((s, i) => (
          <Pill key={s.label}>
            {s.label} {clock(s.at!).slice(0, 5)}{i > 0 && ` · +${span(steps[i - 1].at, s.at)}`}
          </Pill>
        ))}
      </div>
    </div>
  );
}
