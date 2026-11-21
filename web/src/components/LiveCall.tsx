import { useEffect, useState } from "react";
import { PhoneCall, PhoneIncoming, Wrench } from "lucide-react";
import { LiveCall as Live, Line } from "@/lib/api";
import { cn } from "@/lib/utils";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function Bubbles({ lines, dark = false }: { lines: Line[]; dark?: boolean }) {
  return (
    <div className="space-y-1.5">
      {lines.map((l, i) => (
        <div
          key={i}
          className={cn(
            "rounded-2xl px-3 py-1.5 text-sm max-w-[88%] w-fit whitespace-pre-line",
            l.role === "ai" && (dark ? "bg-primary/80 text-white" : "bg-primary/10 text-foreground"),
            l.role === "them" && (dark ? "bg-slate-600 text-white ml-auto" : "bg-muted ml-auto"),
            l.role === "tool" && "mx-auto max-w-full border border-warning/50 bg-warning/10 text-xs",
          )}
        >
          {l.role === "tool" && <Wrench className="inline w-3 h-3 mr-1 -mt-0.5" />}
          {l.text}
        </div>
      ))}
    </div>
  );
}

export function LiveCallBanner({ call }: { call: Live }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const Icon = call.direction === "inbound" ? PhoneIncoming : PhoneCall;
  return (
    <div className="rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 text-white p-4 shadow-xl fade-in">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-hero flex items-center justify-center voice-pulse">
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <p className="font-semibold leading-tight">
              {call.direction === "inbound" ? `Incoming: ${call.who}` : `Calling ${call.who}`}
            </p>
            <p className="text-xs text-slate-300">{call.expert} · AI on the line</p>
          </div>
        </div>
        <span className="font-mono text-sm bg-white/10 rounded-full px-3 py-1">
          <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2 animate-pulse" />
          {mmss(Math.max(0, Math.round(now - call.started)))}
        </span>
      </div>
      {call.lines.length ? (
        <div className="max-h-56 overflow-y-auto flex flex-col-reverse">
          <div><Bubbles lines={call.lines} dark /></div>
        </div>
      ) : <p className="text-sm text-slate-400">Connecting…</p>}
    </div>
  );
}
