import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AudioLines, Check, Loader2, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Panel, Row } from "@/components/kit";
import { useFamily } from "@/components/FamilyTab";
import { api, VoicePrompt, VoiceSettings, VoiceView } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCENTS = { indian: "Indian", neutral: "Neutral" } as const;
const PACES = { slow: "Slow", normal: "Normal", fast: "Fast" } as const;
const PATIENCE = { quick: "Quick", normal: "Normal", patient: "Patient" } as const;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const waits = (p: VoiceSettings["patience"]) => (p === "patient" ? "waits longer" : p === "quick" ? "answers quickly" : "normal waiting");

function Seg<T extends string>({ value, options, onChange }: { value: T; options: Record<T, string>; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-full border p-0.5">
      {(Object.keys(options) as T[]).map((v) => (
        <button key={v} type="button" onClick={() => onChange(v)}
                className={cn("flex-1 h-8 rounded-full text-[13px]", value === v ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>
          {options[v]}
        </button>
      ))}
    </div>
  );
}

function Toggle({ on, onChange, title, sub }: { on: boolean; onChange: (v: boolean) => void; title: string; sub: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)} className="w-full flex items-start gap-3 text-left">
      <span className="flex-1">
        <span className="block text-[14px]">{title}</span>
        <span className="block text-[12px] text-muted-foreground mt-0.5">{sub}</span>
      </span>
      <span className={cn("mt-0.5 w-10 h-6 rounded-full border relative shrink-0", on ? "bg-primary border-primary" : "bg-white/[0.03]")}>
        <span className={cn("absolute top-[2px] w-[18px] h-[18px] rounded-full transition-all",
                            on ? "left-[18px] bg-primary-foreground" : "left-[2px] bg-muted-foreground")} />
      </span>
    </button>
  );
}

/** More tab: how Pathya sounds on every call. */
export function VoicePanel() {
  const { data } = useQuery({ queryKey: ["voice"], queryFn: api.voice });
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const s = data.settings;
  return (
    <>
      <Panel className="overflow-hidden">
        <Row icon={AudioLines} title={`${cap(s.voice)} · ${ACCENTS[s.accent]} accent`}
             sub={`${PACES[s.pace]} pace · ${waits(s.patience)}${s.notes ? " · your instructions" : ""}`} onClick={() => setOpen(true)} />
      </Panel>
      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent className="bg-card border-t max-h-[92dvh]">
          <div className="overflow-y-auto">{open && <VoiceSheet view={data} onDone={() => setOpen(false)} />}</div>
        </DrawerContent>
      </Drawer>
    </>
  );
}

function VoiceSheet({ view, onDone }: { view: VoiceView; onDone: () => void }) {
  const qc = useQueryClient();
  const [s, setS] = useState<VoiceSettings>(view.settings);
  const set = <K extends keyof VoiceSettings>(k: K, v: VoiceSettings[K]) => setS((p) => ({ ...p, [k]: v }));
  const [playing, setPlaying] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const node = useRef<AudioBufferSourceNode | null>(null);
  useEffect(() => () => { node.current?.stop(); void ctx.current?.close(); }, []);

  // Web Audio: the context is created inside the tap, so phones let it play once the sample arrives.
  const play = async (voice: string) => {
    node.current?.stop();
    node.current = null;
    if (playing === voice) { setPlaying(null); return; }
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const c = ctx.current ?? (ctx.current = new Ctx());
    void c.resume();
    setLoading(voice);
    try {
      const buf = await c.decodeAudioData(await (await api.voicePreview({ voice, accent: s.accent, pace: s.pace })).arrayBuffer());
      const n = c.createBufferSource();
      n.buffer = buf;
      n.connect(c.destination);
      n.onended = () => { if (node.current === n) { node.current = null; setPlaying(null); } };
      n.start();
      node.current = n;
      setPlaying(voice);
    } catch (e) {
      toast.error(`Could not play the sample: ${(e as Error).message}`);
      setPlaying(null);
    } finally {
      setLoading(null);
    }
  };

  const save = useMutation({
    mutationFn: () => api.saveVoice(s),
    onSuccess: (v) => { qc.setQueryData(["voice"], v); qc.invalidateQueries({ queryKey: ["voice-prompt"] }); toast.success("Saved. The next call uses it."); onDone(); },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-4 pb-8 space-y-5">
      <DrawerHeader className="px-0 text-left">
        <DrawerTitle className="font-medium">Pathya's voice</DrawerTitle>
        <DrawerDescription>How Pathya sounds on every call: in the app, on the phone and on forwarded calls. Tap ▶ to hear a voice.</DrawerDescription>
      </DrawerHeader>

      <div className="space-y-2">
        <h3 className="label px-1">Voice</h3>
        <div className="rounded-2xl border divide-y">
          {view.voices.map((v) => (
            <div key={v.id} className="flex items-center">
              <button type="button" onClick={() => set("voice", v.id)} className="flex-1 flex items-center gap-3 px-4 py-3 text-left min-w-0">
                <span className={cn("w-5 h-5 rounded-full border flex items-center justify-center shrink-0", s.voice === v.id && "bg-primary border-primary")}>
                  {s.voice === v.id && <Check className="w-3 h-3 text-primary-foreground" />}
                </span>
                <span className="min-w-0">
                  <span className="block text-[15px] leading-tight">{cap(v.id)}</span>
                  <span className="block text-[12px] text-muted-foreground truncate">{v.about}</span>
                </span>
              </button>
              <button type="button" aria-label={`Hear ${v.id}`} onClick={() => play(v.id)}
                      className="w-11 h-11 mr-2 rounded-full flex items-center justify-center text-muted-foreground active:bg-white/5">
                {loading === v.id ? <Loader2 className="w-4 h-4 animate-spin" /> : playing === v.id ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="label px-1">Accent</h3>
        <Seg value={s.accent} options={ACCENTS} onChange={(v) => set("accent", v)} />
        <p className="text-[12px] text-muted-foreground px-1">Indian: native Telugu and Hindi, and Indian English. OpenAI has no Indian voice as such; the accent comes from Pathya's instructions.</p>
      </div>

      <div className="space-y-2">
        <h3 className="label px-1">Pace</h3>
        <Seg value={s.pace} options={PACES} onChange={(v) => set("pace", v)} />
      </div>

      <div className="space-y-2">
        <h3 className="label px-1">When someone pauses</h3>
        <Seg value={s.patience} options={PATIENCE} onChange={(v) => set("patience", v)} />
        <p className="text-[12px] text-muted-foreground px-1">How long Pathya waits before it answers. Patient suits elders and anyone who thinks while speaking.</p>
      </div>

      <div className="space-y-4">
        <Toggle on={s.interrupt} onChange={(v) => set("interrupt", v)} title="Stop talking when someone speaks"
                sub="On: they can interrupt Pathya. Off: Pathya finishes its sentence first (better on noisy lines)." />
        <Toggle on={s.elders_slow} onChange={(v) => set("elders_slow", v)} title="Slower and more patient with 60+"
                sub="Slow pace and patient waiting on every call with a member aged 60 or over." />
      </div>

      <div className="space-y-2">
        <h3 className="label px-1">Your instructions to Pathya</h3>
        <textarea rows={4} maxLength={view.notes_max} value={s.notes} onChange={(e) => set("notes", e.target.value)}
                  placeholder="Call my mother Amma garu. Use respectful Telugu (meeru). Keep it short; she gets tired after 5 minutes."
                  className="w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30" />
        <p className="text-[12px] text-muted-foreground px-1 flex justify-between gap-3">
          <span>How to speak, not what to decide. Pathya's rules always come first: it says it is an AI, never gives medical advice and never orders or books without your tap.</span>
          <span className="font-mono shrink-0">{s.notes.length}/{view.notes_max}</span>
        </p>
      </div>

      <div className="space-y-2">
        <h3 className="label px-1">When a call ends</h3>
        <p className="text-[13px] text-muted-foreground px-1">{view.call_ends}</p>
      </div>

      <Button className="w-full h-12" disabled={save.isPending} onClick={() => save.mutate()}>
        {save.isPending && <Loader2 className="animate-spin" />} Save
      </Button>

      <PromptViewer />
    </div>
  );
}

/** Read-only: the exact prompt Pathya gets on a check-in call with one person (saved settings). */
function PromptViewer() {
  const { data: fam } = useFamily();
  const [who, setWho] = useState<string | null>(null);
  const { data, isFetching, error } = useQuery<VoicePrompt>({ queryKey: ["voice-prompt", who], queryFn: () => api.voicePrompt(who!), enabled: !!who });
  return (
    <div className="space-y-2">
      <h3 className="label px-1">See the full prompt</h3>
      <div className="flex flex-wrap gap-2">
        {(fam?.members ?? []).map((m) => (
          <button key={m.key} type="button" onClick={() => setWho(who === m.key ? null : m.key)}
                  className={cn("h-8 px-3 rounded-full border text-[13px]", who === m.key ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground")}>
            {m.name}
          </button>
        ))}
      </div>
      {who && isFetching && <p className="text-[13px] text-muted-foreground flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Building it</p>}
      {who && error && <p className="text-[13px] text-destructive">{(error as Error).message}</p>}
      {who && data && !isFetching && (
        <div className="space-y-2">
          <p className="text-[12px] text-muted-foreground px-1">
            Check-in call with {data.who}: {cap(data.voice.voice)}, {PACES[data.voice.pace].toLowerCase()} pace, {waits(data.voice.patience)},
            up to {data.max_minutes} min. Tools: {data.tools.join(", ")}.
          </p>
          <pre className="max-h-80 overflow-auto rounded-xl border bg-white/[0.02] p-3 text-[11px] leading-relaxed whitespace-pre-wrap font-mono">{data.prompt}</pre>
        </div>
      )}
    </div>
  );
}
