import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, PhoneCall, PhoneIncoming } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Bubbles } from "@/components/LiveCall";
import { ago, api, CallRecord } from "@/lib/api";
import { cn } from "@/lib/utils";

const KIND: Record<string, string> = {
  list: "Grocery list",
  book: "Clinic booking",
  checkin: "Check-in",
  doorstep: "Delivery call",
};

function savedSummary(c: CallRecord) {
  const s = c.saved ?? {};
  if (s.items?.length) return `List: ${s.items.join(", ")}`;
  if (s.booked) return `Booked ${s.booked.slot?.replace("T", " ").slice(0, 16)} with ${s.booked.doctor}`;
  if (s.held) return `Held slot ${s.held.slot}`;
  if (s.checkin) return s.checkin.summary_en;
  return s.summary ?? "";
}

export function CallHistory() {
  const { data } = useQuery({ queryKey: ["calls"], queryFn: api.calls, refetchInterval: 4000 });
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return null;
  if (!data.length) return <p className="text-muted-foreground text-center py-10">No calls yet.</p>;
  return (
    <div className="space-y-3">
      {data.map((c) => {
        const Icon = c.direction === "inbound" ? PhoneIncoming : PhoneCall;
        const isOpen = open === c.id;
        return (
          <Card key={c.id}>
            <CardContent className="p-4">
              <button className="w-full flex items-start gap-3 text-left" onClick={() => setOpen(isOpen ? null : c.id)}>
                <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold">{c.who}</p>
                    <Badge variant="secondary">{KIND[c.kind ?? ""] ?? c.kind}</Badge>
                    <Badge variant="outline">{c.source}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground truncate">{savedSummary(c) || `${c.transcript.length} lines`}</p>
                  <p className="text-xs text-muted-foreground">{ago(c.ended)}{c.seconds != null && ` · ${c.seconds}s`}</p>
                </div>
                <ChevronDown className={cn("w-4 h-4 mt-2 transition-transform", isOpen && "rotate-180")} />
              </button>
              {isOpen && (
                <div className="mt-3 pt-3 border-t">
                  {c.transcript.length ? <Bubbles lines={c.transcript} /> : <p className="text-sm text-muted-foreground">No transcript.</p>}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
