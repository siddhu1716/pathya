import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function Section({ label, right, children, className }: {
  label: string; right?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between px-1">
        <h2 className="label">{label}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("rounded-2xl border bg-card", className)}>{children}</div>;
}

export function Row({ icon: Icon, title, sub, right, onClick, disabled }: {
  icon: React.ComponentType<{ className?: string }>; title: string; sub?: string; right?: React.ReactNode;
  onClick?: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
            className="w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-white/5 disabled:opacity-40 transition-smooth">
      <span className="w-9 h-9 rounded-full border flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4" />
      </span>
      <span className="flex-1 min-w-0">
        <span className="block text-[15px] leading-tight">{title}</span>
        {sub && <span className="block text-[13px] text-muted-foreground truncate mt-0.5">{sub}</span>}
      </span>
      {right ?? <ChevronRight className="w-4 h-4 text-muted-foreground" />}
    </button>
  );
}

/** A progress ring: the health score (or any 0-100). */
export function Ring({ value, size = 44, stroke = 4, className }: { value: number | null; size?: number; stroke?: number; className?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const color = value == null ? "stroke-white/20" : pct >= 80 ? "stroke-success" : pct >= 60 ? "stroke-foreground" : "stroke-warning";
  return (
    <span className={cn("relative inline-flex items-center justify-center shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} className="stroke-white/10 fill-none" />
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} strokeLinecap="round" className={cn("fill-none transition-all duration-700", color)}
                strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
      </svg>
      <span className="absolute font-mono tabular-nums" style={{ fontSize: size * 0.3 }}>{value ?? "–"}</span>
    </span>
  );
}

/** A goal bar with the percentage reached. limit=true: a maximum (added sugar), amber once it is passed. */
export function Meter({ label, v, goal, unit, limit = false }: { label: string; v: number; goal: number; unit: string; limit?: boolean }) {
  const pct = goal ? Math.round((v / goal) * 100) : 0;
  const tone = limit ? (pct > 100 ? "bg-warning" : "bg-foreground/70") : pct >= 90 ? "bg-success" : pct >= 50 ? "bg-foreground/80" : "bg-foreground/40";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-[13px]">
        <span>{label}</span>
        <span className="font-mono tabular-nums text-muted-foreground text-[12px]">
          {Math.round(v)} / {Math.round(goal)} {unit}{limit ? " max" : ""} <span className={cn("ml-1", !limit && pct >= 90 ? "text-success" : limit && pct > 100 ? "text-warning" : "text-foreground")}>{pct}%</span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-700", tone)} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
}

export function Dot({ tone = "muted", pulse = false }: { tone?: "ok" | "warn" | "bad" | "muted"; pulse?: boolean }) {
  return (
    <span className={cn("inline-block w-1.5 h-1.5 rounded-full", pulse && "voice-pulse", {
      ok: "bg-success", warn: "bg-warning", bad: "bg-destructive", muted: "bg-muted-foreground/50",
    }[tone])} />
  );
}

export function Pill({ children, tone = "muted", className }: {
  children: React.ReactNode; tone?: "ok" | "warn" | "bad" | "muted" | "solid"; className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider", {
      ok: "border-success/30 text-success",
      warn: "border-warning/40 text-warning",
      bad: "border-destructive/40 text-destructive",
      muted: "text-muted-foreground",
      solid: "bg-primary text-primary-foreground border-transparent",
    }[tone], className)}>
      {children}
    </span>
  );
}
