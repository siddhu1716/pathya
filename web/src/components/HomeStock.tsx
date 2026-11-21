import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUp, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, Pill } from "@/components/kit";
import { api, AppState, ShelfItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const useKitchen = () => useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen, refetchInterval: 5000 });

const left = (i: ShelfItem) =>
  i.days_left < 1 ? "use today" : `~${Math.round(i.days_left)} day${Math.round(i.days_left) === 1 ? "" : "s"} left`;

/** What is at home: delivered orders on the shelf, running-low first, one tap to rebuild a cart for the low ones. */
export function AtHome({ state, compact = false }: { state: AppState; compact?: boolean }) {
  const qc = useQueryClient();
  const { data } = useKitchen();
  const shelf = data?.pantry ?? [];
  const low = shelf.filter((i) => i.low);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["kitchen"] }); qc.invalidateQueries({ queryKey: ["state"] }); };
  const reorder = useMutation({
    mutationFn: () => api.reorder(low.map((i) => `${i.qty || 1} x ${i.name}`)),
    onSuccess: () => { toast.success("Cart ready: tap to approve"); refresh(); },
    onError: (e: Error) => toast.error(e.message),
  });
  const used = useMutation({ mutationFn: api.usedUp, onSuccess: refresh, onError: (e: Error) => toast.error(e.message) });

  if (!shelf.length) {
    return compact ? null : (
      <Panel className="px-4 py-5 text-[14px] text-muted-foreground">
        Empty. Delivered orders land here, and QuickPick tells you when something is running low.
      </Panel>
    );
  }
  const rows = compact ? low.slice(0, 4) : shelf;
  return (
    <div className="space-y-3">
      <Panel className="divide-y overflow-hidden">
        {compact && (
          <div className="px-4 py-3 flex items-center justify-between text-[14px]">
            <span>{shelf.length} item{shelf.length === 1 ? "" : "s"} at home</span>
            {low.length > 0 ? <Pill tone="warn">{low.length} running low</Pill> : <Pill tone="ok">All good</Pill>}
          </div>
        )}
        {rows.map((i) => (
          <div key={i.key} className="flex items-center gap-3 px-4 py-3">
            <span className="flex-1 min-w-0">
              <span className="block text-[15px] truncate">{i.name}</span>
              <span className={cn("block font-mono text-[11px]", i.low ? "text-warning" : "text-muted-foreground")}>
                x{i.qty} · {left(i)}{i.store === "dry run" ? " · dry run" : ""}
              </span>
            </span>
            <div className="w-12 h-1 rounded-full bg-white/10 overflow-hidden shrink-0">
              <div className={cn("h-full", i.low ? "bg-warning" : "bg-success")} style={{ width: `${Math.max(6, i.left * 100)}%` }} />
            </div>
            {!compact && (
              <button aria-label={`${i.name} is finished`} disabled={used.isPending} onClick={() => used.mutate(i.key)}
                      className="w-8 h-8 -mr-2 flex items-center justify-center text-muted-foreground active:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </Panel>
      {low.length > 0 && (
        <Button className="w-full h-12" disabled={reorder.isPending || !state.swiggy} onClick={() => reorder.mutate()}>
          {reorder.isPending ? <><Loader2 className="animate-spin" /> Building the cart</> : `Reorder ${low.length} running low`}
        </Button>
      )}
    </div>
  );
}

/** Today's meals (said on a call or typed) and estimated energy/protein against the daily reference. */
export function Today() {
  const qc = useQueryClient();
  const { data } = useKitchen();
  const [text, setText] = useState("");
  const log = useMutation({
    mutationFn: () => api.logMeal(text),
    onSuccess: (m) => { setText(""); toast.success(`About ${m.kcal} kcal`); qc.invalidateQueries({ queryKey: ["kitchen"] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  const t = data?.today;
  const bars: [string, number, number, string][] = t ? [
    ["Energy", t.total.kcal, t.targets.kcal, "kcal"],
    ["Protein", t.total.protein_g, t.targets.protein_g, "g"],
    ["Fibre", t.total.fibre_g, t.targets.fibre_g, "g"],
  ] : [];
  return (
    <Panel className="p-4 space-y-4">
      {bars.map(([label, v, goal, unit]) => (
        <div key={label} className="space-y-1">
          <div className="flex justify-between text-[13px]">
            <span>{label}</span>
            <span className="font-mono tabular-nums text-muted-foreground">{Math.round(v)} / {goal} {unit}</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div className="h-full rounded-full bg-foreground/80" style={{ width: `${Math.min(100, Math.round((v / goal) * 100))}%` }} />
          </div>
        </div>
      ))}
      {t && t.meals.length > 0 && (
        <ul className="space-y-1.5 border-t pt-3">
          {t.meals.map((m) => (
            <li key={m.ts} className="flex justify-between gap-3 text-[14px]">
              <span className="min-w-0 truncate"><span className="text-muted-foreground capitalize">{m.meal || "meal"}: </span>{m.text}</span>
              <span className="font-mono text-[12px] text-muted-foreground shrink-0">{m.kcal} kcal</span>
            </li>
          ))}
        </ul>
      )}
      <form className="flex items-center gap-2 rounded-full border pl-4 pr-1.5 py-1.5 focus-within:border-white/30"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) log.mutate(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={log.isPending}
               placeholder="What did you eat? (2 idli, sambar)" className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground min-w-0" />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0" disabled={log.isPending || !text.trim()} aria-label="Log meal">
          {log.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
        </Button>
      </form>
      <p className="text-[12px] text-muted-foreground">Estimates against {t?.targets.source ?? "a general reference"}. Not dietary advice.</p>
    </Panel>
  );
}
