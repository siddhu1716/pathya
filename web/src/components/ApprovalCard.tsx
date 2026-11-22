import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpRight, CalendarPlus, ExternalLink, Loader2, Share2, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dot, Panel, Photo, Pill } from "@/components/kit";
import { api, CardRow } from "@/lib/api";
import { cn } from "@/lib/utils";

const KIND: Record<string, string> = {
  order: "Order", booking: "Booking", hold: "Held slot", brief: "Doctor brief", meds: "Prescription",
  alert: "Urgent", info: "Update", followup: "Follow-up", plan: "Meal plan", bookreq: "Doctor's appointment",
  clinic: "Clinic found", relay: "Medicines", pharmacies: "Pharmacies", pharmacy_answer: "Pharmacy",
};
const EXPERT: Record<string, string> = { home: "Family", health: "Health", kitchen: "Kitchen", doorstep: "Doorstep", caller: "Calls" };
const SAFETY: Record<string, [string, "ok" | "warn" | "muted"]> = {
  passed: ["Safety passed", "ok"], blocked: ["Safety held", "warn"], unchecked: ["Safety off", "muted"],
};

function storeOf(c: CardRow["card"]) {
  if (c.payload?.store === "zepto") return "Zepto";
  if (c.kind === "order") return "Instamart";
  return EXPERT[c.expert] ?? c.expert[0].toUpperCase() + c.expert.slice(1);
}

export function ApprovalCard({ row }: { row: CardRow }) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const c = row.card;
  const urgent = c.kind === "alert";
  const waiting = row.status === "waiting";

  const tap = useMutation({
    mutationFn: (choice: string) => api.tap(row.id, choice),
    onSuccess: (r) => {
      if (r.result?.open) window.open(r.result.open, "_blank", "noopener");
      if (r.result?.pay_url) window.open(r.result.pay_url, "_blank", "noopener");
      qc.invalidateQueries({ queryKey: ["state"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const reject = useMutation({
    mutationFn: () => api.reject(row.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["state"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const busy = tap.isPending || reject.isPending;
  const [primary, ...rest] = c.choices;

  return (
    <Panel className={cn("p-4 space-y-4 fade-in", urgent && "border-destructive/60")}>
      <div className="flex items-center justify-between gap-2">
        <span className="label flex items-center gap-2">
          <Dot tone={urgent ? "bad" : waiting ? "warn" : row.status === "failed" ? "bad" : "ok"} pulse={urgent} />
          {c.kind === "brief" && c.expert === "kitchen" ? "Nutrition brief" : KIND[c.kind] ?? c.kind} · {storeOf(c)}
        </span>
        {c.kind === "brief" && c.payload?.safety && SAFETY[c.payload.safety] && (
          <Pill tone={SAFETY[c.payload.safety][1]}>{SAFETY[c.payload.safety][0]}</Pill>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex gap-3">
          {c.payload?.photo && <Photo id={c.payload.photo} alt="Prescription photo" className="w-16 h-16" />}
          <h3 className="text-lg font-medium leading-snug">{c.title}</h3>
        </div>
        {c.lines.filter(Boolean).length > 0 && (
          <ul className="space-y-1 text-[14px] text-foreground/85">
            {c.lines.filter(Boolean).map((l, i) => <li key={i} className="whitespace-pre-line">{l}</li>)}
          </ul>
        )}
      </div>

      {(c.total || c.address) && (
        <div className="rounded-xl bg-white/[0.03] border px-3 py-2.5 space-y-1.5">
          {c.total && (
            <div className="flex items-baseline justify-between">
              <span className="label">To pay</span>
              <span className="text-xl font-medium tabular-nums">{c.total}</span>
            </div>
          )}
          {c.address && <p className="text-[13px] text-muted-foreground">Your order will be delivered to: {c.address}</p>}
        </div>
      )}

      {c.warnings.length > 0 && (
        <ul className="space-y-1.5">
          {c.warnings.map((w, i) => (
            <li key={i} className="text-[13px] text-warning/90 border-l-2 border-warning/50 pl-3 whitespace-pre-line">{w}</li>
          ))}
        </ul>
      )}

      {c.payload?.photo && c.payload?.share_text && <SharePhoto id={c.payload.photo} text={c.payload.share_text} />}
      {c.kind === "brief" && c.payload?.consult && c.payload?.text && (
        <ConsultLink name={c.payload.consult.name} url={c.payload.consult.url} text={c.payload.text} />
      )}

      {waiting ? (
        <div className="space-y-3">
          {c.question && <p className="text-[15px]">{c.question}</p>}
          {primary && (
            <Button className="w-full h-12 text-[15px]" variant={urgent ? "destructive" : "default"} disabled={busy}
                    onClick={() => { setPicked(primary.id); tap.mutate(primary.id); }}>
              {tap.isPending && picked === primary.id && <Loader2 className="animate-spin" />}
              {primary.label}
            </Button>
          )}
          {rest.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
              {rest.map((ch) => (
                <Button key={ch.id} variant="outline" size="sm" className="shrink-0" disabled={busy}
                        onClick={() => { setPicked(ch.id); tap.mutate(ch.id); }}>
                  {tap.isPending && picked === ch.id && <Loader2 className="animate-spin" />}
                  {ch.label}
                </Button>
              ))}
            </div>
          )}
          {!urgent && (
            <button className="w-full text-center text-[13px] text-muted-foreground py-1" disabled={busy} onClick={() => reject.mutate()}>
              Not now
            </button>
          )}
          {c.choices.length === 0 && <p className="text-[13px] text-muted-foreground">Nothing to approve on this card.</p>}
        </div>
      ) : (
        <Outcome row={row} />
      )}
    </Panel>
  );
}

/** Share a brief with a doctor in an online consultation: the brief is copied (their site can't receive it from us),
 * then their consultation page opens; paste it into the chat with the doctor. A real link, so no pop-up blocker. */
function ConsultLink({ name, url, text }: { name: string; url: string; text: string }) {
  const copy = () => {
    navigator.clipboard?.writeText(text)
      .then(() => toast.success(`Brief copied. Paste it into the chat with your ${name} doctor.`))
      .catch(() => toast.message(`Opening ${name}. Copy the brief above to share it with the doctor.`));
  };
  return (
    <a href={url} target="_blank" rel="noreferrer" onClick={copy}
       className="press w-full h-11 rounded-xl border flex items-center justify-center gap-2 text-[14px]">
      <Stethoscope className="w-4 h-4" /> Share with a doctor on {name} <ArrowUpRight className="w-3.5 h-3.5 text-muted-foreground" />
    </a>
  );
}

/** Send the prescription photo itself (WhatsApp links can't attach it): the phone's share sheet, else open the photo. */
function SharePhoto({ id, text }: { id: string; text: string }) {
  const [busy, setBusy] = useState(false);
  const share = async () => {
    setBusy(true);
    try {
      const blob = await (await fetch(api.photoUrl(id))).blob();
      const file = new File([blob], "prescription.jpg", { type: blob.type || "image/jpeg" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], text });
      } else {
        await navigator.clipboard?.writeText(text).catch(() => undefined);
        window.open(api.photoUrl(id), "_blank", "noopener");
        toast.message("Photo opened and the list copied: save the photo and attach it in WhatsApp.");
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") toast.error("Could not share the photo.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="outline" className="w-full h-11" disabled={busy} onClick={share}>
      {busy ? <Loader2 className="animate-spin" /> : <Share2 />} Share the prescription photo
    </Button>
  );
}

function Outcome({ row }: { row: CardRow }) {
  const r = row.result;
  if (row.status === "rejected") return <p className="text-[13px] text-muted-foreground">Skipped. Nothing was done.</p>;
  if (row.status === "running") {
    return (
      <div className="space-y-2 text-[14px]">
        <p className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> {r?.pay_url ? "Waiting for your UPI payment" : "Working"}</p>
        {r?.pay_url && (
          <a className="inline-flex items-center gap-1 underline underline-offset-4" href={r.pay_url} target="_blank" rel="noreferrer">
            Open the payment page <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    );
  }
  const failed = row.status === "failed" || r?.ok === false;
  return (
    <div className="space-y-2 text-[14px] border-t pt-3">
      <p className="label flex items-center gap-2">
        <Dot tone={failed ? "bad" : "ok"} /> {failed ? "Not done" : `Done${row.choice ? ` · ${row.choice.replace("UPI:", "UPI ")}` : ""}`}
      </p>
      {r?.message && <p className="whitespace-pre-line">{r.message}</p>}
      {r?.error && <p className="whitespace-pre-line text-destructive">{r.error}</p>}
      {r?.eta && Object.entries(r.eta).map(([id, eta]) => <p key={id} className="text-muted-foreground">Arriving in {eta}</p>)}
      {r?.jobs && r.jobs.length > 0 && <p className="text-muted-foreground">{r.jobs.length} call(s) scheduled.</p>}
      {row.card.payload?.ics && (
        <a className="inline-flex items-center gap-1.5 underline underline-offset-4" href={api.icsUrl(row.id)}>
          <CalendarPlus className="w-4 h-4" /> Add to calendar
        </a>
      )}
      {r?.cancel && <p className="text-[12px] text-muted-foreground">{r.cancel}</p>}
    </div>
  );
}
