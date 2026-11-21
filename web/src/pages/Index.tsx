import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, Download, Home, Loader2, Menu, Package, Smartphone, Users, UtensilsCrossed } from "lucide-react";
import { toast } from "sonner";
import { ScanSheet } from "@/components/Scan";
import { Button } from "@/components/ui/button";
import { ApprovalCard } from "@/components/ApprovalCard";
import { CallHistory } from "@/components/CallHistory";
import { FamilyStrip, FamilyTab } from "@/components/FamilyTab";
import { KitchenTab } from "@/components/KitchenTab";
import { Dot, Panel, Pill, Row, Section } from "@/components/kit";
import { LiveCallBanner } from "@/components/LiveCall";
import { OrderTracker } from "@/components/OrderTracker";
import { CallSettings, Forwarding, QuickActions } from "@/components/QuickActions";
import { VoicePanel } from "@/components/VoiceSettings";
import { PhoneIncoming } from "lucide-react";
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
  { id: "more", label: "More", icon: Menu },
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

// The Android app (mobile/) opens this UI in a WebView whose user agent ends with "PathyaAndroid".
const IN_ANDROID_APP = navigator.userAgent.includes("PathyaAndroid");

/** More tab: in a browser, download the Android app and copy the link it needs; in the app, change that link. */
function AndroidApp() {
  if (IN_ANDROID_APP) {
    return (
      <Panel className="overflow-hidden">
        <Row icon={Smartphone} title="Change server link" sub="After a tunnel restart, paste the new Pathya link"
             onClick={() => window.location.assign("https://localhost/?change=1")} />
      </Panel>
    );
  }
  const link = `${server() || window.location.origin}/${key() ? `?key=${encodeURIComponent(key())}` : ""}`;
  return (
    <Panel className="p-4 space-y-3">
      <p className="text-[14px]">Install Pathya on an Android phone: download it, open the file and allow installs from this browser once.
        The app then asks for your Pathya link.</p>
      <a href={`${server()}/pathya.apk`} download="Pathya.apk"
         className="h-12 w-full rounded-xl bg-primary text-primary-foreground text-[15px] flex items-center justify-center gap-2">
        <Download className="w-4 h-4" /> Download Pathya.apk
      </a>
      <Button variant="outline" className="w-full h-11" onClick={() => navigator.clipboard?.writeText(link).then(() => toast.success("Link copied"))
        .catch(() => toast.error("Copy failed"))}>Copy my Pathya link</Button>
    </Panel>
  );
}

function RunningLow({ s }: { s: AppState }) {
  const { data } = useQuery({ queryKey: ["kitchen"], queryFn: api.kitchen, refetchInterval: 5000 });
  if (!data?.pantry.some((i) => i.low)) return null;
  return <Section label="Running low"><AtHome state={s} compact /></Section>;
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
      <p className="text-[14px] text-muted-foreground">Paste your Pathya link (the one with ?key=). Apps added to the Home Screen need it once.</p>
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        let s2 = srv.trim(), k2 = k.trim();
        try {
          const u = new URL(s2);
          k2 = k2 || u.searchParams.get("key") || "";
          s2 = u.origin === window.location.origin ? "" : u.origin;
        } catch { /* not a link: a bare server or blank */ }
        connect(s2, k2);
        window.location.reload();
      }}>
        <input className={field} value={srv} onChange={(e) => setSrv(e.target.value)} placeholder="https://….trycloudflare.com/?key=…" />
        <input className={field} value={k} onChange={(e) => setK(e.target.value)} placeholder="Key (if not in the link)" />
        <Button type="submit" className="w-full h-12">Connect</Button>
      </form>
    </div>
  );
}

const Index = () => {
  const [tab, setTab] = useState<Tab>("home");
  const [member, setMember] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const { data: s, error } = useQuery({ queryKey: ["state"], queryFn: api.state, refetchInterval: 2000 });

  if (!s) {
    return error ? <Connect error={(error as Error).message} /> : (
      <div className="min-h-[100dvh] flex items-center justify-center text-muted-foreground gap-2"><Loader2 className="animate-spin" /> Loading</div>
    );
  }

  const active = s.orders.filter((o) => !o.delivered && o.store !== "dry run");
  const cards = s.cards;
  const go = (t: Tab) => { setTab(t); if (t !== "family") setMember(null); window.scrollTo({ top: 0 }); };
  const hour = new Date().getHours();
  const hello = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="sticky top-0 z-40 bg-background/85 backdrop-blur border-b">
        <div className="max-w-xl mx-auto px-4 h-14 flex items-center justify-between">
          <button className="flex items-center gap-2.5" onClick={() => go("home")}>
            <span className="w-7 h-7 rounded-md bg-primary text-primary-foreground flex items-center justify-center text-[13px] font-semibold">P</span>
            <span className="text-[15px] font-medium tracking-tight">Pathya</span>
          </button>
          <div className="flex items-center gap-2">
            {s.live.length > 0 && <Pill tone="ok"><Dot tone="ok" pulse /> On a call</Pill>}
            {s.dry_run && <Pill tone="warn">Dry run</Pill>}
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
        {s.ringing.map((j) => (
          <a key={j.id} href={`/call/${j.id}`} className="flex items-center gap-3 rounded-2xl border border-success/40 bg-success/5 px-4 py-3.5">
            <PhoneIncoming className="w-5 h-5 text-success voice-pulse" />
            <span className="flex-1 text-[15px]">Pathya is calling {j.person === "me" ? "you" : s.people.find((p) => p.key === j.person)?.name ?? j.person}</span>
            <span className="rounded-full bg-success text-success-foreground px-3 h-8 leading-8 text-[13px]">Answer</span>
          </a>
        ))}

        {tab === "home" && (
          <>
            <div className="space-y-1 px-1">
              <h1 className="text-[26px] leading-tight font-medium tracking-tight">{hello}, {s.user}.</h1>
              <p className="text-[15px] text-muted-foreground">The right food and care for everyone at home.</p>
            </div>

            <Section label="Family" right={<button className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground" onClick={() => go("family")}>All</button>}>
              <FamilyStrip onOpen={(k) => { setMember(k); go("family"); }} />
            </Section>

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

            <Section label="Do something"><QuickActions state={s} onScan={() => setScanning(true)} onMeals={() => go("meals")} /></Section>

            {s.jobs.length > 0 && (
              <Section label="Up next"><UpNext jobs={s.jobs} ringing={[]} people={s.people} /></Section>
            )}

            <RunningLow s={s} />
          </>
        )}

        {tab === "family" && <FamilyTab pick={member} setPick={setMember} />}

        {tab === "meals" && <KitchenTab state={s} />}

        {tab === "orders" && (
          <Section label="Orders">
            {s.orders.length === 0 ? <p className="text-muted-foreground text-center py-10">No orders yet.</p>
              : <div className="space-y-3">{s.orders.map((o) => <OrderTracker key={o.id} order={o} />)}</div>}
          </Section>
        )}

        {tab === "more" && (
          <>
            <Section label="Calls"><CallSettings state={s} /></Section>
            <Section label="Pathya's voice"><VoicePanel /></Section>
            <Section label="Answer my calls"><Forwarding /></Section>
            <Section label="Call history"><CallHistory /></Section>
            {s.recent.length > 0 && (
              <Section label="Recently handled">
                <div className="space-y-3">{s.recent.slice(0, 4).map((row) => <ApprovalCard key={row.id} row={row} />)}</div>
              </Section>
            )}
            <Section label="Connections"><Lines s={s} /></Section>
            {(IN_ANDROID_APP || s.android_apk) && <Section label="Android app"><AndroidApp /></Section>}
            <Section label="Activity"><Timeline events={s.timeline} /></Section>
          </>
        )}
      </main>

      <nav className="fixed bottom-0 inset-x-0 z-40 border-t bg-background/90 backdrop-blur pb-[env(safe-area-inset-bottom)]">
        <div className="max-w-xl mx-auto grid grid-cols-5">
          {TABS.map((t) => {
            const badge = t.id === "home" ? cards.length : t.id === "orders" ? active.length : 0;
            return (
              <button key={t.id} onClick={() => go(t.id)}
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
