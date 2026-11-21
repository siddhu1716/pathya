import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { PhoneCall, PhoneIncoming, PhoneOff, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { Dot, Panel } from "@/components/kit";
import { LiveCall as Live, Line } from "@/lib/api";
import { cn } from "@/lib/utils";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function Bubbles({ lines }: { lines: Line[] }) {
  return (
    <div className="space-y-2">
      {lines.map((l, i) =>
        l.role === "tool" ? (
          <p key={i} className="font-mono text-[11px] text-warning/90 flex gap-1.5 items-start">
            <Wrench className="w-3 h-3 mt-0.5 shrink-0" /> {l.text}
          </p>
        ) : (
          <div key={i} className={cn("rounded-2xl px-3.5 py-2 text-[14px] leading-snug max-w-[86%] w-fit whitespace-pre-line",
            l.role === "ai" ? "bg-white/[0.06]" : "bg-white text-black ml-auto")}>
            {l.text}
          </div>
        ),
      )}
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
  const end = useMutation({ mutationFn: () => api.hangup(call.id), onSuccess: () => toast.success("Hanging up"), onError: (e: Error) => toast.error(e.message) });
  return (
    <Panel className="p-4 space-y-3 fade-in border-success/30">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-2"><Dot tone="ok" pulse /> Live · {call.expert}</span>
        <span className="font-mono text-[12px] tabular-nums text-muted-foreground">{mmss(Math.max(0, Math.round(now - call.started)))}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-full border flex items-center justify-center"><Icon className="w-4 h-4" /></span>
        <p className="flex-1 text-[15px]">{call.direction === "inbound" ? `${call.who} is on the line` : `Talking with ${call.who}`}</p>
        {call.phone && (
          <button aria-label="End call" disabled={end.isPending} onClick={() => end.mutate()}
                  className="h-9 px-3 rounded-full bg-destructive text-white text-[13px] flex items-center gap-1.5 disabled:opacity-50">
            <PhoneOff className="w-4 h-4" /> End
          </button>
        )}
      </div>
      {call.lines.length ? (
        <div className="max-h-64 overflow-y-auto flex flex-col-reverse">
          <div><Bubbles lines={call.lines} /></div>
        </div>
      ) : <p className="text-[13px] text-muted-foreground">Connecting…</p>}
    </Panel>
  );
}
