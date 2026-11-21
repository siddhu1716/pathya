import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, History, Home, Loader2, Package, Users, UtensilsCrossed } from "lucide-react";
import { ScanSheet } from "@/components/Scan";
import { Button } from "@/components/ui/button";
import { ApprovalCard } from "@/components/ApprovalCard";
import { CallHistory } from "@/components/CallHistory";
import { FamilyTab, FamilyToday } from "@/components/FamilyTab";
import { KitchenTab } from "@/components/KitchenTab";
import { Dot, Panel, Pill, Section } from "@/components/kit";
import { LiveCallBanner } from "@/components/LiveCall";
import { OrderTracker } from "@/components/OrderTracker";
import { AskBox, StartActions } from "@/components/StartActions";
import { Timeline } from "@/components/Timeline";
import { UpNext } from "@/components/UpNext";
import { AtHome } from "@/components/HomeStock";
import { api, AppState, connect, key, server } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "home" | "family" | "meals" | "orders" | "more";
const TABS: { id: Tab; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "family", label: "Family", icon: Users },
  { id: "meals", label: "Meals", icon: UtensilsCrossed },
  { id: "orders", label: "Orders", icon: Package },
  { id: "more", label: "More", icon: History },
];

function Lines({ s }: { s: AppState }) {
  const items: [string, boolean][] = [
    ["Swiggy Instamart", s.swiggy],
    ["Zepto backup", s.zepto],
    [s.phone ? `Phone line ${s.phone_number}` : "Phone line (browser calls)", s.phone],
    ["Exotel +91 line", s.exotel],
  ];
  return (
    <Panel className="divide-y">
      {items.map(([label, ok]) => (
        <div key={label} className="flex items-center justify-between px-4 py-3 text-[14px]">
          <span>{label}</span>
          <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            <Dot tone={ok ? "ok" : "muted"} /> {ok ? "on" : "off"}
          </span>
        </div>
      ))}
    </Panel>
  );
}

function AtHomeSection({ s }: { s: AppState }) {
  const { data } = useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen, refetchInterval: 5000 });
  if (!data?.pantry.length) return null;
  return <Section label="At home"><AtHome state={s} compact /></Section>;
}

/** Shown when the server can't be reached: the UI may be hosted (Vercel) and need the tunnel URL and key. */
function Connect({ error }: { error: string }) {
  const [srv, setSrv] = useState(server());
  const [k, setK] = useState(key());
  const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
  return (
    <div className="min-h-[100dvh] max-w-sm mx-auto px-6 flex flex-col justify-center gap-4">
      <h1 className="text-[22px] font-medium tracking-tight">Connect to Pathya</h1>
      <p className="text-[14px] text-muted-foreground">{error}</p>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); connect(srv, k); window.location.reload(); }}>
        <input className={field} value={srv} onChange={(e) => setSrv(e.target.value)} placeholder="Server (blank = this site), https://….trycloudflare.com" />
        <input className={field} value={k} onChange={(e) => setK(e.target.value)} placeholder="Key (from scripts/phone.py)" />
        <Button type="submit" className="w-full h-12">Connect</Button>
      </form>
    </div>
  );
}

const Index = () => {
  const [tab, setTab] = useState<Tab>("home");
  const [scanning, setScanning] = useState(false);
  const { data: s, error } = useQuery({ queryKey: ["state"], queryFn: api.state, refetchInterval: 2000 });

  if (!s) {
    return error ? <Connect error={(error as Error).message} /> : (
      <div className="min-h-[100dvh] flex items-center justify-center text-muted-foreground gap-2"><Loader2 className="animate-spin" /> Loading</div>
    );
  }

  const active = s.orders.filter((o) => !o.delivered && o.store !== "dry run");
  const cards = s.cards;

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="sticky top-0 z-40 bg-background/85 backdrop-blur border-b">
        <div className="max-w-xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-7 h-7 rounded-md bg-primary text-primary-foreground flex items-center justify-center text-[13px] font-semibold">Q</span>
            <span className="text-[15px] font-medium tracking-tight">Pathya</span>
          </div>
          <div className="flex items-center gap-2">
            {s.live.length > 0 && <Pill tone="ok"><Dot tone="ok" pulse /> On a call</Pill>}
            {s.dry_run ? <Pill tone="warn">Dry run</Pill> : <Pill tone="ok">Live orders</Pill>}
            <button aria-label="Scan a photo" onClick={() => setScanning(true)}
                    className="w-9 h-9 rounded-full border flex items-center justify-center active:bg-white/5">
              <Camera className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <ScanSheet open={scanning} onClose={() => setScanning(false)} />
      <main className="max-w-xl mx-auto px-4 pt-5 pb-28 space-y-7">
        {s.live.map((c) => <LiveCallBanner key={c.id} call={c} />)}

        {tab === "home" && (
          <>
            <div className="space-y-1 px-1">
              <h1 className="text-[26px] leading-tight font-medium tracking-tight">Hi {s.user}.</h1>
              <p className="text-[15px] text-muted-foreground">Family nutrition, from a phone call to the plate.</p>
            </div>
            <AskBox />

            {cards.length > 0 && (
              <Section label={`Needs you · ${cards.length}`}>
                <div className="space-y-3">{cards.map((row) => <ApprovalCard key={row.id} row={row} />)}</div>
              </Section>
            )}

            {active.length > 0 && (
              <Section label="On the way">
                <div className="space-y-3">{active.map((o, i) => <OrderTracker key={o.id} order={o} compact={i > 0} />)}</div>
              </Section>
            )}

            {(s.jobs.length > 0 || s.ringing.length > 0) && (
              <Section label="Up next"><UpNext jobs={s.jobs} ringing={s.ringing} people={s.people} /></Section>
            )}

            <Section label="Family today" right={<button className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground" onClick={() => setTab("family")}>All</button>}>
              <FamilyToday onOpen={() => { setTab("family"); window.scrollTo({ top: 0 }); }} />
            </Section>

            <AtHomeSection s={s} />

            <Section label="Start"><StartActions state={s} /></Section>
          </>
        )}

        {tab === "family" && <FamilyTab state={s} />}

        {tab === "meals" && <KitchenTab state={s} />}

        {tab === "orders" && (
          <Section label="Orders">
            {s.orders.length === 0 ? <p className="text-muted-foreground text-center py-10">No orders yet.</p>
              : <div className="space-y-3">{s.orders.map((o) => <OrderTracker key={o.id} order={o} />)}</div>}
          </Section>
        )}

        {tab === "more" && (
          <>
            {s.recent.length > 0 && (
              <Section label="Recently handled">
                <div className="space-y-3">{s.recent.slice(0, 4).map((row) => <ApprovalCard key={row.id} row={row} />)}</div>
              </Section>
            )}
            <Section label="Calls"><CallHistory /></Section>
            <Section label="Lines"><Lines s={s} /></Section>
            <Section label="Activity"><Timeline events={s.timeline} /></Section>
          </>
        )}
      </main>

      <nav className="fixed bottom-0 inset-x-0 z-40 border-t bg-background/90 backdrop-blur pb-[env(safe-area-inset-bottom)]">
        <div className="max-w-xl mx-auto grid grid-cols-5">
          {TABS.map((t) => {
            const badge = t.id === "home" ? cards.length : t.id === "orders" ? active.length : 0;
            return (
              <button key={t.id} onClick={() => { setTab(t.id); window.scrollTo({ top: 0 }); }}
                      className={cn("h-16 flex flex-col items-center justify-center gap-1 relative",
                        tab === t.id ? "text-foreground" : "text-muted-foreground")}>
                <t.icon className="w-5 h-5" strokeWidth={tab === t.id ? 2 : 1.5} />
                <span className="font-mono text-[10px] uppercase tracking-wider">{t.label}</span>
                {badge > 0 && (
                  <span className="absolute top-2.5 left-1/2 ml-2 min-w-4 h-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] leading-4 text-center">{badge}</span>
                )}
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

export default Index;
