import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Bot, CheckCircle2, Loader2, Phone, PhoneOff, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Line = { role: "ai" | "them" | "tool"; text: string };
type Info = { id: string; kind: string; expert: string; who: string; user: string; done: boolean };
type Phase = "ringing" | "connecting" | "live" | "ended" | "error";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const [info, setInfo] = useState<Info | null>(null);
  const [phase, setPhase] = useState<Phase>("ringing");
  const [error, setError] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [seconds, setSeconds] = useState(0);
  const pc = useRef<RTCPeerConnection | null>(null);
  const dc = useRef<RTCDataChannel | null>(null);
  const mic = useRef<MediaStream | null>(null);
  const transcript = useRef<Line[]>([]);
  const ending = useRef(false);
  const endAfterGoodbye = useRef(false);
  const limit = useRef(5 * 60);

  const add = (l: Line) => {
    transcript.current = [...transcript.current, l];
    setLines(transcript.current);
  };

  useEffect(() => {
    fetch(`/api/calls/${id}`)
      .then(async (r) => (r.ok ? r.json() : Promise.reject(new Error((await r.json()).detail))))
      .then((i: Info) => {
        setInfo(i);
        if (i.done) setPhase("ended");
      })
      .catch((e: Error) => {
        setError(e.message);
        setPhase("error");
      });
  }, [id]);

  useEffect(() => {
    if (phase !== "live") return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  useEffect(() => {
    if (phase === "live" && seconds >= limit.current) hangUp();   // every call has a time limit
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds, phase]);

  const send = (event: object) => dc.current?.readyState === "open" && dc.current.send(JSON.stringify(event));

  async function hangUp() {
    if (ending.current) return;
    ending.current = true;
    mic.current?.getTracks().forEach((t) => t.stop());
    dc.current?.close();
    pc.current?.close();
    setPhase("ended");
    await fetch(`/api/calls/${id}/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: transcript.current }),
    }).catch(() => undefined);
  }

  async function onEvent(e: MessageEvent) {
    const ev = JSON.parse(e.data);
    switch (ev.type) {
      case "conversation.item.input_audio_transcription.completed":
        if (ev.transcript?.trim()) add({ role: "them", text: ev.transcript.trim() });
        break;
      case "response.output_audio_transcript.done":
        if (ev.transcript?.trim()) add({ role: "ai", text: ev.transcript.trim() });
        break;
      case "response.function_call_arguments.done": {
        const r = await fetch(`/api/calls/${id}/tool`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: ev.name, arguments: ev.arguments }),
        });
        const out = r.ok ? await r.json() : { output: "Tool failed on the server.", end: false };
        add({ role: "tool", text: `${ev.name}: ${out.output}` });
        send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: ev.call_id, output: out.output } });
        send({ type: "response.create" });
        if (out.end) {
          endAfterGoodbye.current = true;
          setTimeout(hangUp, 10000);                      // fallback if the goodbye never finishes
        }
        break;
      }
      case "response.done": {
        // Hang up 3 s after the goodbye: the first response after end_call that is speech, not another tool call.
        const calledTool = (ev.response?.output ?? []).some((o: { type: string }) => o.type === "function_call");
        if (endAfterGoodbye.current && !calledTool) setTimeout(hangUp, 3000);
        break;
      }
      case "error":
        add({ role: "tool", text: `Error: ${ev.error?.message ?? "unknown"}` });
        break;
    }
  }

  async function answer() {
    setPhase("connecting");
    try {
      const conn = new RTCPeerConnection();
      pc.current = conn;
      const audio = new Audio();
      audio.autoplay = true;
      conn.ontrack = (e) => (audio.srcObject = e.streams[0]);
      mic.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      conn.addTrack(mic.current.getTracks()[0]);
      const channel = conn.createDataChannel("oai-events");
      dc.current = channel;
      channel.onmessage = onEvent;
      channel.onopen = async () => {
        const g = await fetch(`/api/calls/${id}/greeting`).then((r) => r.json());
        limit.current = (g.max_minutes ?? 5) * 60;
        setPhase("live");
        send({
          type: "response.create",
          response: { instructions: `The person just answered. Your first sentence must be exactly: "${g.greeting}" Then continue as instructed.` },
        });
      };
      const offer = await conn.createOffer();
      await conn.setLocalDescription(offer);
      const r = await fetch(`/api/calls/${id}/sdp`, { method: "POST", headers: { "Content-Type": "application/sdp" }, body: offer.sdp });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `Call failed (${r.status})`);
      await conn.setRemoteDescription({ type: "answer", sdp: await r.text() });
    } catch (e) {
      mic.current?.getTracks().forEach((t) => t.stop());
      pc.current?.close();
      setError((e as Error).message);
      setPhase("error");
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-white flex flex-col items-center px-4 py-8">
      <div className="text-center space-y-1 mt-6">
        <div className={cn("mx-auto w-20 h-20 rounded-full bg-gradient-hero flex items-center justify-center", phase === "ringing" && "voice-pulse")}>
          <Bot className="w-10 h-10" />
        </div>
        <p className="text-2xl font-semibold mt-4">QuickPick (AI)</p>
        <p className="text-slate-300">{info ? `${info.expert} · calling ${info.who} for ${info.user}` : "…"}</p>
        <p className="text-slate-400 text-sm">
          {phase === "ringing" && "Incoming call"}
          {phase === "connecting" && "Connecting…"}
          {phase === "live" && mmss(seconds)}
          {phase === "ended" && "Call ended"}
        </p>
      </div>

      <div className="flex-1 w-full max-w-md my-6 space-y-2 overflow-y-auto">
        {lines.map((l, i) => (
          <div key={i} className={cn("rounded-2xl px-4 py-2 text-sm max-w-[85%]",
            l.role === "ai" && "bg-primary/80",
            l.role === "them" && "bg-slate-600 ml-auto",
            l.role === "tool" && "bg-transparent border border-amber-400/50 text-amber-200 text-xs mx-auto max-w-full")}>
            {l.role === "tool" && <Wrench className="inline w-3 h-3 mr-1" />}
            {l.text}
          </div>
        ))}
        {phase === "ended" && (
          <p className="text-center text-emerald-300 flex items-center justify-center gap-2 pt-4">
            <CheckCircle2 className="w-5 h-5" /> Done. The card appears on the QuickPick home screen.
          </p>
        )}
        {phase === "error" && <p className="text-center text-red-300">{error}</p>}
      </div>

      <div className="pb-6">
        {phase === "ringing" && info && (
          <Button size="voice" className="bg-emerald-500 hover:bg-emerald-600" onClick={answer} aria-label="Answer">
            <Phone className="w-8 h-8" />
          </Button>
        )}
        {phase === "connecting" && <Loader2 className="w-10 h-10 animate-spin" />}
        {phase === "live" && (
          <Button size="voice" variant="destructive" onClick={hangUp} aria-label="Hang up">
            <PhoneOff className="w-8 h-8" />
          </Button>
        )}
      </div>
    </div>
  );
}
