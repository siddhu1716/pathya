import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlarmClock, ArrowUp, CalendarClock, FileImage, HeartPulse, Keyboard, Loader2, PhoneCall, PhoneOutgoing } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Panel, Row } from "@/components/kit";
import { api, AppState, ringIn, setRingIn } from "@/lib/api";
import { cn } from "@/lib/utils";

const day = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";

export function AskBox() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const ask = useMutation({
    mutationFn: () => api.ask(text),
    onSuccess: (r) => {
      setReply(r.reply);
      setText("");
      qc.invalidateQueries({ queryKey: ["state"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="space-y-2">
      <form className="flex items-center gap-2 rounded-full border bg-card pl-4 pr-1.5 py-1.5 focus-within:border-white/30"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) ask.mutate(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={ask.isPending}
               placeholder="Ask QuickPick anything…" className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground min-w-0" />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0" disabled={ask.isPending || !text.trim()} aria-label="Send">
          {ask.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
        </Button>
      </form>
      {ask.isPending && <p className="text-[13px] text-muted-foreground px-4">Working on it…</p>}
      {reply && <p className="text-[14px] text-foreground/85 px-4">{reply}</p>}
    </div>
  );
}

type Sheet = null | "list" | "book" | "rx";

export function StartActions({ state }: { state: AppState }) {
  const qc = useQueryClient();
  const [sheet, setSheet] = useState<Sheet>(null);
  const [ring, setRing] = useState(ringIn());
  const done = (msg: string) => {
    toast.success(msg);
    setSheet(null);
    qc.invalidateQueries({ queryKey: ["state"] });
  };
  const fail = (e: Error) => toast.error(e.message);
  const family = state.people.filter((p) => p.role !== "cook");

  const callList = useMutation({ mutationFn: api.callForList, onSuccess: () => done("Calling now"), onError: fail });
  const checkin = useMutation({ mutationFn: (p: string) => api.checkin(p), onSuccess: () => done("Calling now"), onError: fail });
  const toPhone = state.phone && ring === "phone";
  const callMe = useMutation({ mutationFn: api.callMe, onSuccess: () => done(toPhone ? "Calling your phone" : "Ringing here: tap Answer"), onError: fail });
  const daily = useMutation({
    mutationFn: () => api.daily(state.daily_call == null ? 20 : null),
    onSuccess: (r) => done(r.hour == null ? "Daily check-in off" : "QuickPick will call you every day at 8 PM"), onError: fail,
  });

  const [list, setList] = useState("");
  const cart = useMutation({ mutationFn: () => api.planCart(list), onSuccess: () => { setList(""); done("Cart ready below"); }, onError: fail });

  const [book, setBook] = useState({
    patient: family[0]?.key ?? state.people[0]?.key ?? "", clinic: state.clinics[0]?.key ?? "",
    from: day(1), to: day(5), part: "morning", reason: "BP review",
  });
  const booking = useMutation({
    mutationFn: () => api.book({ patient: book.patient, clinic: book.clinic, window_start: `${book.from}T00:00`,
      window_end: `${book.to}T23:59`, part: book.part, reason: book.reason }),
    onSuccess: () => done("Calling the clinic"), onError: fail,
  });

  const [rxFor, setRxFor] = useState(book.patient);
  const [photo, setPhoto] = useState<File | null>(null);
  const rx = useMutation({ mutationFn: () => api.prescription(rxFor, photo as File),
    onSuccess: () => { setPhoto(null); done("Read. Check the card and confirm."); }, onError: fail });

  return (
    <>
      {state.phone && (
        <div className="flex items-center justify-between px-1 pb-3">
          <span className="text-[13px] text-muted-foreground">Calls ring on</span>
          <div className="flex rounded-full border p-0.5">
            {(["phone", "browser"] as const).map((v) => (
              <button key={v} onClick={() => { setRingIn(v); setRing(v); }}
                      className={cn("px-3 h-7 rounded-full text-[12px]", ring === v ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>
                {v === "phone" ? "Phones" : "This browser"}
              </button>
            ))}
          </div>
        </div>
      )}
      {state.phone && ring === "phone" && (
        <p className="px-1 pb-3 text-[12px] text-muted-foreground">
          Twilio trial: after the short English message, press any key so QuickPick starts talking. Jio numbers can't receive these calls.
        </p>
      )}
      <Panel className="divide-y overflow-hidden">
        <Row icon={PhoneCall} title="Call me now" sub={`Medicines, meals, what's running low · ${state.language}`}
             disabled={callMe.isPending} onClick={() => callMe.mutate()} />
        <Row icon={AlarmClock} title="Daily check-in call" sub="Every day at 8 PM" disabled={daily.isPending}
             onClick={() => daily.mutate()}
             right={<span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{state.daily_call == null ? "off" : `${state.daily_call}:00`}</span>} />
        {state.people.map((p) => (
          <Row key={p.key} icon={PhoneOutgoing} title={`Call ${p.name} for the list`}
               sub={`Kitchen · ${p.language}`} disabled={callList.isPending}
               onClick={() => callList.mutate(p.key)} />
        ))}
        <Row icon={Keyboard} title="Type a list" sub={state.swiggy ? "Instamart cart, Zepto for what's missing" : state.zepto ? "Instamart offline: Zepto cart" : "Stores offline"}
             disabled={!(state.swiggy || state.zepto)} onClick={() => setSheet("list")} />
        <Row icon={CalendarClock} title="Book a doctor" sub="Phones the clinic, books only inside your window" onClick={() => setSheet("book")} />
        {family.map((p) => (
          <Row key={`c-${p.key}`} icon={HeartPulse} title={`Check in with ${p.name}`} sub="Health · questions for the doctor"
               disabled={checkin.isPending} onClick={() => checkin.mutate(p.key)} />
        ))}
        <Row icon={FileImage} title="Read a prescription" sub="Nothing is scheduled until you confirm" onClick={() => setSheet("rx")} />
      </Panel>

      <Drawer open={sheet !== null} onOpenChange={(o) => !o && setSheet(null)}>
        <DrawerContent className="bg-card border-t">
          {sheet === "list" && (
            <form className="p-4 pb-8 space-y-3" onSubmit={(e) => { e.preventDefault(); if (list.trim()) cart.mutate(); }}>
              <DrawerHeader className="px-0 text-left">
                <DrawerTitle className="font-medium">Type a list</DrawerTitle>
                <DrawerDescription>Telugu, Hindi or English. Quantities help.</DrawerDescription>
              </DrawerHeader>
              <textarea className={field} rows={3} value={list} onChange={(e) => setList(e.target.value)}
                        placeholder="2 litres paalu, perugu, ara kilo tomatoes, kottimeera" autoFocus />
              <Button type="submit" className="w-full h-12" disabled={cart.isPending || !list.trim()}>
                {cart.isPending && <Loader2 className="animate-spin" />} {cart.isPending ? "Building the cart (about 30 s)" : "Build the cart"}
              </Button>
            </form>
          )}
          {sheet === "book" && (
            <form className="p-4 pb-8 space-y-3" onSubmit={(e) => { e.preventDefault(); booking.mutate(); }}>
              <DrawerHeader className="px-0 text-left">
                <DrawerTitle className="font-medium">Book a doctor</DrawerTitle>
                <DrawerDescription>QuickPick phones the clinic. Slots outside this window are refused by code.</DrawerDescription>
              </DrawerHeader>
              <div className="grid grid-cols-2 gap-2">
                <select className={field} value={book.patient} onChange={(e) => setBook({ ...book, patient: e.target.value })}>
                  {state.people.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
                </select>
                <select className={field} value={book.clinic} onChange={(e) => setBook({ ...book, clinic: e.target.value })}>
                  {state.clinics.map((c) => <option key={c.key} value={c.key}>{c.doctor}</option>)}
                </select>
                <input className={field} type="date" value={book.from} onChange={(e) => setBook({ ...book, from: e.target.value })} />
                <input className={field} type="date" value={book.to} onChange={(e) => setBook({ ...book, to: e.target.value })} />
                <select className={field} value={book.part} onChange={(e) => setBook({ ...book, part: e.target.value })}>
                  {["morning", "afternoon", "evening", "any"].map((p) => <option key={p}>{p}</option>)}
                </select>
                <input className={field} value={book.reason} placeholder="Reason" onChange={(e) => setBook({ ...book, reason: e.target.value })} />
              </div>
              <Button type="submit" className="w-full h-12" disabled={booking.isPending || !book.reason}>Phone the clinic</Button>
            </form>
          )}
          {sheet === "rx" && (
            <form className="p-4 pb-8 space-y-3" onSubmit={(e) => { e.preventDefault(); if (photo) rx.mutate(); }}>
              <DrawerHeader className="px-0 text-left">
                <DrawerTitle className="font-medium">Read a prescription</DrawerTitle>
                <DrawerDescription>QuickPick copies it exactly; reminders start only after you confirm.</DrawerDescription>
              </DrawerHeader>
              <select className={field} value={rxFor} onChange={(e) => setRxFor(e.target.value)}>
                <option value="me">{state.user} (me)</option>
                {state.people.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
              </select>
              <input className={field} type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              <Button type="submit" className="w-full h-12" disabled={!photo || rx.isPending}>
                {rx.isPending && <Loader2 className="animate-spin" />} Read it
              </Button>
            </form>
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}
