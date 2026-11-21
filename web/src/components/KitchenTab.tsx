import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Panel, Pill, Section } from "@/components/kit";
import { api, AppState, Macros, Nutrition } from "@/lib/api";
import { cn } from "@/lib/utils";

function Usuals({ state }: { state: AppState }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen, refetchInterval: 10000 });
  const [picked, setPicked] = useState<Record<string, boolean>>({});
  const reorder = useMutation({
    mutationFn: (items: string[]) => api.reorder(items),
    onSuccess: () => { toast.success("Cart ready on Home"); setPicked({}); qc.invalidateQueries({ queryKey: ["state"] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  const usuals = data?.usuals ?? [];
  const chosen = usuals.filter((u) => picked[u.name]);
  if (!usuals.length) {
    return <Panel className="px-4 py-5 text-[14px] text-muted-foreground">Nothing yet. Every order teaches QuickPick what this home buys.</Panel>;
  }
  return (
    <div className="space-y-3">
      <Panel className="divide-y overflow-hidden">
        {usuals.map((u) => {
          const on = !!picked[u.name];
          return (
            <button key={u.name} onClick={() => setPicked({ ...picked, [u.name]: !on })}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left active:bg-white/5">
              <span className={cn("w-5 h-5 rounded-md border flex items-center justify-center shrink-0", on && "bg-primary border-primary")}>
                {on && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-[15px] truncate">{u.name}</span>
                <span className="block font-mono text-[11px] text-muted-foreground">
                  usually x{u.typical} · bought {u.count}x · {u.days_ago < 1 ? "today" : `${Math.round(u.days_ago)}d ago`}
                </span>
              </span>
            </button>
          );
        })}
      </Panel>
      <Button className="w-full h-12" disabled={!chosen.length || reorder.isPending || !state.swiggy}
              onClick={() => reorder.mutate(chosen.map((u) => `${u.typical} x ${u.name}`))}>
        {reorder.isPending && <Loader2 className="animate-spin" />}
        {reorder.isPending ? "Building the cart" : chosen.length ? `Reorder ${chosen.length} item${chosen.length > 1 ? "s" : ""}` : "Pick items to reorder"}
      </Button>
    </div>
  );
}

function Plan({ state }: { state: AppState }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen });
  const [days, setDays] = useState(3);
  const [notes, setNotes] = useState("");
  const make = useMutation({
    mutationFn: () => api.mealplan(days, notes),
    onSuccess: () => { toast.success("Plan ready"); qc.invalidateQueries({ queryKey: ["kitchen"] }); qc.invalidateQueries({ queryKey: ["state"] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  const plan = data?.plan;
  const card = state.cards.find((c) => c.card.kind === "plan");
  return (
    <div className="space-y-3">
      <Panel className="p-4 space-y-3">
        <p className="text-[13px] text-muted-foreground">
          {data ? `${data.prefs.people} people · ${data.prefs.diet} · ${data.prefs.cuisine}` : " "}. Uses what you already bought and
          the doctor's written advice to choose dishes.
        </p>
        <div className="flex gap-2">
          {[1, 3, 7].map((d) => (
            <button key={d} onClick={() => setDays(d)}
                    className={cn("flex-1 h-10 rounded-full border text-[14px]", days === d ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
              {d} day{d > 1 ? "s" : ""}
            </button>
          ))}
        </div>
        <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything to keep in mind? (Amma likes pesarattu)"
               className="w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30" />
        <Button className="w-full h-12" disabled={make.isPending} onClick={() => make.mutate()}>
          {make.isPending ? <><Loader2 className="animate-spin" /> Planning (about 15 s)</> : plan ? <><RefreshCw /> New plan</> : "Plan meals"}
        </Button>
      </Panel>
      {card && <ApprovalCard row={card} />}
      {plan && !card && (
        <Panel className="divide-y">
          {plan.days.map((d) => (
            <div key={d.day} className="px-4 py-3 space-y-1">
              <div className="flex justify-between"><span className="label">{d.day}</span><span className="font-mono text-[11px] text-muted-foreground">{d.kcal} kcal · P {d.protein_g} g</span></div>
              {d.meals.map((m) => <p key={m.slot} className="text-[14px]"><span className="text-muted-foreground capitalize">{m.slot}: </span>{m.dish}</p>)}
            </div>
          ))}
        </Panel>
      )}
    </div>
  );
}

const ROWS: [keyof Macros, string, string][] = [
  ["kcal", "Energy", "kcal"], ["protein_g", "Protein", "g"], ["carbs_g", "Carbs", "g"], ["fat_g", "Fat", "g"], ["fibre_g", "Fibre", "g"],
];

function Bars({ n }: { n: Nutrition }) {
  return (
    <div className="space-y-3">
      {ROWS.map(([k, label, unit]) => {
        const v = n.per_person_day[k], t = n.targets[k];
        const pct = t ? Math.min(100, Math.round((v / t) * 100)) : 0;
        return (
          <div key={k} className="space-y-1">
            <div className="flex justify-between text-[13px]">
              <span>{label}</span>
              <span className="font-mono tabular-nums text-muted-foreground">{Math.round(v)} / {t} {unit}</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div className={cn("h-full rounded-full", pct >= 80 ? "bg-success" : "bg-warning")} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NutritionPanel({ state }: { state: AppState }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen });
  const run = useMutation({
    mutationFn: api.nutrition,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kitchen"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const share = useMutation({
    mutationFn: api.shareNutrition,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["state"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const n = data?.nutrition;
  const plan = data?.plan;
  const brief = state.cards.find((c) => c.card.kind === "brief" && c.card.expert === "kitchen");
  const planAvg = plan?.days.length
    ? Math.round(plan.days.reduce((a, d) => a + d.protein_g, 0) / plan.days.length) : null;
  return (
    <div className="space-y-3">
      <Panel className="p-4 space-y-4">
        {n ? (
          <>
            <div className="flex items-center justify-between">
              <span className="label">Per person per day · last {n.days} days</span>
              <Pill>Estimate</Pill>
            </div>
            <Bars n={n} />
            <div className="flex gap-2">
              <Pill>Protein {n.split.protein}%</Pill><Pill>Carbs {n.split.carbs}%</Pill><Pill>Fat {n.split.fat}%</Pill>
            </div>
            <p className="text-[12px] text-muted-foreground">
              From {n.orders} order{n.orders === 1 ? "" : "s"}{n.dry_runs ? ` (${n.dry_runs} dry run)` : ""} for {n.people} people.
              Compared with: {n.targets.source}. Not dietary advice; ask your nutritionist.
            </p>
            {planAvg != null && <p className="text-[13px]">Your meal plan: about {planAvg} g protein per person per day.</p>}
          </>
        ) : (
          <p className="text-[14px] text-muted-foreground">See what your groceries add up to: energy, protein, carbs, fat and fibre per person.</p>
        )}
        <div className="flex gap-2">
          <Button variant={n ? "outline" : "default"} className="flex-1 h-11" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? <><Loader2 className="animate-spin" /> Estimating</> : n ? "Refresh" : "Work it out"}
          </Button>
          {n && (
            <Button className="flex-1 h-11" disabled={share.isPending || !!brief} onClick={() => share.mutate()}>
              Share with {data?.nutritionist?.split(" (")[0] ?? "nutritionist"}
            </Button>
          )}
        </div>
      </Panel>
      {brief && <ApprovalCard row={brief} />}
    </div>
  );
}

export function KitchenTab({ state }: { state: AppState }) {
  return (
    <>
      <div className="space-y-1 px-1">
        <h1 className="text-[26px] leading-tight font-medium tracking-tight">Kitchen</h1>
        <p className="text-[15px] text-muted-foreground">What this home buys, eats and needs.</p>
      </div>
      <Section label="Your usuals"><Usuals state={state} /></Section>
      <Section label="Meal plan"><Plan state={state} /></Section>
      <Section label="Nutrition"><NutritionPanel state={state} /></Section>
    </>
  );
}
