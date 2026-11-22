import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUp, Camera, Loader2, MessageCircle, PhoneCall, PhoneOutgoing, ShoppingBasket, Stethoscope, UtensilsCrossed } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Panel, Row } from "@/components/kit";
import { DoctorSheet } from "@/components/Doctors";
import { api, AppState, ringIn, setRingIn } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";

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
            className="press rounded-2xl border bg-card/80 p-4 text-left space-y-4 disabled:opacity-40">
      <span className="w-10 h-10 rounded-xl border bg-white/[0.04] flex items-center justify-center"><Icon className="w-[18px] h-[18px]" strokeWidth={1.6} /></span>
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
        <Tile icon={Stethoscope} title="Book a doctor" sub="Your doctors, nearby or online" onClick={() => setSheet("doctor")} />
        <Tile icon={MessageCircle} title="Ask Pathya" sub="Say it in one sentence" onClick={() => setSheet("ask")} />
      </div>
      <Drawer open={sheet !== null} onOpenChange={(o) => !o && setSheet(null)}>
        <DrawerContent className="bg-card border-t max-h-[90dvh]">
          <div className="overflow-y-auto">
            {sheet === "groceries" && <Groceries state={state} done={done} fail={fail} />}
            {sheet === "doctor" && <DoctorSheet state={state} done={done} fail={fail} />}
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
