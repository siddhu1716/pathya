import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Activity, ArrowUp, Camera, ChevronDown, ChevronLeft, HeartPulse, Loader2, PhoneOutgoing, Plus, Stethoscope, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Dot, Meter, Panel, Pill, Ring, Row, Section } from "@/components/kit";
import { ScanSheet } from "@/components/Scan";
import { api, Dose, Family, key as appKey, Member, server } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
const SLOTS = ["morning", "afternoon", "night"] as const;
const PART: Record<string, string> = { food: "Food", medicines: "Medicines", movement: "Movement", checkins: "Check-in calls" };
const MISSING: Record<string, string> = {
  medicines: "Counts once medicines are listed.",
  movement: "Counts once a watch sends steps (Connect a watch).",
  checkins: "Counts once the daily check-in call is on.",
};

export const useFamily = () => useQuery({ queryKey: ["family"], queryFn: api.family, refetchInterval: 5000 });

function useRefresh() {
  const qc = useQueryClient();
  return () => { qc.invalidateQueries({ queryKey: ["family"] }); qc.invalidateQueries({ queryKey: ["state"] }); };
}

const initials = (name: string) => name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
const who = (m: Member) => (m.key === "me" ? "you" : m.name);
const pctOf = (v: number, goal: number) => (goal ? Math.round((v / goal) * 100) : 0);

export function doseTone(doses: Dose[]): "ok" | "warn" | "bad" | null {
  if (!doses.length) return null;
  if (doses.some((d) => d.taken && d.taken !== "yes")) return "bad";
  const hour = new Date().getHours();
  if (doses.some((d) => !d.taken && d.hour <= hour)) return "warn";
  return "ok";
}

/** What the health score is made of, and what would raise it. */
function HealthSheet({ m, open, onClose }: { m: Member; open: boolean; onClose: () => void }) {
  const h = m.health;
  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="bg-card border-t max-h-[90dvh]">
        <div className="p-4 pb-8 space-y-4 overflow-y-auto">
          <DrawerHeader className="px-0 text-left">
            <DrawerTitle className="font-medium">{m.key === "me" ? "Your" : `${m.name}'s`} health score</DrawerTitle>
            <DrawerDescription>{h.about}</DrawerDescription>
          </DrawerHeader>
          <div className="flex items-center gap-4">
            <Ring value={h.score} size={72} stroke={6} />
            <div>
              <p className="text-[18px]">{h.label}</p>
              <p className="text-[13px] text-muted-foreground">Last 7 days</p>
            </div>
          </div>
          {h.parts.map((p) => (
            <div key={p.part} className="space-y-1.5">
              <div className="flex justify-between text-[14px]">
                <span>{PART[p.part]} <span className="font-mono text-[11px] text-muted-foreground">· weight {p.weight}</span></span>
                <span className="font-mono tabular-nums">{p.percent}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div className={cn("h-full rounded-full", p.percent >= 80 ? "bg-success" : p.percent >= 50 ? "bg-foreground/80" : "bg-warning")} style={{ width: `${p.percent}%` }} />
              </div>
              <p className="text-[13px] text-muted-foreground">{p.detail}</p>
              {p.tips.map((t) => <p key={t} className="text-[13px]">→ {t}</p>)}
            </div>
          ))}
          {h.missing.map((k) => (
            <p key={k} className="text-[13px] text-muted-foreground"><span className="text-foreground/80">{PART[k]}:</span> {MISSING[k]}</p>
          ))}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function GoalBar({ m }: { m: Member }) {
  const g = m.goal_progress;
  if (!g) return null;
  return (
    <Panel className="p-4 space-y-2">
      <div className="flex justify-between text-[14px]">
        <span>{m.goal === "bulk" ? "Bulk" : "Cut"} goal · {g.start} → {g.target} kg</span>
        <span className="font-mono tabular-nums">{g.percent}%</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full bg-success transition-all duration-700" style={{ width: `${g.percent}%` }} />
      </div>
      <p className="text-[12px] text-muted-foreground">Now {g.current} kg · {g.left_kg} kg to go. Update the weight in the profile or scan a body report.</p>
    </Panel>
  );
}

function MemberRow({ m, onPick, onScore }: { m: Member; onPick: () => void; onScore: () => void }) {
  const tone = doseTone(m.doses);
  const today = pctOf(m.today.total.kcal, m.today.targets.kcal);
  return (
    <div className="flex items-center gap-3 px-4 py-3.5">
      <button aria-label={`${m.name}'s health score`} onClick={onScore}><Ring value={m.health.score} /></button>
      <button onClick={onPick} className="flex-1 min-w-0 text-left space-y-1.5 active:opacity-70">
        <span className="flex items-center gap-2">
          <span className="text-[15px] truncate">{m.key === "me" ? `${m.name} (you)` : m.name}</span>
          {m.elder && <span className="font-mono text-[10px] text-muted-foreground">{m.age}</span>}
          {tone && <Dot tone={tone} />}
          {m.watch.length > 0 && <Dot tone="warn" />}
        </span>
        <span className="flex items-center gap-2">
          <span className="h-1 flex-1 rounded-full bg-white/10 overflow-hidden">
            <span className={cn("block h-full", today >= 90 ? "bg-success" : "bg-foreground/70")} style={{ width: `${Math.min(100, today)}%` }} />
          </span>
          <span className="font-mono text-[11px] text-muted-foreground w-24 text-right">today {today}%</span>
        </span>
      </button>
      <Pill>{(m.goal || "maintain").replace("_", " ")}</Pill>
    </div>
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
            <DrawerDescription>Track their plate and medicines. Pathya calls only numbers in household.yaml.</DrawerDescription>
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
  const t = m.today.targets, v = m.today.total;
  return (
    <Panel className="p-4 space-y-4">
      <Meter label="Energy" v={v.kcal} goal={t.kcal} unit="kcal" />
      <Meter label="Protein" v={v.protein_g} goal={t.protein_g} unit="g" />
      <Meter label="Fibre" v={v.fibre_g} goal={t.fibre_g} unit="g" />
      <Meter label="Added sugar" v={v.sugar_g ?? 0} goal={t.sugar_g ?? 0} unit="g" limit />
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
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={log.isPending} placeholder={`What did ${who(m)} eat?`}
               className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground min-w-0" />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0" disabled={log.isPending || !text.trim()} aria-label="Log meal">
          {log.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
        </Button>
      </form>
      <p className="text-[12px] text-muted-foreground">Estimates. Targets: {t.source}</p>
    </Panel>
  );
}

const doseText = (d: Dose) =>
  d.taken === "yes" ? "Taken" : d.taken === "no" ? "Not taken" : d.taken === "not_sure" ? "Not sure" : d.hour <= new Date().getHours() ? "Not answered yet" : `Due ${d.hour}:00`;

function MedsPanel({ m }: { m: Member }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const [adding, setAdding] = useState(false);
  const [med, setMed] = useState({ name: "", dose: "", food: "", days: "", times: ["morning"] as string[] });
  const add = useMutation({
    mutationFn: () => api.addMed(m.key, { name: med.name, dose: med.dose, food: med.food, times: med.times, days: med.days ? Number(med.days) : null }),
    onSuccess: () => { setMed({ name: "", dose: "", food: "", days: "", times: ["morning"] }); setAdding(false); refresh(); }, onError: fail,
  });
  const remove = useMutation({ mutationFn: (i: number) => api.removeMed(m.key, i), onSuccess: refresh, onError: fail });
  const remind = useMutation({ mutationFn: (on: boolean) => api.reminders(m.key, on), onSuccess: refresh, onError: fail });
  const mark = useMutation({ mutationFn: (slot: string) => api.dose(m.key, slot, "yes"), onSuccess: refresh, onError: fail });
  const toggle = (s: string) => setMed({ ...med, times: med.times.includes(s) ? med.times.filter((x) => x !== s) : [...med.times, s] });
  const done = m.doses.filter((d) => d.taken === "yes").length;
  return (
    <div className="space-y-3">
      {m.doses.length > 0 && (
        <Panel className="divide-y">
          <div className="px-4 py-3"><Meter label="Today's doses" v={done} goal={m.doses.length} unit="taken" /></div>
          {m.doses.map((d) => (
            <div key={d.slot} className="px-4 py-3 flex items-start gap-3">
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex justify-between">
                  <span className="label">{d.slot}</span>
                  <span className={cn("font-mono text-[11px]", d.taken === "yes" ? "text-success" : d.taken ? "text-warning" : "text-muted-foreground")}>{doseText(d)}</span>
                </div>
                <p className="text-[14px]">{d.meds.join(", ")}</p>
                {d.words && <p className="text-[13px] text-muted-foreground">"{d.words}"</p>}
              </div>
              {d.taken !== "yes" && (
                <Button variant="outline" size="sm" className="h-8 shrink-0" disabled={mark.isPending} onClick={() => mark.mutate(d.slot)}>Taken</Button>
              )}
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
        {adding ? (
          <form className="p-4 space-y-2" onSubmit={(e) => { e.preventDefault(); if (med.name.trim() && med.times.length) add.mutate(); }}>
            <input className={field} value={med.name} onChange={(e) => setMed({ ...med, name: e.target.value })} placeholder="Medicine, exactly as written" autoFocus />
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
            <Button type="submit" className="w-full h-11" disabled={add.isPending || !med.name.trim() || !med.times.length}>Add medicine</Button>
          </form>
        ) : (
          <Row icon={Plus} title="Add a medicine" sub="Type it, or scan the strip or prescription" onClick={() => setAdding(true)} />
        )}
        <Row icon={PhoneOutgoing} title="Reminder calls" disabled={!m.has_phone || remind.isPending || !m.meds.length}
             sub={m.has_phone ? "9 AM, 2 PM, 9 PM, daily for the course" : "No phone in household.yaml"}
             onClick={() => remind.mutate(!m.reminders)}
             right={<span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{m.reminders ? "on" : "off"}</span>} />
      </Panel>
      <p className="text-[12px] text-muted-foreground px-1">Pathya reminds and records answers in their words. It never suggests or changes a medicine or dose.</p>
    </div>
  );
}

function ProfilePanel({ m, fam, onRemoved }: { m: Member; fam: Family; onRemoved: () => void }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const [p, setP] = useState({
    goal: m.goal || "maintain", age: m.age ?? "", sex: m.sex ?? "", height_cm: m.height_cm ?? "", weight_kg: m.weight_kg ?? "",
    target_weight_kg: m.target_weight_kg ?? "", activity: m.activity ?? "sedentary", food: m.food ?? "veg",
    allergies: m.allergies ?? "", conditions: (m.conditions || []).join(", "), kcal: m.override?.kcal ?? "", protein_g: m.override?.protein_g ?? "",
  });
  const num = (v: string | number) => (v === "" ? null : Number(v));
  const save = useMutation({
    mutationFn: () => api.saveMember(m.key, {
      goal: p.goal, age: num(p.age), sex: p.sex, height_cm: num(p.height_cm), weight_kg: num(p.weight_kg), target_weight_kg: num(p.target_weight_kg),
      activity: p.activity, food: p.food, allergies: p.allergies, conditions: p.conditions.split(",").map((c) => c.trim()).filter(Boolean),
      override: { ...(p.kcal !== "" ? { kcal: Number(p.kcal) } : {}), ...(p.protein_g !== "" ? { protein_g: Number(p.protein_g) } : {}) },
    }),
    onSuccess: () => { toast.success("Saved: targets updated"); refresh(); }, onError: fail,
  });
  const remove = useMutation({ mutationFn: () => api.removeMember(m.key), onSuccess: () => { refresh(); onRemoved(); }, onError: fail });
  const set = (k: keyof typeof p) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setP({ ...p, [k]: e.target.value });
  return (
    <Panel className="p-4 space-y-3">
      <p className="label">Goal</p>
      <div className="flex flex-wrap gap-2">
        {Object.entries(fam.goals).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setP({ ...p, goal: id })}
                  className={cn("px-3 h-8 rounded-full border text-[13px]", p.goal === id ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
            {label}
          </button>
        ))}
      </div>
      {(p.goal === "bulk" || p.goal === "cut") && (
        <input className={field} inputMode="decimal" value={p.target_weight_kg} onChange={set("target_weight_kg")} placeholder="Goal weight (kg), for the goal bar" />
      )}
      <p className="label pt-1">Body</p>
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
      {m.body && Object.keys(m.body).length > 0 && (
        <p className="text-[12px] font-mono text-muted-foreground">
          Body report{m.body.date ? ` ${m.body.date}` : ""}: {[m.body.body_fat_pct && `fat ${m.body.body_fat_pct}%`, m.body.skeletal_muscle_kg && `muscle ${m.body.skeletal_muscle_kg} kg`, m.body.bmr_kcal && `BMR ${m.body.bmr_kcal}`].filter(Boolean).join(" · ")}
        </p>
      )}
      <p className="label pt-1">Health notes</p>
      <input className={field} value={p.allergies} onChange={set("allergies")} placeholder="Allergies (never on their plate)" />
      <input className={field} value={p.conditions} onChange={set("conditions")} placeholder="What the doctor said (sugar, BP ...)" />
      <p className="text-[12px] text-muted-foreground">Used only to choose dishes and portions. Pathya never diagnoses.</p>
      <p className="label pt-1">Nutritionist (optional)</p>
      <div className="grid grid-cols-2 gap-2">
        <input className={field} inputMode="numeric" value={p.kcal} onChange={set("kcal")} placeholder="kcal a day" />
        <input className={field} inputMode="numeric" value={p.protein_g} onChange={set("protein_g")} placeholder="Protein g a day" />
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

function Checkups({ m }: { m: Member }) {
  const [all, setAll] = useState(false);
  const shown = all ? m.checkups : m.checkups.slice(0, 3);
  return (
    <Panel className="divide-y">
      {shown.map((c) => (
        <div key={c.what} className="px-4 py-3 flex gap-3">
          <Stethoscope className="w-4 h-4 mt-0.5 shrink-0 text-muted-foreground" />
          <div>
            <p className="text-[15px]">{c.what}</p>
            <p className="text-[13px] text-muted-foreground">{c.why} <span className="font-mono text-[11px]">({c.source})</span></p>
          </div>
        </div>
      ))}
      {m.checkups.length > 3 && (
        <button className="w-full px-4 py-3 text-left font-mono text-[11px] uppercase tracking-wider text-muted-foreground" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${m.checkups.length}`}
        </button>
      )}
      <p className="px-4 py-3 text-[12px] text-muted-foreground">
        What people {m.age}+ are usually offered. Ask the doctor which apply to {who(m)}. Pathya never diagnoses.
      </p>
    </Panel>
  );
}

function WatchHelp({ open, onClose, m }: { open: boolean; onClose: () => void; m: Member }) {
  const url = `${server() || window.location.origin}/api/activity/${m.key}`;
  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="bg-card border-t">
        <div className="p-4 pb-8 space-y-3">
          <DrawerHeader className="px-0 text-left">
            <DrawerTitle className="font-medium">Connect an Apple Watch</DrawerTitle>
            <DrawerDescription>Apple Health has no web access, so an iPhone Shortcut sends today's numbers. Run it as a daily automation.</DrawerDescription>
          </DrawerHeader>
          <ol className="text-[14px] space-y-1.5 list-decimal pl-5">
            <li>Shortcuts → New → <b>Find Health Samples</b>: Steps, today, sum. Again for Active Energy.</li>
            <li><b>Get contents of URL</b>, method POST, JSON body: steps, active_kcal, source "Apple Watch".</li>
            <li>Header <span className="font-mono">X-QuickPick-Key</span> with your key.</li>
            <li>Automation → Time of day (for example 9 PM) → run this shortcut.</li>
          </ol>
          <p className="font-mono text-[12px] break-all rounded-xl border p-3">POST {url}<br />X-QuickPick-Key: {appKey() || "(your key)"}</p>
          <p className="text-[12px] text-muted-foreground">With a watch, today's energy target becomes a sedentary base plus the active energy it measured. WHOOP has an official API: it can be added with a WHOOP developer app.</p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function Chip({ icon: Icon, label, onClick, disabled, on }: { icon: typeof Camera; label: string; onClick: () => void; disabled?: boolean; on?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
            className={cn("flex flex-col items-center justify-center gap-1.5 rounded-2xl border h-20 text-[12px] active:bg-white/5 disabled:opacity-40",
              on && "border-success/40 text-success")}>
      <Icon className="w-5 h-5" />
      <span className="leading-tight text-center px-1">{label}</span>
    </button>
  );
}

function MemberPage({ m, fam, onBack }: { m: Member; fam: Family; onBack: () => void }) {
  const refresh = useRefresh();
  const fail = (e: Error) => toast.error(e.message);
  const call = useMutation({ mutationFn: () => api.callMember(m.key), onSuccess: () => { toast.success("Calling"); refresh(); }, onError: fail });
  const daily = useMutation({ mutationFn: () => api.dailyMember(m.key, m.daily_hour == null ? 20 : null), onSuccess: refresh, onError: fail });
  const [scanning, setScanning] = useState(false);
  const [watchHelp, setWatchHelp] = useState(false);
  const [score, setScore] = useState(false);
  const [editing, setEditing] = useState(false);
  return (
    <>
      <button onClick={onBack} className="flex items-center gap-1 text-[14px] text-muted-foreground -ml-1"><ChevronLeft className="w-4 h-4" /> Family</button>
      <div className="flex items-center gap-4 px-1">
        <button aria-label="Health score" onClick={() => setScore(true)} className="flex flex-col items-center gap-1">
          <Ring value={m.health.score} size={64} stroke={5} />
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Health</span>
        </button>
        <div className="min-w-0">
          <h1 className="text-[24px] leading-tight font-medium tracking-tight truncate">{m.key === "me" ? `${m.name} (you)` : m.name}</h1>
          <p className="text-[13px] text-muted-foreground">
            {[m.relation !== "me" && m.relation, m.age && `${m.age} yrs`, m.language].filter(Boolean).join(" · ")}
          </p>
          <p className="text-[13px] pt-0.5">{fam.goals[m.goal] ?? m.goal} · <button className="underline underline-offset-4 text-muted-foreground" onClick={() => setScore(true)}>{m.health.label}</button></p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Chip icon={PhoneOutgoing} label={m.key === "me" ? "Call me" : `Call ${m.name}`} onClick={() => call.mutate()} disabled={!m.has_phone || call.isPending} />
        <Chip icon={Camera} label="Scan" onClick={() => setScanning(true)} />
        <Chip icon={HeartPulse} label={m.daily_hour == null ? "Daily call off" : `Daily ${m.daily_hour}:00`} on={m.daily_hour != null}
              onClick={() => daily.mutate()} disabled={!m.has_phone || daily.isPending} />
      </div>
      <p className="text-[12px] text-muted-foreground px-1 -mt-3">
        One call covers meals, medicines, groceries, how {who(m)} {m.key === "me" ? "feel" : "feels"} and questions for the doctor.
      </p>
      {!m.has_phone && <p className="text-[12px] text-muted-foreground px-1">No phone in household.yaml, so Pathya can't call {m.name}. Everything else works.</p>}
      {m.watch.length > 0 && (
        <Panel className="p-4 space-y-1 border-warning/40">
          <p className="label text-warning">For the family</p>
          {m.watch.map((w) => <p key={w} className="text-[14px]">{w}</p>)}
          <p className="text-[12px] text-muted-foreground">From logged meals only. Talk to {m.name} or the doctor if you are worried.</p>
        </Panel>
      )}
      <GoalBar m={m} />
      <Section label="Today"><TodayPanel m={m} /></Section>
      <Section label="Medicines"><MedsPanel m={m} /></Section>
      {m.checkups.length > 0 && <Section label={`Checkups at ${m.age}`}><Checkups m={m} /></Section>}
      <Panel className="divide-y overflow-hidden">
        <Row icon={Activity} title={m.activity ? `${m.activity.steps.toLocaleString("en-IN")} steps · ${Math.round(m.activity.active_kcal)} active kcal` : "Connect a watch"}
             sub={m.activity ? `Today, from ${m.activity.source}` : "Apple Watch through an iPhone Shortcut"} onClick={() => setWatchHelp(true)} />
        <Row icon={ChevronDown} title="Profile and goal" sub="Age, body, health notes, nutritionist targets" onClick={() => setEditing(!editing)}
             right={<ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform", editing && "rotate-180")} />} />
      </Panel>
      {editing && <ProfilePanel key={`${m.key}-${m.weight_kg}-${m.height_cm}`} m={m} fam={fam} onRemoved={onBack} />}
      <ScanSheet open={scanning} onClose={() => setScanning(false)} who={m.key} />
      <WatchHelp open={watchHelp} onClose={() => setWatchHelp(false)} m={m} />
      <HealthSheet m={m} open={score} onClose={() => setScore(false)} />
    </>
  );
}

export function FamilyTab({ pick, setPick }: { pick: string | null; setPick: (k: string | null) => void }) {
  const { data: fam } = useFamily();
  const [adding, setAdding] = useState(false);
  const [scoreFor, setScoreFor] = useState<Member | null>(null);
  if (!fam) return <p className="text-muted-foreground flex items-center gap-2"><Loader2 className="animate-spin" /> Loading</p>;
  const m = fam.members.find((x) => x.key === pick);
  if (m) return <MemberPage m={m} fam={fam} onBack={() => setPick(null)} />;
  const ranked = [...fam.members].sort((a, b) => (b.health.score ?? -1) - (a.health.score ?? -1));
  return (
    <>
      <div className="space-y-1 px-1">
        <h1 className="text-[26px] leading-tight font-medium tracking-tight">Family</h1>
        <p className="text-[15px] text-muted-foreground">{fam.star ? `${fam.star} has the best health score this week.` : "Health scores fill in as meals and medicines are logged."}</p>
      </div>
      <Panel className="divide-y overflow-hidden">
        {ranked.map((x) => <MemberRow key={x.key} m={x} onPick={() => setPick(x.key)} onScore={() => setScoreFor(x)} />)}
      </Panel>
      <Button variant="outline" className="w-full h-12" onClick={() => setAdding(true)}><Plus /> Add a family member</Button>
      <p className="text-[12px] text-muted-foreground px-1">{fam.about}</p>
      <AddMember open={adding} onClose={() => setAdding(false)} />
      {scoreFor && <HealthSheet m={fam.members.find((x) => x.key === scoreFor.key) ?? scoreFor} open onClose={() => setScoreFor(null)} />}
    </>
  );
}

/** Home: one card per member (health score ring, today's energy, doses). */
export function FamilyStrip({ onOpen }: { onOpen: (key: string) => void }) {
  const { data: fam } = useFamily();
  if (!fam) return null;
  return (
    <div className="flex gap-3 overflow-x-auto snap-x -mx-4 px-4 pb-1">
      {fam.members.map((m) => {
        const tone = doseTone(m.doses);
        const pending = m.doses.filter((d) => !d.taken && d.hour <= new Date().getHours()).length;
        const today = pctOf(m.today.total.kcal, m.today.targets.kcal);
        return (
          <button key={m.key} onClick={() => onOpen(m.key)}
                  className="snap-start shrink-0 w-[9.5rem] rounded-2xl border bg-card p-3 text-left space-y-2.5 active:bg-white/5">
            <div className="flex items-center justify-between">
              <Ring value={m.health.score} size={40} />
              {tone && <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground"><Dot tone={tone} />{pending ? `${pending} dose` : "meds"}</span>}
            </div>
            <div>
              <p className="text-[15px] truncate">{m.key === "me" ? "You" : m.name}</p>
              <p className="text-[12px] text-muted-foreground truncate">{m.health.label}</p>
            </div>
            <div className="space-y-1">
              <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                <div className={cn("h-full", today >= 90 ? "bg-success" : "bg-foreground/70")} style={{ width: `${Math.min(100, today)}%` }} />
              </div>
              <p className="font-mono text-[10px] text-muted-foreground">today {today}% of energy</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
