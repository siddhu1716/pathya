import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Loader2, Plus, Search, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { useFamily } from "@/components/FamilyTab";
import { api, AppState, Clinic } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
const iso = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};
const WHEN = { week: ["This week", 1, 7], next: ["Next week", 7, 13] } as const;
const PARTS = ["morning", "afternoon", "evening", "any"] as const;
const initials = (name: string) =>
  name.replace(/\(.*?\)/g, "").replace(/^\s*dr\.?\s*/i, "").split(/\s+/).filter((w) => /^[a-z]/i.test(w)).slice(0, 2)
    .map((w) => w[0].toUpperCase()).join("") || "Dr";
const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Chips<T extends string>({ value, options, onChange, label }: {
  value: T; options: readonly T[] | T[]; onChange: (v: T) => void; label?: (v: T) => string;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onChange(o)}
                className={cn("press h-8 px-3 rounded-full border text-[13px]",
                  value === o ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
          {label ? label(o) : o}
        </button>
      ))}
    </div>
  );
}

type Ask = { patient: string; when: keyof typeof WHEN; part: (typeof PARTS)[number]; reason: string };

/** Who, when and why: shared by booking a saved doctor and finding a new one. */
function AskFields({ ask, set }: { ask: Ask; set: (a: Ask) => void }) {
  const { data: fam } = useFamily();
  const members = fam?.members ?? [];
  return (
    <div className="space-y-2.5">
      <Chips value={ask.patient} options={members.map((m) => m.key)} onChange={(patient) => set({ ...ask, patient })}
             label={(k) => (k === "me" ? "Me" : members.find((m) => m.key === k)?.name ?? k)} />
      <div className="flex gap-1.5 flex-wrap">
        <Chips value={ask.when} options={Object.keys(WHEN) as (keyof typeof WHEN)[]} onChange={(when) => set({ ...ask, when })}
               label={(w) => WHEN[w][0]} />
        <Chips value={ask.part} options={PARTS} onChange={(part) => set({ ...ask, part })} label={(p) => sentence(p)} />
      </div>
      <input className={field} value={ask.reason} onChange={(e) => set({ ...ask, reason: e.target.value })}
             placeholder="Reason, in their words (sugar review, knee pain)" />
    </div>
  );
}

const range = (ask: Ask) => ({ from: iso(WHEN[ask.when][1]), to: iso(WHEN[ask.when][2]) });

function DoctorCard({ c, open, onOpen, ask, setAsk, done, fail }: {
  c: Clinic; open: boolean; onOpen: () => void; ask: Ask; setAsk: (a: Ask) => void; done: (m: string) => void; fail: (e: Error) => void;
}) {
  const book = useMutation({
    mutationFn: () => {
      const w = range(ask);
      return api.book({ patient: ask.patient, clinic: c.key, window_start: `${w.from}T00:00`, window_end: `${w.to}T23:59`,
        part: ask.part, reason: ask.reason || "consultation" });
    },
    onSuccess: () => done(`Calling ${c.clinic} to book`),
    onError: fail,
  });
  return (
    <div className={cn("rounded-2xl border bg-card transition-smooth", open && "border-white/20")}>
      <button type="button" onClick={onOpen} className="press w-full flex items-center gap-3 p-4 text-left">
        <span className="w-11 h-11 rounded-full bg-white/[0.06] border flex items-center justify-center font-mono text-[13px] shrink-0">{initials(c.doctor)}</span>
        <span className="flex-1 min-w-0">
          <span className="block text-[15px] leading-tight truncate">{c.doctor}</span>
          <span className="block text-[12px] text-muted-foreground truncate mt-0.5">{[c.specialty, c.clinic].filter(Boolean).join(" · ")}</span>
          {(c.sees.length > 0 || c.phone_hint) && (
            <span className="block font-mono text-[11px] text-muted-foreground/80 mt-1">
              {[c.sees.length ? `sees ${c.sees.join(", ")}` : "", c.phone_hint].filter(Boolean).join(" · ")}
            </span>
          )}
        </span>
        <span className={cn("h-8 px-3 rounded-full text-[13px] flex items-center shrink-0", open ? "border text-muted-foreground" : "bg-primary text-primary-foreground")}>
          {open ? "Close" : "Book"}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 rise">
          <AskFields ask={ask} set={setAsk} />
          <Button className="w-full h-12" disabled={book.isPending} onClick={() => book.mutate()}>
            {book.isPending && <Loader2 className="animate-spin" />} Phone {c.clinic.split(",")[0]} to book
          </Button>
          <p className="text-[12px] text-muted-foreground">Pathya books only inside these days and times, and adds it to your calendar after.</p>
        </div>
      )}
    </div>
  );
}

function AddDoctor({ specialties, onDone, fail }: { specialties: string[]; onDone: () => void; fail: (e: Error) => void }) {
  const qc = useQueryClient();
  const [d, setD] = useState({ doctor: "", specialty: "", clinic: "", phone: "" });
  const add = useMutation({
    mutationFn: () => api.addDoctor(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["doctors"] }); qc.invalidateQueries({ queryKey: ["state"] }); onDone(); },
    onError: fail,
  });
  const ok = d.doctor.trim() && d.clinic.trim() && d.phone.replace(/\D/g, "").length >= 10;
  return (
    <form className="rounded-2xl border p-4 space-y-2 rise" onSubmit={(e) => { e.preventDefault(); if (ok) add.mutate(); }}>
      <input className={field} value={d.doctor} onChange={(e) => setD({ ...d, doctor: e.target.value })} placeholder="Doctor's name (Dr. Meera Rao)" autoFocus />
      <select className={field} value={d.specialty} onChange={(e) => setD({ ...d, specialty: e.target.value })}>
        <option value="">Specialty (optional)</option>
        {specialties.map((s) => <option key={s}>{s}</option>)}
      </select>
      <input className={field} value={d.clinic} onChange={(e) => setD({ ...d, clinic: e.target.value })} placeholder="Clinic or hospital, area" />
      <input className={field} type="tel" inputMode="tel" value={d.phone} onChange={(e) => setD({ ...d, phone: e.target.value })} placeholder="Appointment number" />
      <Button type="submit" className="w-full h-11" disabled={add.isPending || !ok}>{add.isPending && <Loader2 className="animate-spin" />} Save doctor</Button>
      <p className="text-[12px] text-muted-foreground">Saved in household.yaml. Pathya phones only numbers saved there.</p>
    </form>
  );
}

function FindDoctor({ specialties, ask, setAsk, done, fail }: {
  specialties: string[]; ask: Ask; setAsk: (a: Ask) => void; done: (m: string) => void; fail: (e: Error) => void;
}) {
  const [kind, setKind] = useState(specialties[0] ?? "General physician");
  const [hospital, setHospital] = useState("");
  const [area, setArea] = useState("");
  const find = useMutation({
    mutationFn: () => {
      const w = range(ask);
      return api.bookRequest({ patient: ask.patient, hospital, doctor: hospital.trim() ? "" : kind, area, reason: ask.reason,
        from_date: w.from, to_date: w.to, part: ask.part });
    },
    onSuccess: () => done("Card on Home: tap it and Pathya looks up the number"),
    onError: fail,
  });
  return (
    <div className="space-y-3">
      <div className="flex gap-1.5 overflow-x-auto -mx-4 px-4 pb-1 no-scrollbar">
        {specialties.map((s) => (
          <button key={s} type="button" onClick={() => { setKind(s); setHospital(""); }}
                  className={cn("press h-9 px-3.5 rounded-full border text-[13px] whitespace-nowrap",
                    kind === s && !hospital.trim() ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
            {s}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input className={field} value={hospital} onChange={(e) => setHospital(e.target.value)} placeholder="Or a hospital (Yashoda)" />
        <input className={field} value={area} onChange={(e) => setArea(e.target.value)} placeholder="Area (Madhapur)" />
      </div>
      <AskFields ask={ask} set={setAsk} />
      <Button className="w-full h-12" disabled={find.isPending || (!area.trim() && !hospital.trim())} onClick={() => find.mutate()}>
        {find.isPending ? <Loader2 className="animate-spin" /> : <Search />} Find {hospital.trim() || `a ${kind.toLowerCase()}`} and ask me first
      </Button>
    </div>
  );
}

/** Book a doctor: your doctors as profiles (one tap to book), a specialist near you, a planning call, or online now. */
export function DoctorSheet({ state, done, fail }: { state: AppState; done: (m: string) => void; fail: (e: Error) => void }) {
  const { data } = useQuery({ queryKey: ["doctors"], queryFn: api.doctors });
  const { data: fam } = useFamily();
  const [tab, setTab] = useState<"doctors" | "call" | "online">("doctors");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [ask, setAsk] = useState<Ask>({ patient: "me", when: "week", part: "morning", reason: "" });
  const [caller, setCaller] = useState("me");
  const intake = useMutation({ mutationFn: () => api.intake(caller), onSuccess: () => done("Calling to plan the appointment"), onError: fail });
  const saved = data?.saved ?? state.clinics;
  return (
    <div className="p-4 pb-8 space-y-4">
      <DrawerHeader className="px-0 text-left">
        <DrawerTitle className="font-medium">Book a doctor</DrawerTitle>
        <DrawerDescription>Pathya phones the clinic and books only inside your days and times. It never diagnoses.</DrawerDescription>
      </DrawerHeader>
      <div className="grid grid-cols-3 rounded-full border p-0.5">
        {([["doctors", "Doctors"], ["call", "Plan by call"], ["online", "Online now"]] as const).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} className={cn("h-9 rounded-full text-[13px]", tab === id ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>{label}</button>
        ))}
      </div>

      {tab === "doctors" && (
        <div className="space-y-5 stagger">
          <section className="space-y-2.5">
            <h3 className="label px-1">Your doctors</h3>
            {saved.map((c) => (
              <DoctorCard key={c.key} c={c} open={open === c.key} onOpen={() => {
                setOpen(open === c.key ? null : c.key);
                const sees = (fam?.members ?? []).find((m) => c.sees.includes(m.name));
                if (sees) setAsk({ ...ask, patient: sees.key });
              }} ask={ask} setAsk={setAsk} done={done} fail={fail} />
            ))}
            {adding ? <AddDoctor specialties={data?.specialties ?? []} onDone={() => setAdding(false)} fail={fail} /> : (
              <button type="button" onClick={() => setAdding(true)}
                      className="press w-full rounded-2xl border border-dashed p-4 flex items-center gap-3 text-left text-muted-foreground">
                <span className="w-11 h-11 rounded-full border border-dashed flex items-center justify-center"><Plus className="w-4 h-4" /></span>
                <span><span className="block text-[15px] text-foreground">Add a doctor</span><span className="block text-[12px]">Your family doctor, a specialist you trust</span></span>
              </button>
            )}
          </section>
          <section className="space-y-2.5">
            <h3 className="label px-1">Find a specialist near you</h3>
            <FindDoctor specialties={data?.specialties ?? []} ask={ask} setAsk={setAsk} done={done} fail={fail} />
          </section>
        </div>
      )}

      {tab === "call" && (
        <div className="space-y-3 rise">
          <p className="text-[14px] text-muted-foreground">
            Pathya calls, asks who it's for, the reason in their words, a hospital or area, and good days. Then it finds the clinic
            and shows you a card; it phones the clinic only after your tap.
          </p>
          <div className="flex flex-wrap gap-2">
            {(fam?.members ?? []).filter((m) => m.has_phone).map((m) => (
              <button key={m.key} onClick={() => setCaller(m.key)}
                      className={cn("press px-3 h-9 rounded-full border text-[14px]", caller === m.key ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
                Call {m.key === "me" ? "me" : m.name}
              </button>
            ))}
          </div>
          <Button className="w-full h-12" disabled={intake.isPending} onClick={() => intake.mutate()}>
            {intake.isPending && <Loader2 className="animate-spin" />} Start the call
          </Button>
        </div>
      )}

      {tab === "online" && (
        <div className="space-y-2.5 stagger">
          {(data?.online ?? []).map((o) => (
            <a key={o.name} href={o.url} target="_blank" rel="noreferrer" className="press flex items-center gap-3 rounded-2xl border bg-card p-4">
              <span className="w-11 h-11 rounded-full bg-white/[0.06] border flex items-center justify-center shrink-0"><Video className="w-4 h-4" /></span>
              <span className="flex-1 min-w-0">
                <span className="block text-[15px]">{o.name}</span>
                <span className="block text-[12px] text-muted-foreground mt-0.5">{o.about}</span>
              </span>
              <ArrowUpRight className="w-4 h-4 text-muted-foreground shrink-0" />
            </a>
          ))}
          <p className="text-[12px] text-muted-foreground px-1">
            Their doctors, fees and slots are on their site; you book and pay there. Pathya shares nothing with them.
          </p>
        </div>
      )}
    </div>
  );
}
