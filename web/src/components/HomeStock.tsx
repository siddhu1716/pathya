import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, X } from "lucide-react";
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
        <Button className="w-full h-12" disabled={reorder.isPending || !(state.swiggy || state.zepto)} onClick={() => reorder.mutate()}>
          {reorder.isPending ? <><Loader2 className="animate-spin" /> Building the cart</> : `Reorder ${low.length} running low`}
        </Button>
      )}
    </div>
  );
}
