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
