import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, History, Home, Inbox, Loader2, Package, Phone, PhoneCall, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ApprovalCard } from "@/components/ApprovalCard";
import { CallHistory } from "@/components/CallHistory";
import { AskBox, ExpertActions } from "@/components/ExpertActions";
import { JobsPanel } from "@/components/JobsPanel";
import { LiveCallBanner } from "@/components/LiveCall";
import { OrderTracker } from "@/components/OrderTracker";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "home" | "orders" | "calls" | "timeline";
const TABS: { id: Tab; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "orders", label: "Orders", icon: Package },
  { id: "calls", label: "Calls", icon: PhoneCall },
  { id: "timeline", label: "Timeline", icon: History },
];

const Chip = ({ ok, children }: { ok: boolean; children: React.ReactNode }) => (
  <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border",
    ok ? "border-success/30 bg-success/10 text-success" : "border-muted-foreground/20 text-muted-foreground")}>
    <span className={cn("w-1.5 h-1.5 rounded-full", ok ? "bg-success" : "bg-muted-foreground/40")} />
    {children}
  </span>
);

const Index = () => {
  const [tab, setTab] = useState<Tab>("home");
  const { data: s, error } = useQuery({ queryKey: ["state"], queryFn: api.state, refetchInterval: 2000 });

  if (!s) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground gap-2">
        {error ? `Can't reach QuickPick: ${(error as Error).message}` : <><Loader2 className="animate-spin" /> Loading…</>}
      </div>
    );
  }

  const active = s.orders.filter((o) => !o.delivered && o.store !== "dry run");
  const urgent = s.cards.some((c) => c.card.kind === "alert");

  return (
    <div className="min-h-screen bg-background pb-20 lg:pb-6">
      {s.dry_run && (
        <div className="bg-destructive text-destructive-foreground text-center text-xs font-semibold py-1">
          DRY RUN: no real orders are placed
        </div>
      )}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-hero flex items-center justify-center shadow">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold bg-gradient-hero bg-clip-text text-transparent leading-tight">QuickPick Experts</h1>
              <p className="text-[11px] text-muted-foreground">Experts prepare. {s.user} commits.</p>
            </div>
          </div>
          <div className="hidden sm:flex flex-wrap justify-end gap-1">
            <Chip ok={s.swiggy}>Swiggy</Chip>
            <Chip ok={s.zepto}>Zepto</Chip>
            <Chip ok={s.phone}>{s.phone ? `AI line ${s.phone_number}` : "Browser calls"}</Chip>
          </div>
        </div>
        <nav className="hidden lg:block container mx-auto px-4">
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                      className={cn("px-4 py-2 text-sm font-medium border-b-2 transition-smooth flex items-center gap-2",
                        tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>
                <t.icon className="w-4 h-4" /> {t.label}
                {t.id === "orders" && active.length > 0 && <Badge className="h-5 px-1.5">{active.length}</Badge>}
              </button>
            ))}
          </div>
        </nav>
      </header>

      <main className="container mx-auto px-4 py-5">
        {s.live.length > 0 && (
          <div className="grid gap-3 mb-5 md:grid-cols-2">
            {s.live.map((c) => <LiveCallBanner key={c.id} call={c} />)}
          </div>
        )}

        {tab === "home" && (
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="space-y-6 lg:col-span-2">
              <AskBox swiggy={s.swiggy} />
              <div className="space-y-3">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  {urgent ? <AlertOctagon className="w-5 h-5 text-destructive" /> : <Inbox className="w-5 h-5" />}
                  Waiting for you ({s.cards.length})
                </h2>
                {s.cards.length === 0 && (
                  <p className="rounded-xl border-2 border-dashed border-muted-foreground/20 p-6 text-center text-muted-foreground text-sm">
                    Nothing to approve. Ask QuickPick, or start a call.
                  </p>
                )}
                {s.cards.map((row) => <ApprovalCard key={row.id} row={row} />)}
              </div>
              {active.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-base font-semibold flex items-center gap-2"><Package className="w-5 h-5" /> On the way</h2>
                  {active.map((o) => <OrderTracker key={o.id} order={o} />)}
                </div>
              )}
              {s.recent.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-base font-semibold">Recently handled</h2>
                  {s.recent.slice(0, 4).map((row) => <ApprovalCard key={row.id} row={row} />)}
                </div>
              )}
            </section>
            <aside className="space-y-6">
              <JobsPanel jobs={s.jobs} ringing={s.ringing} people={s.people} />
              <ExpertActions state={s} />
              {s.phone && (
                <div className="rounded-xl border bg-card p-4 text-sm">
                  <p className="font-medium flex items-center gap-2"><Phone className="w-4 h-4" /> QuickPick answers {s.phone_number}</p>
                  <p className="text-muted-foreground mt-1">Family members get the Kitchen Expert. Anyone else, like a delivery partner, gets the Doorstep Expert.</p>
                </div>
              )}
            </aside>
          </div>
        )}

        {tab === "orders" && (
          <div className="max-w-2xl mx-auto space-y-4">
            {s.orders.length === 0 && <p className="text-muted-foreground text-center py-10">No orders yet.</p>}
            {s.orders.map((o) => <OrderTracker key={o.id} order={o} />)}
          </div>
        )}

        {tab === "calls" && <div className="max-w-2xl mx-auto"><CallHistory /></div>}

        {tab === "timeline" && <div className="max-w-2xl mx-auto"><Timeline events={s.timeline} /></div>}
      </main>

      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t bg-card/95 backdrop-blur">
        <div className="grid grid-cols-4">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
                    className={cn("py-2 flex flex-col items-center gap-0.5 text-[11px] relative",
                      tab === t.id ? "text-primary" : "text-muted-foreground")}>
              <t.icon className="w-5 h-5" />
              {t.label}
              {t.id === "home" && s.cards.length > 0 && (
                <span className="absolute top-1 right-[30%] min-w-4 h-4 px-1 rounded-full bg-destructive text-white text-[10px] leading-4">{s.cards.length}</span>
              )}
              {t.id === "orders" && active.length > 0 && (
                <span className="absolute top-1 right-[30%] min-w-4 h-4 px-1 rounded-full bg-primary text-white text-[10px] leading-4">{active.length}</span>
              )}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
};

export default Index;
