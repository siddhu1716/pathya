import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Camera, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Panel } from "@/components/kit";
import { useFamily } from "@/components/FamilyTab";
import { api, BodyReport, ScanResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";
const SLOTS = ["morning", "afternoon", "night"];
const BODY: [keyof BodyReport, string][] = [
  ["weight_kg", "Weight (kg)"], ["height_cm", "Height (cm)"], ["body_fat_pct", "Body fat (%)"], ["skeletal_muscle_kg", "Muscle (kg)"],
  ["fat_mass_kg", "Fat mass (kg)"], ["bmr_kcal", "BMR (kcal)"], ["visceral_fat_level", "Visceral fat level"],
];

/** Camera: a meal is logged straight away; a medicine, prescription or body report waits for you to confirm. */
export function ScanSheet({ open, onClose, who: initial = "me" }: { open: boolean; onClose: () => void; who?: string }) {
  const qc = useQueryClient();
  const { data: fam } = useFamily();
  const [who, setWho] = useState(initial);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [med, setMed] = useState({ name: "", days: "", times: ["morning"] as string[] });
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setWho(initial); setResult(null); } }, [open, initial]);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["family"] }); qc.invalidateQueries({ queryKey: ["state"] }); };
  const fail = (e: Error) => toast.error(e.message);
  const name = fam?.members.find((m) => m.key === who)?.name ?? "";

  const scan = useMutation({
    mutationFn: (photo: File) => api.scan(who, photo),
    onSuccess: (r) => {
      setResult(r);
      if (r.kind === "medicine" && r.medicines[0]) {
        const m = r.medicines[0];
        setMed({ name: [m.name_as_printed, m.strength].filter(Boolean).join(" "), days: "", times: ["morning"] });
      }
      refresh();
    },
    onError: fail,
  });
  const dose = useMutation({ mutationFn: (slot: string) => api.dose(who, slot, "yes", "photo of the strip"),
    onSuccess: () => { toast.success("Marked as taken"); refresh(); }, onError: fail });
  const add = useMutation({ mutationFn: () => api.addMed(who, { name: med.name, dose: "", food: "", times: med.times, days: med.days ? Number(med.days) : null }),
    onSuccess: () => { toast.success(`Added to ${name}'s medicines`); refresh(); onClose(); }, onError: fail });
  const save = useMutation({
    mutationFn: (r: BodyReport) => api.saveMember(who, { ...(r.weight_kg ? { weight_kg: r.weight_kg } : {}), ...(r.height_cm ? { height_cm: r.height_cm } : {}), body: r }),
    onSuccess: () => { toast.success(`Saved to ${name}'s profile; targets updated`); refresh(); onClose(); }, onError: fail,
  });

  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="bg-card border-t max-h-[90dvh]">
        <div className="p-4 pb-8 space-y-3 overflow-y-auto">
          <DrawerHeader className="px-0 text-left">
            <DrawerTitle className="font-medium">Scan a photo</DrawerTitle>
            <DrawerDescription>A plate, a medicine strip, a prescription or a body composition report (InBody).</DrawerDescription>
          </DrawerHeader>
          <div className="flex flex-wrap gap-2">
            {(fam?.members ?? []).map((m) => (
              <button key={m.key} onClick={() => { setWho(m.key); setResult(null); }}
                      className={cn("px-3 h-9 rounded-full border text-[14px]", who === m.key ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
                {m.key === "me" ? "Me" : m.name}
              </button>
            ))}
          </div>
          <input ref={input} type="file" accept="image/*" capture="environment" className="hidden"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) scan.mutate(f); e.target.value = ""; }} />
          <Button className="w-full h-14 text-[16px]" disabled={scan.isPending} onClick={() => input.current?.click()}>
            {scan.isPending ? <><Loader2 className="animate-spin" /> Reading the photo</> : <><Camera /> Take a photo for {who === "me" ? "me" : name}</>}
          </Button>

          {result?.kind === "meal" && (
            <Panel className="p-4 space-y-1">
              <p className="label flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Logged for {who === "me" ? "you" : name}</p>
              <p className="text-[15px]">{result.entry.text}</p>
              <p className="font-mono text-[12px] text-muted-foreground">
                about {result.entry.kcal} kcal · protein {Math.round(result.entry.protein_g)} g · fibre {Math.round(result.entry.fibre_g)} g · added sugar {Math.round(result.entry.sugar_g ?? 0)} g
              </p>
            </Panel>
          )}

          {result?.kind === "medicine" && (
            <Panel className="p-4 space-y-3">
              <p className="label">As printed</p>
              {result.medicines.map((m, i) => (
                <p key={i} className="text-[15px]">{m.name_as_printed} {m.strength ?? ""} {m.unclear && <span className="text-warning text-[12px]">(check: unclear)</span>}</p>
              ))}
              {result.matches.length > 0 && result.due.length > 0 && (
                <div className="space-y-2 border-t pt-3">
                  <p className="text-[13px] text-muted-foreground">Matches {result.matches.join(", ")}. Mark a dose taken:</p>
                  <div className="flex gap-2">
                    {result.due.map((d) => (
                      <Button key={d.slot} variant="outline" className="flex-1 h-10 capitalize" disabled={dose.isPending || d.taken === "yes"}
                              onClick={() => dose.mutate(d.slot)}>{d.taken === "yes" ? `${d.slot} ✓` : d.slot}</Button>
                    ))}
                  </div>
                </div>
              )}
              <div className="space-y-2 border-t pt-3">
                <p className="text-[13px] text-muted-foreground">Or add it to {name}'s medicines, exactly as written on the paper:</p>
                <input className={field} value={med.name} onChange={(e) => setMed({ ...med, name: e.target.value })} />
                <div className="flex gap-2">
                  {SLOTS.map((s) => (
                    <button key={s} onClick={() => setMed({ ...med, times: med.times.includes(s) ? med.times.filter((x) => x !== s) : [...med.times, s] })}
                            className={cn("flex-1 h-9 rounded-full border text-[13px] capitalize", med.times.includes(s) ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
                      {s}
                    </button>
                  ))}
                </div>
                <input className={field} inputMode="numeric" value={med.days} placeholder="Days (as the doctor wrote)" onChange={(e) => setMed({ ...med, days: e.target.value.replace(/\D/g, "") })} />
                <Button className="w-full h-11" disabled={add.isPending || !med.name.trim() || !med.times.length} onClick={() => add.mutate()}>Add medicine</Button>
              </div>
            </Panel>
          )}

          {result?.kind === "prescription" && (
            <Panel className="p-4 text-[15px]">Read. A card is waiting on Home: check it matches the paper. Reminders start only after you confirm.</Panel>
          )}

          {result?.kind === "body_report" && (
            <Panel className="p-4 space-y-3">
              <p className="label">As printed{result.report.date ? ` · ${result.report.date}` : ""}</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {BODY.filter(([k]) => result.report[k] != null).map(([k, label]) => (
                  <p key={k} className="flex justify-between text-[14px]"><span className="text-muted-foreground">{label}</span><span className="font-mono">{result.report[k]}</span></p>
                ))}
              </div>
              <Button className="w-full h-11" disabled={save.isPending} onClick={() => save.mutate(result.report)}>Save to {who === "me" ? "my" : `${name}'s`} profile</Button>
              <p className="text-[12px] text-muted-foreground">Used to work out energy and protein targets. Pathya never judges these numbers.</p>
            </Panel>
          )}

          {result?.kind === "other" && <Panel className="p-4 text-[14px] text-muted-foreground">{result.note || "Couldn't tell what this is."} Try a plate, a strip, a prescription or a report.</Panel>}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
