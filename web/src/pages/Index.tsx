import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, Download, Home, Loader2, Menu, Package, Smartphone, Users, UtensilsCrossed } from "lucide-react";
import { toast } from "sonner";
import { ScanSheet } from "@/components/Scan";
import { Button } from "@/components/ui/button";
import { ApprovalCard } from "@/components/ApprovalCard";
import { CallCartReview } from "@/components/CallCartReview";
import { CallHistory } from "@/components/CallHistory";
import { FamilyStrip, FamilyTab } from "@/components/FamilyTab";
import { KitchenTab } from "@/components/KitchenTab";
import { Wordmark } from "@/components/Wordmark";
import { CallLanguages } from "@/components/CallLanguages";
import { Dot, Panel, Pill, Row, Section } from "@/components/kit";
import { LiveCallBanner } from "@/components/LiveCall";
import { OrderTracker } from "@/components/OrderTracker";
import { CallMe, CallSettings, Forwarding, QuickActions } from "@/components/QuickActions";
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
  const shareable = key() && !key().startsWith("pathya_");          // a phone sign-in session is never shared
  const link = `${server() || window.location.origin}/${shareable ? `?key=${encodeURIComponent(key())}` : ""}`;
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

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";

/** Shown when the app can't open: sign in with your phone number (a code by SMS), or paste your Pathya link. */
function Connect({ error }: { error: string }) {
  const { data: auth } = useQuery({ queryKey: ["auth-status"], queryFn: api.authStatus, retry: false });
  const [mode, setMode] = useState<"phone" | "link">("phone");
  const phoneOk = !!auth?.phone_sign_in;
  return (
    <main className="entry-screen">
      <div className="entry-card">
        <div className="entry-brand"><Wordmark /><img src="/thali.webp" alt="" width="144" height="144" /></div>
        {phoneOk && mode === "phone" ? <PhoneSignIn onLink={() => setMode("link")} /> : (
          <>
            <h1 className="text-[22px] font-medium tracking-tight">Connect to Pathya</h1>
            {!/key needed/i.test(error) && <p className="text-[14px] text-muted-foreground">{error}</p>}
            <LinkForm />
            {phoneOk && <button className="text-[14px] text-muted-foreground underline underline-offset-4" onClick={() => setMode("phone")}>Sign in with your phone number</button>}
          </>
        )}
      </div>
    </main>
  );
}

function PhoneSignIn({ onLink }: { onLink: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const fail = (e: Error) => toast.error(e.message);
  const [how, setHow] = useState<"sms" | "call">("sms");
  const start = useMutation({
    mutationFn: (channel: "sms" | "call" = "sms") => api.signInStart(phone, channel),
    onSuccess: (r) => { setSentTo(r.to); setHow(r.channel === "call" ? "call" : "sms"); }, onError: fail,
  });
  const check = useMutation({
    mutationFn: () => api.signInCheck(phone, code),
    onSuccess: (r) => { connect(server(), r.token); window.location.reload(); },
    onError: fail,
  });
  return (
    <>
      <h1 className="text-[22px] font-medium tracking-tight">Sign in to Pathya</h1>
      <p className="text-[14px] text-muted-foreground">
        {sentTo ? (how === "call" ? `Pathya's number is calling ${sentTo} to read out a code.` : `We texted a code to ${sentTo}.`)
          : "Your phone number, as it is in your family's Pathya. We'll text you a code."}
      </p>
      {!sentTo ? (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (phone.trim()) start.mutate("sms"); }}>
          <input className={field} aria-label="Phone number" type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98480 22338" autoFocus />
          <Button type="submit" className="w-full h-12" disabled={start.isPending || phone.replace(/\D/g, "").length < 10}>
            {start.isPending && <Loader2 className="animate-spin" />} Send code
          </Button>
        </form>
      ) : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (code.trim()) check.mutate(); }}>
          <input className={cn(field, "font-mono tracking-[0.3em] text-center text-[20px]")} aria-label="Verification code" inputMode="numeric" autoComplete="one-time-code"
                 value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="••••••" autoFocus />
          <Button type="submit" className="w-full h-12" disabled={check.isPending || code.length < 4}>
            {check.isPending && <Loader2 className="animate-spin" />} Sign in
          </Button>
          <div className="flex justify-between gap-3 text-[13px] text-muted-foreground">
            <button type="button" disabled={start.isPending} onClick={() => { setCode(""); start.mutate("sms"); }}>Text a new code</button>
            <button type="button" disabled={start.isPending} onClick={() => { setCode(""); start.mutate("call"); }}>Call me with the code</button>
          </div>
        </form>
      )}
      <button className="text-[13px] text-muted-foreground underline underline-offset-4" onClick={onLink}>I have a Pathya link instead</button>
    </>
  );
}

function LinkForm() {
  const [srv, setSrv] = useState(server());
  const [k, setK] = useState(key().startsWith("pathya_") ? "" : key());
  return (
    <>
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
        <input className={field} aria-label="Pathya link" value={srv} onChange={(e) => setSrv(e.target.value)} placeholder="https://….trycloudflare.com/?key=…" />
        <input className={field} aria-label="Access key" value={k} onChange={(e) => setK(e.target.value)} placeholder="Key (if not in the link)" />
        <Button type="submit" className="w-full h-12">Connect</Button>
      </form>
    </>
  );
}

/** More tab: who is signed in on this phone. */
function Account() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  if (!me || me.via === "open") return null;
  const out = async () => {
    await api.signOut().catch(() => undefined);
    connect(server(), "");
    window.location.reload();
  };
  return (
    <Panel className="flex items-center justify-between gap-3 px-4 py-3">
      <span className="min-w-0">
        <span className="block text-[15px]">{me.name}</span>
        <span className="block text-[12px] text-muted-foreground">{me.via === "phone" ? `Signed in with …${me.phone_end}` : "Opened with the Pathya link"}</span>
      </span>
      <Button variant="outline" size="sm" className="shrink-0" onClick={out}>{me.via === "phone" ? "Sign out" : "Forget link"}</Button>
    </Panel>
  );
}

/** The header steps out of the way while you scroll down and comes back as soon as you scroll up. */
function useHideOnScroll() {
  const [hidden, setHidden] = useState(false);
  const last = useRef(0);
  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      if (Math.abs(y - last.current) > 6) setHidden(y > 72 && y > last.current);
      last.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return hidden;
}

/** First paint: the shape of Home, breathing, instead of a spinner. */
function HomeSkeleton() {
  return (
    <div className="min-h-[100dvh] max-w-xl mx-auto px-4 pt-20 space-y-7" aria-label="Loading">
      <div className="space-y-3"><div className="skeleton h-10 w-3/4" /><div className="skeleton h-4 w-1/2" /></div>
      <div className="flex gap-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-32 min-w-0 flex-1" />)}</div>
      <div className="grid grid-cols-2 gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-28" />)}</div>
    </div>
  );
}

const Index = () => {
  const [tab, setTab] = useState<Tab>("home");
  const hideHeader = useHideOnScroll();
  const [member, setMember] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const { data: s, error } = useQuery({
    queryKey: ["state"], queryFn: api.state,
    refetchInterval: (q) => (/key needed/i.test(q.state.error?.message ?? "") ? false : 2000),   // signed out: wait
  });

  if (!s) {
    return error ? <Connect error={(error as Error).message} /> : <HomeSkeleton />;
  }

  const active = s.orders.filter((o) => !o.delivered && o.store !== "dry run");
  const cards = s.cards;
  const go = (t: Tab) => { setTab(t); if (t !== "family") setMember(null); window.scrollTo({ top: 0 }); };
  const hour = new Date().getHours();
  const hello = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className={cn("sticky top-0 z-40 glass border-b hairline transition-transform duration-300 ease-out", hideHeader && "-translate-y-full")}>
        <div className="shell-width mx-auto px-4 min-h-16 flex items-center justify-between">
          <button className="min-h-11 flex items-center" aria-label="Pathya home" onClick={() => go("home")}>
            <Wordmark />
          </button>
          <div className="flex items-center gap-2">
            {s.live.length > 0 && <Pill tone="ok"><Dot tone="ok" pulse /> On a call</Pill>}
            {s.dry_run && <Pill tone="warn">Dry run</Pill>}
            <button aria-label="Scan a photo" onClick={() => setScanning(true)}
                    className="w-11 h-11 rounded-full border bg-card flex items-center justify-center active:bg-white/5">
              <Camera className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>
      <ScanSheet open={scanning} onClose={() => setScanning(false)} />

      <main key={tab} className={cn("page-content mx-auto px-4 pt-5 pb-28 space-y-7", tab === "home" ? "shell-width" : "max-w-2xl")}>
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
            {!scanning && <CallCartReview cards={cards} />}
            <div className="home-hero">
              <div className="hero-copy">
                <p className="hero-date">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p>
                <h1 className="display">{hello}, <span>{s.user}.</span></h1>
                <p className="hero-description">{cards.length
                  ? `${cards.length} ${cards.length === 1 ? "card is" : "cards are"} waiting for your review.`
                  : "Check in about meals, medicines or groceries by phone."}</p>
                <div className="hero-controls">
                  <CallMe state={s} />
                  <CallLanguages key={s.language} openingLanguage={s.language} />
                </div>
              </div>
              <img className="hero-thali" alt="" src="/thali.webp" width="720" height="720" />
            </div>

            {s.preparing_call_cart && (
              <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Preparing the grocery cart from your call…
              </p>
            )}
            {cards.length > 0 && (
              <Section label={`For your review · ${cards.length}`}>
                <div className="space-y-3">{cards.map((row) => <ApprovalCard key={row.id} row={row} />)}</div>
              </Section>
            )}

            {active.length > 0 && (
              <Section label="On the way">
                <div className="space-y-3">{active.map((o, i) => <OrderTracker key={o.id} order={o} compact={i > 0} />)}</div>
              </Section>
            )}

            <div className="home-sections">
              <Section label="Your family" right={<button className="section-link" onClick={() => go("family")}>View family →</button>}>
                <FamilyStrip onOpen={(k) => { setMember(k); go("family"); }} />
              </Section>
              <Section label="Quick actions"><QuickActions state={s} onScan={() => setScanning(true)} onMeals={() => go("meals")} /></Section>
            </div>

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
            <Section label="Account"><Account /></Section>
            <Section label="Calls"><CallSettings state={s} /></Section>
            <Section label="Pathya's voice"><VoicePanel /></Section>
            <Section label="Answer my calls"><Forwarding /></Section>
            <Section label="Call history"><CallHistory onReview={() => go("home")} /></Section>
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

      <nav aria-label="Main navigation" className="fixed bottom-0 inset-x-0 z-40 border-t hairline glass pb-[env(safe-area-inset-bottom)]">
        <div className="max-w-xl mx-auto grid grid-cols-5">
          {TABS.map((t) => {
            const badge = t.id === "home" ? cards.length : t.id === "orders" ? active.length : 0;
            return (
              <button key={t.id} aria-current={tab === t.id ? "page" : undefined} onClick={() => go(t.id)}
                      className={cn("press h-16 flex flex-col items-center justify-center gap-1 relative",
                        tab === t.id ? "text-primary" : "text-muted-foreground")}>
                <span className={cn("absolute top-0 h-[2px] w-7 rounded-full bg-primary transition-transform duration-300 ease-out",
                  tab === t.id ? "scale-x-100" : "scale-x-0")} />
                <t.icon className="w-5 h-5" strokeWidth={tab === t.id ? 2 : 1.5} />
                <span className="text-[12px] font-medium">{t.label}</span>
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
