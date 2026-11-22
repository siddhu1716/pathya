import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ChevronDown, PhoneCall, PhoneIncoming } from "lucide-react";
import { Panel } from "@/components/kit";
import { Bubbles } from "@/components/LiveCall";
import { ago, api, CallRecord } from "@/lib/api";
import { cn } from "@/lib/utils";

const KIND: Record<string, string> = { home: "Family call", list: "Grocery list", menu: "Cook’s menu", book: "Clinic booking",
  checkin: "Check-in", doorstep: "Delivery call" };

function saved(c: CallRecord) {
  const s = c.saved ?? {};
  if (s.items?.length) return s.items.join(", ");
  if (s.booked) return `Booked ${String(s.booked.slot).replace("T", " ").slice(0, 16)} with ${s.booked.doctor}`;
  if (s.held) return `Held ${s.held.slot}`;
  if (s.checkin) return s.checkin.summary_en;
  return s.summary ?? "";
}

export function CallHistory({ onReview }: { onReview: () => void }) {
  const { data } = useQuery({ queryKey: ["calls"], queryFn: api.calls, refetchInterval: 4000 });
  const qc = useQueryClient();
  const recover = useMutation({ mutationFn: api.recoverCallList, onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["state"] });
    onReview();
  }, onError: (error: Error) => toast.error(error.message) });
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return null;
  if (!data.length) return <p className="text-muted-foreground text-center py-10">No calls yet.</p>;
  return (
    <Panel className="divide-y overflow-hidden">
      {data.map((c) => {
        const Icon = c.direction === "inbound" ? PhoneIncoming : PhoneCall;
        const isOpen = open === c.id;
        return (
          <div key={c.id}>
            <button className="w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-white/5" onClick={() => setOpen(isOpen ? null : c.id)}>
              <span className="w-9 h-9 rounded-full border flex items-center justify-center shrink-0"><Icon className="w-4 h-4" /></span>
              <span className="flex-1 min-w-0">
                <span className="block text-[15px]">{c.who} <span className="text-muted-foreground">· {KIND[c.kind ?? ""] ?? c.kind}</span></span>
                <span className="block text-[13px] text-muted-foreground truncate">{saved(c) || `${c.transcript.length} lines`}</span>
              </span>
              <span className="font-mono text-[11px] text-muted-foreground text-right shrink-0">
                {ago(c.ended)}<br />{c.seconds != null && `${c.seconds}s`}
              </span>
              <ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} />
            </button>
            {isOpen && (
              <div className="px-4 pb-4">
                {c.transcript.length ? <Bubbles lines={c.transcript} /> : <p className="text-[13px] text-muted-foreground">No transcript.</p>}
                {(c.kind === "home" || c.kind === "list" || c.kind === "menu") && (
                  <Button className="mt-3" variant="outline" disabled={recover.isPending} onClick={() => recover.mutate(c.id)}>
                    {recover.isPending && recover.variables === c.id ? "Checking the call…" : "Review grocery list on Home"}
                  </Button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </Panel>
  );
}
