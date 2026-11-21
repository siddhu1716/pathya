import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2, Phone, PhoneOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dot } from "@/components/kit";
import { Bubbles } from "@/components/LiveCall";
import { api, apiFetch } from "@/lib/api";

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
    if (id) api.line(id, l).then((r) => {                 // the home screen shows the call live
      if (r.note) send({ type: "conversation.item.create", item: { type: "message", role: "system", content: [{ type: "input_text", text: r.note }] } });
    }).catch(() => undefined);
  };

  useEffect(() => {
    apiFetch(`/api/calls/${id}`)
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

  async function decline() {
    await api.decline(id!).catch(() => undefined);
    window.location.href = "/";
  }

  async function hangUp() {
    if (ending.current) return;
    ending.current = true;
    mic.current?.getTracks().forEach((t) => t.stop());
    dc.current?.close();
    pc.current?.close();
    setPhase("ended");
    await apiFetch(`/api/calls/${id}/end`, {
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
        const r = await apiFetch(`/api/calls/${id}/tool`, {
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
        const g = await apiFetch(`/api/calls/${id}/greeting`).then((r) => r.json());
        limit.current = (g.max_minutes ?? 5) * 60;
        setPhase("live");
        // A system message, not response.create instructions: those would replace the session prompt for this turn.
        send({
          type: "conversation.item.create",
          item: { type: "message", role: "system", content: [{ type: "input_text",
            text: `The person just answered. Your first sentence must be exactly: "${g.greeting}" Then, in the same turn, continue as your instructions say (say why you are calling, or ask how you can help).` }] },
        });
        send({ type: "response.create" });
      };
      const offer = await conn.createOffer();
      await conn.setLocalDescription(offer);
      const r = await apiFetch(`/api/calls/${id}/sdp`, { method: "POST", headers: { "Content-Type": "application/sdp" }, body: offer.sdp });
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
    <div className="min-h-[100dvh] bg-background flex flex-col px-4 pt-10 pb-[max(2rem,env(safe-area-inset-bottom))] max-w-xl mx-auto">
      <div className="text-center space-y-3">
        <span className="label flex items-center justify-center gap-2">
          <Dot tone={phase === "live" ? "ok" : phase === "error" ? "bad" : "muted"} pulse={phase === "live" || phase === "ringing"} />
          {phase === "ringing" && "Incoming call"}
          {phase === "connecting" && "Connecting"}
          {phase === "live" && `Live · ${mmss(seconds)}`}
          {phase === "ended" && "Call ended"}
          {phase === "error" && "Could not connect"}
        </span>
        <p className="text-[28px] font-medium tracking-tight">Pathya</p>
        <p className="text-[14px] text-muted-foreground">{info ? `${info.expert} · talking with ${info.who} for ${info.user}` : " "}</p>
      </div>

      <div className="flex-1 w-full my-8 overflow-y-auto">
        <Bubbles lines={lines} />
        {phase === "ended" && (
          <p className="text-center text-[14px] text-muted-foreground pt-6">Done. The result appears on the Pathya home screen.</p>
        )}
        {phase === "error" && <p className="text-center text-[14px] text-destructive">{error}</p>}
      </div>

      <div className="flex justify-center gap-16">
        {phase === "ringing" && info && (
          <>
            <div className="flex flex-col items-center gap-2">
              <Button className="h-16 w-16 rounded-full bg-destructive text-white hover:bg-destructive/90" onClick={decline} aria-label="Decline">
                <PhoneOff className="!size-6" />
              </Button>
              <span className="text-[12px] text-muted-foreground">Decline</span>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Button className="h-16 w-16 rounded-full bg-success text-black hover:bg-success/90" onClick={answer} aria-label="Answer">
                <Phone className="!size-6" />
              </Button>
              <span className="text-[12px] text-muted-foreground">Answer</span>
            </div>
          </>
        )}
        {(phase === "connecting" || phase === "live") && (
          <div className="flex flex-col items-center gap-2">
            <Button className="h-16 w-16 rounded-full bg-destructive text-white hover:bg-destructive/90" onClick={hangUp} aria-label="Hang up">
              {phase === "connecting" ? <Loader2 className="!size-6 animate-spin" /> : <PhoneOff className="!size-6" />}
            </Button>
            <span className="text-[12px] text-muted-foreground">{phase === "connecting" ? "Connecting · tap to cancel" : "Hang up"}</span>
          </div>
        )}
        {phase === "ended" && <Button variant="outline" asChild><a href="/">Back to Pathya</a></Button>}
      </div>
    </div>
  );
}
