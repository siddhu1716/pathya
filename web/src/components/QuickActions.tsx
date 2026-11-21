import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUp, Camera, Loader2, MessageCircle, PhoneCall, PhoneOutgoing, ShoppingBasket, Stethoscope, UtensilsCrossed } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Panel, Row } from "@/components/kit";
import { useFamily } from "@/components/FamilyTab";
import { api, AppState, ringIn, setRingIn } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
const day = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};

export function AskBox({ autoFocus = false, onDone }: { autoFocus?: boolean; onDone?: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const ask = useMutation({
    mutationFn: () => api.ask(text),
    onSuccess: (r) => { setReply(r.reply); setText(""); qc.invalidateQueries({ queryKey: ["state"] }); onDone?.(); },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="space-y-2">
      <form className="flex items-center gap-2 rounded-full border bg-card pl-4 pr-1.5 py-1.5 focus-within:border-white/30"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) ask.mutate(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={ask.isPending} autoFocus={autoFocus}
               placeholder="Amma's BP review this week, we're out of milk…" className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground min-w-0" />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0" disabled={ask.isPending || !text.trim()} aria-label="Send">
          {ask.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
        </Button>
      </form>
      {ask.isPending && <p className="text-[13px] text-muted-foreground px-4">Working on it…</p>}
      {reply && <p className="text-[14px] text-foreground/85 px-4">{reply}</p>}
    </div>
  );
}

type Sheet = null | "groceries" | "doctor" | "ask";

function Tile({ icon: Icon, title, sub, onClick, disabled }: { icon: typeof Camera; title: string; sub: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
            className="rounded-2xl border bg-card p-4 text-left space-y-3 active:bg-white/5 disabled:opacity-40 transition-smooth">
      <span className="w-9 h-9 rounded-full border flex items-center justify-center"><Icon className="w-4 h-4" /></span>
      <span className="block">
        <span className="block text-[15px] leading-tight">{title}</span>
        <span className="block text-[12px] text-muted-foreground mt-0.5 leading-snug">{sub}</span>
      </span>
    </button>
  );
}

/** Home: the six things people do most. */
export function QuickActions({ state, onScan, onMeals }: { state: AppState; onScan: () => void; onMeals: () => void }) {
  const qc = useQueryClient();
  const [sheet, setSheet] = useState<Sheet>(null);
  const done = (msg: string) => { toast.success(msg); setSheet(null); qc.invalidateQueries({ queryKey: ["state"] }); };
  const fail = (e: Error) => toast.error(e.message);
  const toPhone = state.phone && ringIn() === "phone";
  const callMe = useMutation({ mutationFn: api.callMe, onSuccess: () => done(toPhone ? "Calling your phone" : "Ringing below: tap Answer"), onError: fail });
  const stores = state.swiggy || state.zepto;
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <Tile icon={Camera} title="Scan" sub="Plate, medicine, prescription, report" onClick={onScan} />
        <Tile icon={PhoneCall} title="Call me" sub={`Meals, medicines, orders · ${state.language}`} onClick={() => callMe.mutate()} disabled={callMe.isPending} />
        <Tile icon={ShoppingBasket} title="Groceries" sub={stores ? (state.swiggy ? "Instamart cart, one tap" : "Zepto cart, one tap") : "Stores offline"}
              onClick={() => setSheet("groceries")} />
        <Tile icon={UtensilsCrossed} title="Meal plan" sub="A plate for everyone" onClick={onMeals} />
        <Tile icon={Stethoscope} title="Book a doctor" sub="Pathya calls and books" onClick={() => setSheet("doctor")} />
        <Tile icon={MessageCircle} title="Ask Pathya" sub="Say it in one sentence" onClick={() => setSheet("ask")} />
      </div>
      <Drawer open={sheet !== null} onOpenChange={(o) => !o && setSheet(null)}>
        <DrawerContent className="bg-card border-t max-h-[90dvh]">
          <div className="overflow-y-auto">
            {sheet === "groceries" && <Groceries state={state} done={done} fail={fail} />}
            {sheet === "doctor" && <Doctor state={state} done={done} fail={fail} />}
            {sheet === "ask" && (
              <div className="p-4 pb-8 space-y-3">
                <DrawerHeader className="px-0 text-left">
                  <DrawerTitle className="font-medium">Ask Pathya</DrawerTitle>
                  <DrawerDescription>One sentence can start several things. Anything that costs money or books a slot waits for your tap.</DrawerDescription>
                </DrawerHeader>
                <AskBox autoFocus />
              </div>
            )}
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}

function Groceries({ state, done, fail }: { state: AppState; done: (m: string) => void; fail: (e: Error) => void }) {
  const [list, setList] = useState("");
  const cart = useMutation({ mutationFn: () => api.planCart(list), onSuccess: () => { setList(""); done("Cart ready on Home: tap to approve"); }, onError: fail });
  const callList = useMutation({ mutationFn: api.callForList, onSuccess: () => done("Calling for the list"), onError: fail });
  return (
    <div className="p-4 pb-8 space-y-3">
      <DrawerHeader className="px-0 text-left">
        <DrawerTitle className="font-medium">Groceries</DrawerTitle>
        <DrawerDescription>Type it in Telugu, Hindi or English, or let Pathya call for the list. Nothing is ordered before your tap.</DrawerDescription>
      </DrawerHeader>
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (list.trim()) cart.mutate(); }}>
        <textarea className={field} rows={3} value={list} onChange={(e) => setList(e.target.value)} placeholder="2 litres paalu, perugu, ara kilo tomatoes, kottimeera" />
        <Button type="submit" className="w-full h-12" disabled={cart.isPending || !list.trim() || !(state.swiggy || state.zepto)}>
          {cart.isPending && <Loader2 className="animate-spin" />} {cart.isPending ? "Building the cart (about 30 s)" : "Build the cart"}
        </Button>
      </form>
      <Panel className="divide-y overflow-hidden">
        {state.people.map((p) => (
          <Row key={p.key} icon={PhoneOutgoing} title={`Call ${p.name} for the list`} sub={`${p.role === "cook" ? "Cook" : "Family"} · ${p.language}`}
               disabled={callList.isPending} onClick={() => callList.mutate(p.key)} />
        ))}
      </Panel>
    </div>
  );
}

function Doctor({ state, done, fail }: { state: AppState; done: (m: string) => void; fail: (e: Error) => void }) {
  const { data: fam } = useFamily();
  const members = fam?.members ?? [];
  const [mode, setMode] = useState<"plan" | "known">("plan");
  const [caller, setCaller] = useState("me");
  const intake = useMutation({ mutationFn: () => api.intake(caller), onSuccess: () => done("Calling to plan the appointment"), onError: fail });
  const [f, setF] = useState({ patient: "me", place: state.clinics[0]?.key ?? "other", hospital: "", doctor: "", area: "",
    reason: "", from: day(1), to: day(7), part: "morning" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const saved = f.place !== "other";
  const book = useMutation({
    mutationFn: async (): Promise<unknown> => saved
      ? api.book({ patient: f.patient, clinic: f.place, window_start: `${f.from}T00:00`, window_end: `${f.to}T23:59`, part: f.part, reason: f.reason || "consultation" })
      : api.bookRequest({ patient: f.patient, hospital: f.hospital, doctor: f.doctor, area: f.area, reason: f.reason, from_date: f.from, to_date: f.to, part: f.part }),
    onSuccess: () => done(saved ? "Calling the clinic" : "Card on Home: Pathya finds the number, you confirm"),
    onError: fail,
  });
  return (
    <div className="p-4 pb-8 space-y-3">
      <DrawerHeader className="px-0 text-left">
        <DrawerTitle className="font-medium">Book a doctor</DrawerTitle>
        <DrawerDescription>Pathya phones the clinic and books only inside your days and times. It never diagnoses.</DrawerDescription>
      </DrawerHeader>
      <div className="grid grid-cols-2 rounded-full border p-0.5">
        {([["plan", "Pathya plans it"], ["known", "I know where"]] as const).map(([id, label]) => (
          <button key={id} onClick={() => setMode(id)} className={cn("h-9 rounded-full text-[14px]", mode === id ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>{label}</button>
        ))}
      </div>
      {mode === "plan" ? (
        <div className="space-y-3">
          <p className="text-[14px] text-muted-foreground">
            Pathya calls, asks who it's for, the reason in their words, a hospital or area, and good days. Then it finds the clinic
            and shows you a card; it phones the clinic only after your tap.
          </p>
          <div className="flex flex-wrap gap-2">
            {members.filter((m) => m.has_phone).map((m) => (
              <button key={m.key} onClick={() => setCaller(m.key)}
                      className={cn("px-3 h-9 rounded-full border text-[14px]", caller === m.key ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
                Call {m.key === "me" ? "me" : m.name}
              </button>
            ))}
          </div>
          <Button className="w-full h-12" disabled={intake.isPending} onClick={() => intake.mutate()}>
            {intake.isPending && <Loader2 className="animate-spin" />} Start the call
          </Button>
        </div>
      ) : (
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); book.mutate(); }}>
          <div className="grid grid-cols-2 gap-2">
            <select className={field} value={f.patient} onChange={set("patient")}>
              {members.map((m) => <option key={m.key} value={m.key}>{m.key === "me" ? `${m.name} (me)` : m.name}</option>)}
            </select>
            <select className={field} value={f.place} onChange={set("place")}>
              {state.clinics.map((c) => <option key={c.key} value={c.key}>{c.doctor}</option>)}
              <option value="other">Somewhere else…</option>
            </select>
          </div>
          {!saved && (
            <>
              <input className={field} value={f.hospital} onChange={set("hospital")} placeholder="Hospital or clinic (Yashoda, Apollo …)" />
              <div className="grid grid-cols-2 gap-2">
                <input className={field} value={f.doctor} onChange={set("doctor")} placeholder="Doctor (optional)" />
                <input className={field} value={f.area} onChange={set("area")} placeholder="Area (Somajiguda)" />
              </div>
            </>
          )}
          <input className={field} value={f.reason} onChange={set("reason")} placeholder="Reason, in your words (BP review, knee pain)" />
          <div className="grid grid-cols-3 gap-2">
            <input className={field} type="date" value={f.from} onChange={set("from")} />
            <input className={field} type="date" value={f.to} onChange={set("to")} />
            <select className={field} value={f.part} onChange={set("part")}>
              {["morning", "afternoon", "evening", "any"].map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <Button type="submit" className="w-full h-12" disabled={book.isPending || (!saved && !f.hospital.trim() && !f.doctor.trim())}>
            {book.isPending && <Loader2 className="animate-spin" />} {saved ? "Phone the clinic" : "Find it and ask me first"}
          </Button>
        </form>
      )}
    </div>
  );
}

/** More tab: forward your own phone to Pathya (Jio can only forward to an Indian number: the Exotel one). */
export function Forwarding() {
  const { data: f } = useQuery({ queryKey: ["forwarding"], queryFn: api.forwarding });
  if (!f) return null;
  if (!f.number) return <Panel className="px-4 py-3 text-[14px] text-muted-foreground">Set EXOTEL_NUMBER in .env to the Exotel number your phone forwards to.</Panel>;
  const copy = (t: string) => navigator.clipboard?.writeText(t).then(() => toast.success("Copied")).catch(() => undefined);
  return (
    <Panel className="p-4 space-y-3">
      <p className="text-[14px]">When you can't pick up, your phone forwards the call to <span className="font-mono">{f.number}</span> and Pathya answers:
        it says it is your AI assistant, guides the delivery partner to you (or takes a message from anyone else) and tells you here.</p>
      <ol className="text-[13px] space-y-1.5 list-decimal pl-5 text-muted-foreground">
        <li>Exotel: in the call flow for {f.number}, add a <b>Voicebot</b> step with the URL below, then Hangup.</li>
        <li>On your Jio phone, dial a code below (tap to copy). Other networks: {f.other_networks}.</li>
        <li>Test: call your own number from another phone and let it ring.</li>
      </ol>
      {f.voicebot_url && <button onClick={() => copy(f.voicebot_url!)} className="w-full text-left font-mono text-[11px] break-all rounded-xl border p-3">{f.voicebot_url}</button>}
      <div className="divide-y rounded-xl border">
        {f.codes.map((c) => (
          <div key={c.when} className="flex items-center justify-between px-3 py-2 text-[13px]">
            <span>{c.when}</span>
            <span className="flex gap-2">
              <button className="font-mono rounded-full border px-2 py-0.5" onClick={() => copy(c.on)}>{c.on}</button>
              <button className="font-mono text-muted-foreground" onClick={() => copy(c.off)}>{c.off}</button>
            </span>
          </div>
        ))}
      </div>
      <p className="text-[12px] text-muted-foreground">Trial Exotel numbers ask callers for a PIN; a dedicated Exotel number (after KYC) does not.
        Cancel all forwarding with <span className="font-mono">{f.off_all}</span>.</p>
    </Panel>
  );
}

/** More tab: where calls ring, and the Twilio trial note. */
export function CallSettings({ state }: { state: AppState }) {
  const [ring, setRing] = useState(ringIn());
  if (!state.phone) return <Panel className="px-4 py-3 text-[14px] text-muted-foreground">Calls ring in this browser (phone line off).</Panel>;
  return (
    <Panel className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[14px]">Calls ring on</span>
        <div className="flex rounded-full border p-0.5">
          {(["phone", "browser"] as const).map((v) => (
            <button key={v} onClick={() => { setRingIn(v); setRing(v); }}
                    className={cn("px-3 h-7 rounded-full text-[12px]", ring === v ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>
              {v === "phone" ? "Phones" : "This browser"}
            </button>
          ))}
        </div>
      </div>
      <p className="text-[12px] text-muted-foreground">Pathya's calls go out on Twilio ({state.phone_number}). Trial: after the short English message, press any key.
        Jio numbers refuse Twilio calls: put a non-Jio number in Family &gt; You &gt; Phone; until then a refused call rings here instead.</p>
    </Panel>
  );
}
