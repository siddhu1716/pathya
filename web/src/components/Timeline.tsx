import { History } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TimelineEvent } from "@/lib/api";

const time = (ts: number) =>
  new Date(ts * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <History className="w-5 h-5" /> Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-1 text-xs font-mono">
          {events.map((e, i) => (
            <li key={`${e.ts}-${i}`} className="flex gap-2">
              <span className="text-muted-foreground shrink-0">{time(e.ts)}</span>
              <span className="text-primary shrink-0 w-20 truncate">{e.expert}</span>
              <span className="break-words min-w-0">{e.what}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
