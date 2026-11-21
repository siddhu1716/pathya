import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUp, ChevronLeft, Loader2, PhoneOutgoing, Plus, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Dot, Panel, Pill, Row, Section } from "@/components/kit";
import { api, AppState, Dose, Family, Member } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
const SLOTS = ["morning", "afternoon", "night"] as const;

export const useFamily = () => useQuery({ queryKey: ["family"], queryFn: api.family, refetchInterval: 5000 });

function useRefresh() {
  const qc = useQueryClient();
  return () => { qc.invalidateQueries({ queryKey: ["family"] }); qc.invalidateQueries({ queryKey: ["state"] }); };
}

const initials = (name: string) => name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

export function doseTone(doses: Dose[]): "ok" | "warn" | "bad" | null {
  if (!doses.length) return null;
  if (doses.some((d) => d.taken && d.taken !== "yes")) return "bad";
  const hour = new Date().getHours();
  if (doses.some((d) => !d.taken && d.hour <= hour)) return "warn";
  return "ok";
}

function Bar({ label, v, goal, unit, limit = false }: { label: string; v: number; goal: number; unit: string; limit?: boolean }) {
  const pct = goal ? Math.min(100, Math.round((v / goal) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[13px]">
        <span>{label}</span>
        <span className="font-mono tabular-nums text-muted-foreground">{Math.round(v)} / {Math.round(goal)} {unit}{limit ? " max" : ""}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div className={cn("h-full rounded-full", limit && v > goal ? "bg-warning" : "bg-foreground/80")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Board({ fam, onPick }: { fam: Family; onPick: (k: string) => void }) {
  const [rules, setRules] = useState(false);
  const top = fam.board.rows[0];
  return (
    <Panel className="overflow-hidden">
      <div className="px-4 pt-4 pb-2 flex items-baseline justify-between">
        <p className="text-[15px]">{top && top.points > 0 ? <>{top.name} leads this week</> : "Nobody has points yet"}</p>
        <button className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground" onClick={() => setRules(!rules)}>
          {rules ? "Hide" : "How"}
        </button>
      </div>
      {rules && (
        <ul className="px-4 pb-2 text-[12px] text-muted-foreground space-y-0.5">
          {fam.board.rules.map((r) => <li key={r}>{r}</li>)}
          <li>No points for readings or weight.</li>
        </ul>
      )}
      <div className="divide-y border-t">
        {fam.board.rows.map((r) => (
          <button key={r.key} onClick={() => onPick(r.key)} className="w-full flex items-center gap-3 px-4 py-3 text-left active:bg-white/5">
            <span className={cn("font-mono text-[13px] w-6", r.rank === 1 && r.points > 0 ? "text-foreground" : "text-muted-foreground")}>
              {String(r.rank).padStart(2, "0")}
            </span>
            <span className="flex-1 text-[15px] truncate">{r.name}</span>
            {r.streak >= 3 && <Pill tone="ok">{r.streak}-day streak</Pill>}
            <span className="font-mono text-[15px] tabular-nums w-12 text-right">{r.points}</span>
          </button>
        ))}
      </div>
      <p className="px-4 py-2 border-t font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Week of {fam.board.week_of}</p>
    </Panel>
  );
}

function MemberRow({ m, onPick }: { m: Member; onPick: () => void }) {
  const t = m.targets, today = m.today.total;
  const tone = doseTone(m.doses);
  return (
    <button onClick={onPick} className="w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-white/5">
      <span className="w-10 h-10 rounded-full border flex items-center justify-center text-[13px] shrink-0">{initials(m.name)}</span>
      <span className="flex-1 min-w-0 space-y-1.5">
        <span className="flex items-center gap-2">
          <span className="text-[15px] truncate">{m.name}</span>
          {tone && <Dot tone={tone} />}
        </span>
        <span className="flex gap-1.5">
          <span className="h-1 flex-1 rounded-full bg-white/10 overflow-hidden">
            <span className="block h-full bg-foreground/80" style={{ width: `${Math.min(100, (today.kcal / t.kcal) * 100)}%` }} />
          </span>
          <span className="h-1 flex-1 rounded-full bg-white/10 overflow-hidden">
            <span className="block h-full bg-success" style={{ width: `${Math.min(100, (today.protein_g / t.protein_g) * 100)}%` }} />
          </span>
        </span>
        <span className="block font-mono text-[11px] text-muted-foreground">
          {Math.round(today.kcal)} kcal · P {Math.round(today.protein_g)} g{m.relation && m.relation !== "me" ? ` · ${m.relation}` : ""}
        </span>
      </span>
      <Pill>{(m.goal || "maintain").replace("_", " ")}</Pill>
    </button>
  );
}

function AddMember({ open, onClose }: { open: boolean; onClose: () => void }) {
  const refresh = useRefresh();
  const [name, setName] = useState("");
  const [relation, setRelation] = useState("");
  const add = useMutation({
    mutationFn: () => api.addMember(name, relation),
    onSuccess: (m) => { toast.success(`${m.name} added`); setName(""); setRelation(""); refresh(); onClose(); },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="bg-card border-t">
        <form className="p-4 pb-8 space-y-3" onSubmit={(e) => { e.preventDefault(); if (name.trim()) add.mutate(); }}>
          <DrawerHeader className="px-0 text-left">
            <DrawerTitle className="font-medium">Add a family member</DrawerTitle>
            <DrawerDescription>Track their plate and medicines. QuickPick calls only numbers in household.yaml.</DrawerDescription>
          </DrawerHeader>
          <input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (Nanna, Chinni ...)" autoFocus />
          <input className={field} value={relation} onChange={(e) => setRelation(e.target.value)} placeholder="Relation (father, sister ...)" />
          <Button type="submit" className="w-full h-12" disabled={add.isPending || !name.trim()}>Add</Button>
        </form>
      </DrawerContent>
    </Drawer>
  );
}

function TodayPanel({ m }: { m: Member }) {
  const refresh = useRefresh();
  const [text, setText] = useState("");
  const log = useMutation({
    mutationFn: () => api.logMeal(text, m.key),
    onSuccess: (x) => { setText(""); toast.success(`About ${x.kcal} kcal`); refresh(); },
    onError: (e: Error) => toast.error(e.message),
  });
  const t = m.targets, v = m.today.total;
  return (
    <Panel className="p-4 space-y-4">
      <Bar label="Energy" v={v.kcal} goal={t.kcal} unit="kcal" />
      <Bar label="Protein" v={v.protein_g} goal={t.protein_g} unit="g" />
      <Bar label="Fibre" v={v.fibre_g} goal={t.fibre_g} unit="g" />
      <Bar label="Added sugar" v={v.sugar_g ?? 0} goal={t.sugar_g} unit="g" limit />
      {m.today.meals.length > 0 && (
        <ul className="space-y-1.5 border-t pt-3">
          {m.today.meals.map((x) => (
            <li key={x.ts} className="flex justify-between gap-3 text-[14px]">
              <span className="min-w-0 truncate"><span className="text-muted-foreground capitalize">{x.meal || "meal"}: </span>{x.text}</span>
              <span className="font-mono text-[12px] text-muted-foreground shrink-0">{x.kcal} kcal</span>
            </li>
          ))}
        </ul>
      )}
      <form className="flex items-center gap-2 rounded-full border pl-4 pr-1.5 py-1.5 focus-within:border-white/30"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) log.mutate(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={log.isPending}
               placeholder={`What did ${m.key === "me" ? "you" : m.name} eat?`}
               className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground min-w-0" />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0" disabled={log.isPending || !text.trim()} aria-label="Log meal">
          {log.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
        </Button>
      </form>
      <p className="text-[12px] text-muted-foreground">Estimates. Targets: {t.source}.</p>
    </Panel>
  );
}

const doseText = (d: Dose) =>
  d.taken === "yes" ? "Taken" : d.taken === "no" ? "Not taken" : d.taken === "not_sure" ? "Not sure" : d.hour <= new Date().getHours() ? "Not answered yet" : `Due ${d.hour}:00`;

function MedsPanel({ m }: { m: Member }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const [med, setMed] = useState({ name: "", dose: "", food: "", days: "", times: ["morning"] as string[] });
  const add = useMutation({
    mutationFn: () => api.addMed(m.key, { name: med.name, dose: med.dose, food: med.food, times: med.times, days: med.days ? Number(med.days) : null }),
    onSuccess: () => { setMed({ name: "", dose: "", food: "", days: "", times: ["morning"] }); refresh(); }, onError: fail,
  });
  const remove = useMutation({ mutationFn: (i: number) => api.removeMed(m.key, i), onSuccess: refresh, onError: fail });
  const remind = useMutation({ mutationFn: (on: boolean) => api.reminders(m.key, on), onSuccess: refresh, onError: fail });
  const toggle = (s: string) => setMed({ ...med, times: med.times.includes(s) ? med.times.filter((x) => x !== s) : [...med.times, s] });
  return (
    <div className="space-y-3">
      {m.doses.length > 0 && (
        <Panel className="divide-y">
          {m.doses.map((d) => (
            <div key={d.slot} className="px-4 py-3 space-y-0.5">
              <div className="flex justify-between">
                <span className="label">{d.slot}</span>
                <span className={cn("font-mono text-[11px]", d.taken === "yes" ? "text-success" : d.taken ? "text-warning" : "text-muted-foreground")}>{doseText(d)}</span>
              </div>
              <p className="text-[14px]">{d.meds.join(", ")}</p>
              {d.words && <p className="text-[13px] text-muted-foreground">"{d.words}"</p>}
            </div>
          ))}
        </Panel>
      )}
      <Panel className="divide-y overflow-hidden">
        {m.meds.map((x, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <span className="flex-1 min-w-0">
              <span className="block text-[15px] truncate">{x.name_as_written}</span>
              <span className="block font-mono text-[11px] text-muted-foreground">
                {[x.dose, SLOTS.filter((s) => x[s]).join(" · "), x.food, x.days ? `${x.days} days` : ""].filter(Boolean).join(" · ")}
              </span>
            </span>
            <button aria-label="Remove" className="w-8 h-8 -mr-2 flex items-center justify-center text-muted-foreground" onClick={() => remove.mutate(i)}>
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
        <form className="p-4 space-y-2" onSubmit={(e) => { e.preventDefault(); if (med.name.trim() && med.times.length) add.mutate(); }}>
          <input className={field} value={med.name} onChange={(e) => setMed({ ...med, name: e.target.value })} placeholder="Medicine, exactly as written" />
          <div className="grid grid-cols-3 gap-2">
            <input className={field} value={med.dose} onChange={(e) => setMed({ ...med, dose: e.target.value })} placeholder="Dose" />
            <input className={field} value={med.food} onChange={(e) => setMed({ ...med, food: e.target.value })} placeholder="Food" />
            <input className={field} value={med.days} inputMode="numeric" onChange={(e) => setMed({ ...med, days: e.target.value.replace(/\D/g, "") })} placeholder="Days" />
          </div>
          <div className="flex gap-2">
            {SLOTS.map((s) => (
              <button type="button" key={s} onClick={() => toggle(s)}
                      className={cn("flex-1 h-9 rounded-full border text-[13px] capitalize", med.times.includes(s) ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
                {s}
              </button>
            ))}
          </div>
          <Button type="submit" variant="outline" className="w-full h-11" disabled={add.isPending || !med.name.trim() || !med.times.length}>
            <Plus /> Add medicine
          </Button>
        </form>
      </Panel>
      <Row icon={PhoneOutgoing} title="Reminder calls" disabled={!m.has_phone || remind.isPending || !m.meds.length}
           sub={m.has_phone ? "At 9 AM, 2 PM and 9 PM, daily for the course" : "No phone in household.yaml"}
           onClick={() => remind.mutate(!m.reminders)}
           right={<span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{m.reminders ? "on" : "off"}</span>} />
      <p className="text-[12px] text-muted-foreground px-1">QuickPick reminds and records answers in their words. It never suggests or changes a medicine or dose.</p>
    </div>
  );
}

function ProfilePanel({ m, fam, onRemoved }: { m: Member; fam: Family; onRemoved: () => void }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const [p, setP] = useState({
    goal: m.goal || "maintain", age: m.age ?? "", sex: m.sex ?? "", height_cm: m.height_cm ?? "", weight_kg: m.weight_kg ?? "",
    activity: m.activity ?? "sedentary", food: m.food ?? "veg", allergies: m.allergies ?? "", conditions: (m.conditions || []).join(", "),
    kcal: m.override?.kcal ?? "", protein_g: m.override?.protein_g ?? "",
  });
  const num = (v: string | number) => (v === "" ? null : Number(v));
  const save = useMutation({
    mutationFn: () => api.saveMember(m.key, {
      goal: p.goal, age: num(p.age), sex: p.sex, height_cm: num(p.height_cm), weight_kg: num(p.weight_kg), activity: p.activity,
      food: p.food, allergies: p.allergies, conditions: p.conditions.split(",").map((c) => c.trim()).filter(Boolean),
      override: { ...(p.kcal !== "" ? { kcal: Number(p.kcal) } : {}), ...(p.protein_g !== "" ? { protein_g: Number(p.protein_g) } : {}) },
    }),
    onSuccess: () => { toast.success("Saved"); refresh(); }, onError: fail,
  });
  const remove = useMutation({ mutationFn: () => api.removeMember(m.key), onSuccess: () => { refresh(); onRemoved(); }, onError: fail });
  const set = (k: keyof typeof p) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setP({ ...p, [k]: e.target.value });
  return (
    <Panel className="p-4 space-y-3">
      <div className="flex flex-wrap gap-2">
        {Object.entries(fam.goals).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setP({ ...p, goal: id })}
                  className={cn("px-3 h-8 rounded-full border text-[13px]", p.goal === id ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
            {label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input className={field} inputMode="numeric" value={p.age} onChange={set("age")} placeholder="Age" />
        <select className={field} value={p.sex} onChange={set("sex")}>
          <option value="">Sex</option><option value="female">Female</option><option value="male">Male</option>
        </select>
        <input className={field} inputMode="decimal" value={p.height_cm} onChange={set("height_cm")} placeholder="Height (cm)" />
        <input className={field} inputMode="decimal" value={p.weight_kg} onChange={set("weight_kg")} placeholder="Weight (kg)" />
        <select className={field} value={p.activity} onChange={set("activity")}>
          {fam.activity.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select className={field} value={p.food} onChange={set("food")}>
          <option value="veg">Veg</option><option value="egg">Egg</option><option value="non-veg">Non-veg</option>
        </select>
      </div>
      <input className={field} value={p.allergies} onChange={set("allergies")} placeholder="Allergies (never on their plate)" />
      <input className={field} value={p.conditions} onChange={set("conditions")} placeholder="What the doctor said (sugar, BP ...)" />
      <p className="text-[12px] text-muted-foreground">Used only to choose dishes and portions. QuickPick never diagnoses.</p>
      <div className="grid grid-cols-2 gap-2">
        <input className={field} inputMode="numeric" value={p.kcal} onChange={set("kcal")} placeholder="Nutritionist kcal" />
        <input className={field} inputMode="numeric" value={p.protein_g} onChange={set("protein_g")} placeholder="Nutritionist protein g" />
      </div>
      <Button className="w-full h-12" disabled={save.isPending} onClick={() => save.mutate()}>
        {save.isPending && <Loader2 className="animate-spin" />} Save
      </Button>
      {m.added && (
        <Button variant="ghost" className="w-full h-10 text-muted-foreground" disabled={remove.isPending} onClick={() => remove.mutate()}>
          <Trash2 /> Remove {m.name}
        </Button>
      )}
    </Panel>
  );
}

function MemberPage({ m, fam, onBack }: { m: Member; fam: Family; onBack: () => void }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const call = useMutation({ mutationFn: () => api.callMember(m.key), onSuccess: () => { toast.success("Calling"); refresh(); }, onError: fail });
  const daily = useMutation({ mutationFn: () => api.dailyMember(m.key, m.daily_hour == null ? 20 : null), onSuccess: refresh, onError: fail });
  const row = fam.board.rows.find((r) => r.key === m.key);
  return (
    <>
      <button onClick={onBack} className="flex items-center gap-1 text-[14px] text-muted-foreground -ml-1"><ChevronLeft className="w-4 h-4" /> Family</button>
      <div className="flex items-center gap-4 px-1">
        <span className="w-14 h-14 rounded-full border flex items-center justify-center text-[18px]">{initials(m.name)}</span>
        <div className="min-w-0">
          <h1 className="text-[24px] leading-tight font-medium tracking-tight truncate">{m.key === "me" ? `${m.name} (you)` : m.name}</h1>
          <p className="text-[13px] text-muted-foreground">
            {[m.relation !== "me" && m.relation, m.language, row ? `${row.points} pts this week` : ""].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>
      {m.has_phone && (
        <Panel className="divide-y overflow-hidden">
          <Row icon={PhoneOutgoing} title={m.key === "me" ? "Call me now" : `Call ${m.name} now`} sub="Medicines, meals, groceries, a dish idea"
               disabled={call.isPending} onClick={() => call.mutate()} />
          <Row icon={PhoneOutgoing} title="Daily check-in call" sub="Every day at 8 PM" disabled={daily.isPending} onClick={() => daily.mutate()}
               right={<span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{m.daily_hour == null ? "off" : `${m.daily_hour}:00`}</span>} />
        </Panel>
      )}
      <Section label="Today"><TodayPanel m={m} /></Section>
      <Section label="Medicines"><MedsPanel m={m} /></Section>
      <Section label="Profile and goal"><ProfilePanel key={m.key} m={m} fam={fam} onRemoved={onBack} /></Section>
    </>
  );
}

export function FamilyTab({ state }: { state: AppState }) {
  const { data: fam } = useFamily();
  const [pick, setPick] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  if (!fam) return <p className="text-muted-foreground flex items-center gap-2"><Loader2 className="animate-spin" /> Loading</p>;
  const m = fam.members.find((x) => x.key === pick);
  if (m) return <MemberPage m={m} fam={fam} onBack={() => setPick(null)} />;
  return (
    <>
      <div className="space-y-1 px-1">
        <h1 className="text-[26px] leading-tight font-medium tracking-tight">Family</h1>
        <p className="text-[15px] text-muted-foreground">Everyone's plate, medicines and progress.</p>
      </div>
      <Section label="This week"><Board fam={fam} onPick={setPick} /></Section>
      <Section label={`Members · ${fam.members.length}`}>
        <Panel className="divide-y overflow-hidden">
          {fam.members.map((x) => <MemberRow key={x.key} m={x} onPick={() => setPick(x.key)} />)}
        </Panel>
        <Button variant="outline" className="w-full h-12" onClick={() => setAdding(true)}><Plus /> Add a family member</Button>
      </Section>
      <AddMember open={adding} onClose={() => setAdding(false)} />
      {state.dry_run && <p className="text-[12px] text-muted-foreground px-1">Targets are general references, not prescriptions. Ask your doctor or nutritionist.</p>}
    </>
  );
}

/** Home: who still has a dose to confirm, and today's energy for each member. */
export function FamilyToday({ onOpen }: { onOpen: () => void }) {
  const { data: fam } = useFamily();
  if (!fam) return null;
  return (
    <Panel className="divide-y overflow-hidden">
      {fam.members.slice(0, 4).map((m) => {
        const tone = doseTone(m.doses);
        const pending = m.doses.filter((d) => !d.taken && d.hour <= new Date().getHours()).length;
        return (
          <button key={m.key} onClick={onOpen} className="w-full flex items-center gap-3 px-4 py-3 text-left active:bg-white/5">
            <span className="w-8 h-8 rounded-full border flex items-center justify-center text-[12px] shrink-0">{initials(m.name)}</span>
            <span className="flex-1 min-w-0 text-[15px] truncate">{m.name}</span>
            {tone && <span className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground"><Dot tone={tone} />{pending ? `${pending} dose${pending > 1 ? "s" : ""}` : "meds"}</span>}
            <span className="font-mono text-[12px] tabular-nums text-muted-foreground w-24 text-right">{Math.round(m.today.total.kcal)}/{m.targets.kcal}</span>
          </button>
        );
      })}
    </Panel>
  );
}
