import { Panel } from "@/components/kit";
import { clock, TimelineEvent } from "@/lib/api";

export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) return <p className="text-muted-foreground text-center py-10">Nothing yet.</p>;
  return (
    <Panel className="divide-y">
      {events.map((e, i) => (
        <div key={`${e.ts}-${i}`} className="px-4 py-2.5 flex gap-3">
          <span className="font-mono text-[11px] text-muted-foreground shrink-0 pt-0.5 tabular-nums">{clock(e.ts)}</span>
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{e.expert}</p>
            <p className="text-[13px] break-words">{e.what}</p>
          </div>
        </div>
      ))}
    </Panel>
  );
}
