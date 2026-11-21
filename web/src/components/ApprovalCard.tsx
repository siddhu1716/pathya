import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CalendarPlus, CheckCircle2, ExternalLink, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, CardRow } from "@/lib/api";
import { cn } from "@/lib/utils";

const KIND_LABEL: Record<string, string> = {
  order: "Kitchen · order",
  booking: "Health · booking",
  hold: "Health · held slot",
  brief: "Health · doctor brief",
  meds: "Health · prescription",
  alert: "Urgent",
  info: "Info",
  followup: "Health · follow-up",
};

const SAFETY: Record<string, { label: string; className: string }> = {
  passed: { label: "Safety: passed", className: "bg-success/15 text-success border-success/30" },
  blocked: { label: "Safety: held", className: "bg-warning/20 text-warning-foreground border-warning/40" },
  unchecked: { label: "Safety: off", className: "bg-muted text-muted-foreground" },
};

export function ApprovalCard({ row }: { row: CardRow }) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const c = row.card;
  const urgent = c.kind === "alert";
  const waiting = row.status === "waiting";

  const tap = useMutation({
    mutationFn: (choice: string) => api.tap(row.id, choice),
    onSuccess: (r) => {
      if (r.result?.open) window.open(r.result.open, "_blank", "noopener");
      if (r.result?.pay_url) window.open(r.result.pay_url, "_blank", "noopener");
      qc.invalidateQueries({ queryKey: ["state"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const reject = useMutation({
    mutationFn: () => api.reject(row.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["state"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const busy = tap.isPending || reject.isPending;

  return (
    <Card
      className={cn(
        "fade-in transition-smooth",
        urgent && "border-2 border-destructive bg-destructive/5",
        !waiting && "opacity-90",
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className={cn("text-lg leading-snug", urgent && "text-destructive")}>
            {urgent && <AlertTriangle className="inline w-5 h-5 mr-1 -mt-1" />}
            {c.title}
          </CardTitle>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <Badge variant={urgent ? "destructive" : "secondary"}>{KIND_LABEL[c.kind] ?? c.kind}</Badge>
            {c.kind === "brief" && c.payload?.safety && (
              <Badge variant="outline" className={SAFETY[c.payload.safety]?.className}>
                <ShieldCheck className="w-3 h-3 mr-1" />
                {SAFETY[c.payload.safety]?.label ?? c.payload.safety}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {c.lines.length > 0 && (
          <ul className="space-y-1">
            {c.lines.filter(Boolean).map((l, i) => (
              <li key={i} className="whitespace-pre-line">{l}</li>
            ))}
          </ul>
        )}

        {c.total && (
          <p className="text-base font-semibold">To pay: {c.total}</p>
        )}
        {c.address && (
          <p className="text-muted-foreground">Your order will be delivered to: {c.address}</p>
        )}

        {c.warnings.length > 0 && (
          <div className="space-y-1">
            {c.warnings.map((w, i) => (
              <p key={i} className="rounded-md border border-warning/40 bg-warning/15 px-3 py-2 whitespace-pre-line">
                {w}
              </p>
            ))}
          </div>
        )}

        {waiting && (
          <>
            {c.question && <p className="font-medium">{c.question}</p>}
            <div className="flex flex-wrap gap-2">
              {c.choices.map((ch) => (
                <Button
                  key={ch.id}
                  size="sm"
                  variant={urgent ? "destructive" : ch.id === c.choices[0]?.id ? "default" : "outline"}
                  disabled={busy}
                  onClick={() => {
                    setPicked(ch.id);
                    tap.mutate(ch.id);
                  }}
                >
                  {tap.isPending && picked === ch.id && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                  {ch.label}
                </Button>
              ))}
              {!urgent && (
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => reject.mutate()}>
                  Not now
                </Button>
              )}
            </div>
            {c.choices.length === 0 && (
              <p className="text-muted-foreground">Nothing to approve on this card.</p>
            )}
          </>
        )}

        {!waiting && <Outcome row={row} />}
      </CardContent>
    </Card>
  );
}

function Outcome({ row }: { row: CardRow }) {
  const r = row.result;
  if (row.status === "rejected") return <p className="text-muted-foreground">Not now. Nothing was done.</p>;
  if (row.status === "running") {
    return (
      <div className="space-y-2">
        <p className="flex items-center gap-2 font-medium">
          <Loader2 className="w-4 h-4 animate-spin" /> {r?.pay_url ? "Waiting for your UPI payment…" : "Working…"}
        </p>
        {r?.pay_url && (
          <a className="inline-flex items-center gap-1 text-primary underline" href={r.pay_url} target="_blank" rel="noreferrer">
            Open the payment page <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    );
  }
  const failed = row.status === "failed" || r?.ok === false;
  return (
    <div className={cn("space-y-2 rounded-md border px-3 py-2", failed ? "border-destructive/40 bg-destructive/5" : "border-success/30 bg-success/5")}>
      <p className="flex items-center gap-2 font-medium">
        {failed ? <XCircle className="w-4 h-4 text-destructive" /> : <CheckCircle2 className="w-4 h-4 text-success" />}
        {failed ? "Not done" : `Done${row.choice ? ` (${row.choice})` : ""}`}
      </p>
      {r?.message && <p className="whitespace-pre-line">{r.message}</p>}
      {r?.error && <p className="whitespace-pre-line text-destructive">{r.error}</p>}
      {r?.eta &&
        Object.entries(r.eta).map(([id, eta]) => (
          <p key={id}>Order {id}: arriving in {eta}</p>
        ))}
      {r?.jobs && r.jobs.length > 0 && <p>{r.jobs.length} call(s) scheduled. See Upcoming.</p>}
      {row.card.payload?.ics && (
        <a className="inline-flex items-center gap-1 text-primary underline" href={api.icsUrl(row.id)}>
          <CalendarPlus className="w-4 h-4" /> Add to calendar
        </a>
      )}
      {r?.cancel && <p className="text-muted-foreground">{r.cancel}</p>}
    </div>
  );
}
