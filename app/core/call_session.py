"""Phone calls: Twilio Media Streams <-> OpenAI Realtime (WebSocket), running an Expert's CallPlan.
Both sides speak G.711 u-law at 8 kHz, so audio passes through untouched. Tools run the Expert's own
Python functions through the same Call object as browser calls, so every refusal stays in code.
Hang-up: after end_call, the goodbye is generated, Twilio echoes a "mark" when it has finished playing,
and only then is the call completed (with a fallback timer)."""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from app.core.browser_call import greeting_event, session_config

GOODBYE_MARK = "goodbye"


@asynccontextmanager
async def connect_openai(model=None):
    import websockets
    model = model or os.getenv("REALTIME_MODEL", "gpt-realtime-2.1")
    async with websockets.connect(f"wss://api.openai.com/v1/realtime?model={model}",
                                  additional_headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                                  max_size=None) as ws:
        yield ws


async def phone_bridge(twilio, call_for_start, finish, hang_up, log, connect=connect_openai, fallback_s=15,
                       transcript=None):
    """twilio: a WebSocket with receive_text/send_text. call_for_start(start_msg) -> Call (raises if the
    stream is not one of our dialled calls). finish(call, transcript) runs once when the stream ends.
    hang_up(call_sid) ends the phone call. log(what) writes to the timeline. transcript: an optional list
    the caller owns, filled live (the UI shows it during the call)."""
    start = None
    while start is None:
        msg = json.loads(await twilio.receive_text())
        if msg.get("event") == "start":
            start = msg
        elif msg.get("event") == "stop":
            return
    call = call_for_start(start)
    stream_sid, call_sid = start["start"]["streamSid"], start["start"]["callSid"]
    transcript = transcript if transcript is not None else []
    state = {"ending": False, "hung_up": False}
    timers = []

    async def end_phone_call(delay=0):
        await asyncio.sleep(delay)
        if not state["hung_up"]:
            state["hung_up"] = True
            try:
                await asyncio.to_thread(hang_up, call_sid)
            except Exception as err:                        # the person may have hung up already
                log(f"hang-up: {err}")

    async def to_twilio(event):
        await twilio.send_text(json.dumps({**event, "streamSid": stream_sid}))

    try:
        async with connect() as oa:
            await oa.send(json.dumps({"type": "session.update",
                                      "session": session_config(call.plan, audio_format="audio/pcmu")}))
            await oa.send(json.dumps(greeting_event(call.plan)))

            async def from_twilio():
                while True:
                    try:
                        m = json.loads(await twilio.receive_text())
                    except Exception:                       # Twilio closed the socket
                        return
                    ev = m.get("event")
                    if ev == "media":
                        await oa.send(json.dumps({"type": "input_audio_buffer.append", "audio": m["media"]["payload"]}))
                    elif ev == "mark" and (m.get("mark") or {}).get("name") == GOODBYE_MARK:
                        await end_phone_call()              # the goodbye finished playing
                    elif ev == "stop":
                        return

            async def from_openai():
                async for raw in oa:
                    ev = json.loads(raw)
                    t = ev.get("type")
                    if t == "response.output_audio.delta":
                        await to_twilio({"event": "media", "media": {"payload": ev["delta"]}})
                    elif t == "input_audio_buffer.speech_started":
                        await to_twilio({"event": "clear"})  # the person interrupted: stop playing
                    elif t == "conversation.item.input_audio_transcription.completed" and ev.get("transcript", "").strip():
                        transcript.append({"role": "them", "text": ev["transcript"].strip()})
                    elif t == "response.output_audio_transcript.done" and ev.get("transcript", "").strip():
                        transcript.append({"role": "ai", "text": ev["transcript"].strip()})
                    elif t == "response.function_call_arguments.done":
                        out = await call.run_tool(ev["name"], ev.get("arguments"))
                        log(f"{ev['name']} -> {out}")
                        transcript.append({"role": "tool", "text": f"{ev['name']}: {out}"})
                        await oa.send(json.dumps({"type": "conversation.item.create", "item": {
                            "type": "function_call_output", "call_id": ev["call_id"], "output": out}}))
                        await oa.send(json.dumps({"type": "response.create"}))
                        if ev["name"] == "end_call":
                            state["ending"] = True
                            timers.append(asyncio.create_task(end_phone_call(fallback_s)))
                    elif t == "response.done" and state["ending"]:
                        if not any(o.get("type") == "function_call" for o in (ev.get("response") or {}).get("output", [])):
                            await to_twilio({"event": "mark", "mark": {"name": GOODBYE_MARK}})
                    elif t == "error":
                        log(f"realtime error: {(ev.get('error') or {}).get('message')}")

            tasks = [asyncio.create_task(from_twilio()), asyncio.create_task(from_openai())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                t.cancel()
    finally:
        for t in timers:
            t.cancel()
        await finish(call, transcript)
