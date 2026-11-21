import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApprovalCard } from "@/components/ApprovalCard";
import { useFamily } from "@/components/FamilyTab";
import { AtHome } from "@/components/HomeStock";
import { Panel, Pill, Section } from "@/components/kit";
import { api, AppState, Macros, MealPlan, Nutrition } from "@/lib/api";
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
      <Button className="w-full h-12" disabled={!chosen.length || reorder.isPending || !(state.swiggy || state.zepto)}
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
  const { data: fam } = useFamily();
  const [days, setDays] = useState(3);
  const [notes, setNotes] = useState("");
  const [off, setOff] = useState<Record<string, boolean>>({});
  const [guests, setGuests] = useState(0);
  const eaters = (fam?.members ?? []).filter((m) => !off[m.key]);
  const make = useMutation({
    mutationFn: () => api.mealplan(days, notes, fam ? eaters.map((m) => m.key) : null, guests),
    onSuccess: () => { toast.success("Plan ready"); qc.invalidateQueries({ queryKey: ["kitchen"] }); qc.invalidateQueries({ queryKey: ["state"] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  const plan = data?.plan;
  const card = state.cards.find((c) => c.card.kind === "plan");
  return (
    <div className="space-y-3">
      <Panel className="p-4 space-y-3">
        <p className="label">Who is eating</p>
        <div className="flex flex-wrap gap-2">
          {(fam?.members ?? []).map((m) => (
            <button key={m.key} onClick={() => setOff({ ...off, [m.key]: !off[m.key] })}
                    className={cn("px-3 h-9 rounded-full border text-[14px]", !off[m.key] ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
              {m.key === "me" ? "Me" : m.name}
            </button>
          ))}
          <span className="flex items-center gap-1 rounded-full border px-1 h-9">
            <button aria-label="Fewer guests" className="w-7 h-7 text-muted-foreground" onClick={() => setGuests(Math.max(0, guests - 1))}>-</button>
            <span className="text-[14px] tabular-nums min-w-14 text-center">{guests} guest{guests === 1 ? "" : "s"}</span>
            <button aria-label="More guests" className="w-7 h-7 text-muted-foreground" onClick={() => setGuests(Math.min(20, guests + 1))}>+</button>
          </span>
        </div>
        <p className="text-[13px] text-muted-foreground">
          {eaters.length + guests} eating · {data ? `${data.prefs.diet} · ${data.prefs.cuisine}` : ""}. One menu, a plate for each
          person's goal, from what's at home.
        </p>
        <div className="flex gap-2">
          {[1, 3, 7].map((d) => (
            <button key={d} onClick={() => setDays(d)}
                    className={cn("flex-1 h-10 rounded-full border text-[14px]", days === d ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
              {d} day{d > 1 ? "s" : ""}
            </button>
          ))}
        </div>
        <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything to keep in mind? (less oil, someone fasting on Monday)"
               className="w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30" />
        <Button className="w-full h-12" disabled={make.isPending || eaters.length + guests === 0} onClick={() => make.mutate()}>
          {make.isPending ? <><Loader2 className="animate-spin" /> Planning (about 30 s)</> : plan ? <><RefreshCw /> New plan</> : "Plan meals"}
        </Button>
      </Panel>
      {card && <ApprovalCard row={card} />}
      {plan && plan.days.some((d) => d.meals.some((m) => m.parts?.length)) && <PlanView plan={plan} />}
      {plan && !card && !plan.days.some((d) => d.meals.some((m) => m.parts?.length)) && (
        <Panel className="divide-y">
          {plan.days.map((d) => (
            <div key={d.day} className="px-4 py-3 space-y-1">
              <div className="flex justify-between"><span className="label">{d.day}</span><span className="font-mono text-[11px] text-muted-foreground">{d.kcal} kcal · P {d.protein_g} g</span></div>
              {d.meals.map((m) => <p key={m.slot} className="text-[14px]"><span className="text-muted-foreground capitalize">{m.slot}: </span>{m.dish}</p>)}
              {(d.people ?? []).map((p) => (
                <p key={p.who} className="text-[13px] text-muted-foreground"><span className="text-foreground/85">{p.who}:</span> {p.plate} · {p.kcal} kcal</p>
              ))}
            </div>
          ))}
        </Panel>
      )}
    </div>
  );
}

/** One person's plate, food by food, with +/- (the plan and the cook's call use these quantities). */
function PlanView({ plan }: { plan: MealPlan }) {
  const qc = useQueryClient();
  const { data: fam } = useFamily();
  const [d, setD] = useState(0);
  const day = plan.days[Math.min(d, plan.days.length - 1)];
  const people = day.people ?? [];
  const [pick, setPick] = useState<string | null>(null);
  const who = people.find((p) => p.who === pick)?.who ?? people[0]?.who;
  const save = (p: MealPlan) => qc.setQueryData(["kitchen"], (old: object | undefined) => (old ? { ...old, plan: { ...plan, ...p } } : old));
  const fail = (e: Error) => toast.error(e.message);
  const portion = useMutation({ mutationFn: (a: { m: number; part: number; qty: number }) => api.portion(d, a.m, a.part, who!, a.qty), onSuccess: save, onError: fail });
  const fit = useMutation({ mutationFn: () => api.fit(d, who!), onSuccess: (p) => { save(p); toast.success(`Fitted to ${who}'s target`); }, onError: fail });
  if (!who) return null;
  const totals = people.find((p) => p.who === who)!;
  const member = fam?.members.find((m) => m.name === who);
  const t = member?.targets;
  return (
    <Panel className="overflow-hidden">
      {plan.days.length > 1 && (
        <div className="flex gap-2 px-4 pt-4 overflow-x-auto">
          {plan.days.map((x, i) => (
            <button key={i} onClick={() => setD(i)} className={cn("px-3 h-8 rounded-full border text-[13px] shrink-0", i === d ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>{x.day}</button>
          ))}
        </div>
      )}
      <div className="flex gap-2 px-4 pt-3 overflow-x-auto">
        {people.map((p) => (
          <button key={p.who} onClick={() => setPick(p.who)} className={cn("px-3 h-8 rounded-full border text-[13px] shrink-0", p.who === who ? "bg-white/10 border-white/30" : "text-muted-foreground")}>{p.who}</button>
        ))}
      </div>
      <div className="px-4 py-3 space-y-2 border-b">
        {t ? (
          <>
            <MiniBar label="Energy" v={totals.kcal} goal={t.kcal} unit="kcal" />
            <MiniBar label="Protein" v={totals.protein_g} goal={t.protein_g} unit="g" />
          </>
        ) : <p className="font-mono text-[12px] text-muted-foreground">{totals.kcal} kcal · protein {totals.protein_g} g</p>}
        {totals.plate && <p className="text-[13px] text-muted-foreground">{totals.plate}</p>}
      </div>
      <div className="divide-y">
        {day.meals.map((meal, mi) => {
          const qty = meal.portions?.find((p) => p.who === who)?.qty ?? [];
          return (
            <div key={mi} className="px-4 py-3 space-y-2">
              <p className="text-[14px]"><span className="label mr-2">{meal.slot}</span>{meal.dish}</p>
              {(meal.parts ?? []).map((part, pi) => {
                const q = qty[pi] ?? 0;
                return (
                  <div key={pi} className="flex items-center gap-2">
                    <span className={cn("flex-1 min-w-0 text-[14px] truncate", !q && "text-muted-foreground line-through")}>{part.food}</span>
                    <span className="font-mono text-[11px] text-muted-foreground w-14 text-right">{Math.round(part.kcal * q)} kcal</span>
                    <span className="flex items-center rounded-full border h-8">
                      <button aria-label={`Less ${part.food}`} className="w-8 h-8 text-muted-foreground" disabled={portion.isPending || q <= 0}
                              onClick={() => portion.mutate({ m: mi, part: pi, qty: Math.max(0, q - 0.5) })}>-</button>
                      <span className="font-mono text-[12px] tabular-nums min-w-16 text-center">{q} {part.unit}</span>
                      <button aria-label={`More ${part.food}`} className="w-8 h-8 text-muted-foreground" disabled={portion.isPending}
                              onClick={() => portion.mutate({ m: mi, part: pi, qty: q + 0.5 })}>+</button>
                    </span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      {t && (
        <div className="p-4 border-t">
          <Button variant="outline" className="w-full h-11" disabled={fit.isPending} onClick={() => fit.mutate()}>
            {fit.isPending ? <Loader2 className="animate-spin" /> : null} Fit {who}'s plate to {t.kcal} kcal
          </Button>
        </div>
      )}
    </Panel>
  );
}

function MiniBar({ label, v, goal, unit }: { label: string; v: number; goal: number; unit: string }) {
  const pct = goal ? Math.min(100, Math.round((v / goal) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[12px]"><span>{label}</span><span className="font-mono tabular-nums text-muted-foreground">{Math.round(v)} / {goal} {unit}</span></div>
      <div className="h-1 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-foreground/80" style={{ width: `${pct}%` }} /></div>
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
  const saved = data?.nutrition;
  const n = saved && data ? { ...saved, targets: data.targets } : saved;      // always each member's current targets
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
        <h1 className="text-[26px] leading-tight font-medium tracking-tight">Meals</h1>
        <p className="text-[15px] text-muted-foreground">One kitchen, a plate for everyone.</p>
      </div>
      <Section label="Meal plan"><Plan state={state} /></Section>
      <Section label="At home"><AtHome state={state} /></Section>
      <Section label="Your usuals"><Usuals state={state} /></Section>
      <Section label="Nutrition"><NutritionPanel state={state} /></Section>
    </>
  );
}
