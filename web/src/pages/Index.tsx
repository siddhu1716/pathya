import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, Inbox, Loader2, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ApprovalCard } from "@/components/ApprovalCard";
import { AskBox, ExpertActions } from "@/components/ExpertActions";
import { JobsPanel } from "@/components/JobsPanel";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";

const Index = () => {
  const { data: s, error } = useQuery({ queryKey: ["state"], queryFn: api.state, refetchInterval: 2000 });

  if (!s) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground gap-2">
        {error ? `Can't reach QuickPick: ${(error as Error).message}` : <><Loader2 className="animate-spin" /> Loading…</>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {s.dry_run && (
        <div className="bg-destructive text-destructive-foreground text-center text-sm font-semibold py-1">
          DRY RUN: no real orders are placed (set DRY_RUN=0 in .env for a real order)
        </div>
      )}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-hero flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-hero bg-clip-text text-transparent leading-tight">QuickPick Experts</h1>
              <p className="text-xs text-muted-foreground">Experts prepare. {s.user} commits.</p>
            </div>
          </div>
          <Badge variant={s.swiggy ? "secondary" : "destructive"}>
            {s.swiggy ? "Swiggy connected" : "Swiggy offline"}
          </Badge>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 grid gap-6 lg:grid-cols-3">
        <section className="space-y-6 lg:col-span-2">
          <AskBox swiggy={s.swiggy} />

          <div className="space-y-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              {s.cards.some((c) => c.card.kind === "alert") ? <AlertOctagon className="w-5 h-5 text-destructive" /> : <Inbox className="w-5 h-5" />}
              Waiting for you ({s.cards.length})
            </h2>
            {s.cards.length === 0 && (
              <p className="rounded-lg border-2 border-dashed border-muted-foreground/25 p-6 text-center text-muted-foreground">
                Nothing to approve. Ask QuickPick, or start a call.
              </p>
            )}
            {s.cards.map((row) => <ApprovalCard key={row.id} row={row} />)}
          </div>

          {s.recent.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">Recently handled</h2>
              {s.recent.map((row) => <ApprovalCard key={row.id} row={row} />)}
            </div>
          )}
        </section>

        <aside className="space-y-6">
          <JobsPanel jobs={s.jobs} ringing={s.ringing} people={s.people} />
          <ExpertActions state={s} />
          <Timeline events={s.timeline} />
        </aside>
      </main>
    </div>
  );
};

export default Index;
