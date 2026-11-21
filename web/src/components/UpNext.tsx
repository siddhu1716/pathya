import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Clock, PhoneIncoming } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/kit";
import { api, Job, Person } from "@/lib/api";

const KIND: Record<string, string> = {
  list: "Grocery list call", menu: "Menu call", book: "Clinic booking call", checkin: "Check-in call",
  followup: "Follow-up", home: "Check-in call", doorstep: "Incoming call", meds: "Medicine reminder", intake: "Doctor booking call",
};

const when = (ts: number) => new Date(ts * 1000).toLocaleString("en-IN", { weekday: "short", hour: "2-digit", minute: "2-digit" });

const who = (job: Job, people: Person[]) =>
  job.person === "me" ? "you" : people.find((p) => p.key === job.person)?.name ?? job.person;

export function UpNext({ jobs, ringing, people }: { jobs: Job[]; ringing: Job[]; people: Person[] }) {
  const qc = useQueryClient();
  const runNow = useMutation({
    mutationFn: (id: string) => api.runNow(id),
    onSuccess: () => { toast.success("Starting now"); qc.invalidateQueries({ queryKey: ["state"] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  if (!jobs.length && !ringing.length) return null;
  return (
    <Panel className="divide-y overflow-hidden">
      {ringing.map((j) => (
        <div key={j.id} className="flex items-center gap-3 px-4 py-3.5">
          <span className="w-9 h-9 rounded-full border border-success/40 flex items-center justify-center"><PhoneIncoming className="w-4 h-4 text-success voice-pulse" /></span>
          <div className="flex-1 min-w-0">
            <p className="text-[15px]">{KIND[j.kind] ?? j.kind}</p>
            <p className="text-[13px] text-muted-foreground">Ringing in the browser · {who(j, people)}</p>
          </div>
          <Button size="sm" asChild><a href={`/call/${j.id}`}>Answer</a></Button>
        </div>
      ))}
      {jobs.map((j) => (
        <div key={j.id} className="flex items-center gap-3 px-4 py-3.5">
          <span className="w-9 h-9 rounded-full border flex items-center justify-center"><Clock className="w-4 h-4" /></span>
          <div className="flex-1 min-w-0">
            <p className="text-[15px]">{KIND[j.kind] ?? j.kind} · {who(j, people)}</p>
            <p className="text-[13px] text-muted-foreground truncate">{when(j.run_at)}{j.kind === "home" ? (j.payload?.daily_hour != null ? " · every evening" : "") : j.kind === "meds" ? ` · ${j.payload?.slot}` : j.payload?.purpose ? ` · ${j.payload.purpose}` : ""}</p>
          </div>
          <Button size="sm" variant="outline" disabled={runNow.isPending} onClick={() => runNow.mutate(j.id)}>Run now</Button>
        </div>
      ))}
    </Panel>
  );
}
