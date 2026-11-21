import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Clock, PhoneCall, PhoneIncoming, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, Job, Person } from "@/lib/api";

const KIND: Record<string, string> = {
  list: "Grocery list call",
  book: "Clinic booking call",
  checkin: "Check-in call",
  followup: "Follow-up",
};

const when = (ts: number) =>
  new Date(ts * 1000).toLocaleString("en-IN", { weekday: "short", hour: "2-digit", minute: "2-digit" });

function who(job: Job, people: Person[]) {
  return people.find((p) => p.key === job.person)?.name ?? job.person;
}

export function JobsPanel({ jobs, ringing, people }: { jobs: Job[]; ringing: Job[]; people: Person[] }) {
  const qc = useQueryClient();
  const runNow = useMutation({
    mutationFn: (id: string) => api.runNow(id),
    onSuccess: () => {
      toast.success("Starting now");
      qc.invalidateQueries({ queryKey: ["state"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <PhoneCall className="w-5 h-5" /> Calls and reminders
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {ringing.map((j) => (
          <div key={j.id} className="flex items-center justify-between gap-2 rounded-md border-2 border-primary/50 bg-primary/5 px-3 py-2">
            <div>
              <p className="font-medium flex items-center gap-1">
                <PhoneIncoming className="w-4 h-4 text-primary voice-pulse" /> Ringing: {KIND[j.kind] ?? j.kind}
              </p>
              <p className="text-muted-foreground">{who(j, people)}</p>
            </div>
            <Button size="sm" asChild>
              <a href={`/call/${j.id}`} target="_blank" rel="noreferrer">Answer</a>
            </Button>
          </div>
        ))}
        {jobs.length === 0 && ringing.length === 0 && <p className="text-muted-foreground">Nothing scheduled.</p>}
        {jobs.map((j) => (
          <div key={j.id} className="flex items-center justify-between gap-2 border-b last:border-0 pb-2">
            <div>
              <p className="font-medium">{KIND[j.kind] ?? j.kind} · {who(j, people)}</p>
              <p className="text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" /> {when(j.run_at)}
                {j.payload?.purpose && <span className="truncate max-w-[16rem]"> · {j.payload.purpose}</span>}
              </p>
            </div>
            <Button size="sm" variant="outline" disabled={runNow.isPending} onClick={() => runNow.mutate(j.id)}>
              <Play className="w-3 h-3 mr-1" /> Run now
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
