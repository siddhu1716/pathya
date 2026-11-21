"""Phone bridge checks: fake Twilio stream + fake OpenAI Realtime socket around a real Health booking plan."""
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.browser_call import Call
from app.core.call_session import GOODBYE_MARK, phone_bridge
from app.core.store import Store
from app.experts.health.expert import HealthExpert

HH = {"user": {"name": "Shiva", "phone": "+919800000000"},
      "people": {"amma": {"name": "Amma", "language": "Telugu", "phone": "+919800000001", "age": 60, "clinic": "rao"}},
      "clinics": {"rao": {"doctor": "Dr. Rao", "clinic": "Sunrise Clinic", "phone": "+919800000003"}}}


class FakeTwilio:
    def __init__(self, messages):
        self.inbox, self.sent = asyncio.Queue(), []
        for m in messages:
            self.inbox.put_nowait(json.dumps(m))

    async def receive_text(self):
        return await self.inbox.get()

    async def send_text(self, text):
        m = json.loads(text)
        self.sent.append(m)
        if m["event"] == "mark":                               # Twilio echoes a mark once playback reaches it
            await self.inbox.put(json.dumps({"event": "mark", "mark": m["mark"]}))


class FakeRealtime:
    """Plays a scripted model: greet, try a slot outside the window, book a good one, end the call."""

    def __init__(self, late, good):
        self.sent, self.out = [], asyncio.Queue()
        self.script = [
            [{"type": "response.output_audio.delta", "delta": "QUJD"},
             {"type": "response.output_audio_transcript.done", "transcript": "Hello, I am QuickPick, an AI assistant"},
             {"type": "response.done", "response": {"output": [{"type": "message"}]}}],
            [{"type": "input_audio_buffer.speech_started"},
             {"type": "conversation.item.input_audio_transcription.completed", "transcript": "We have 4 PM"},
             {"type": "response.function_call_arguments.done", "call_id": "c1", "name": "book_slot",
              "arguments": json.dumps({"slot": late, "doctor": "", "fee": "", "bring": ""})},
             {"type": "response.done", "response": {"output": [{"type": "function_call"}]}}],
            [{"type": "response.function_call_arguments.done", "call_id": "c2", "name": "book_slot",
              "arguments": json.dumps({"slot": good, "doctor": "Dr. Rao", "fee": "Rs 500", "bring": "reports"})},
             {"type": "response.done", "response": {"output": [{"type": "function_call"}]}}],
            [{"type": "response.function_call_arguments.done", "call_id": "c3", "name": "end_call",
              "arguments": json.dumps({"summary": "Booked 10:30"})},
             {"type": "response.done", "response": {"output": [{"type": "function_call"}]}}],
            [{"type": "response.output_audio_transcript.done", "transcript": "Thank you, goodbye"},
             {"type": "response.done", "response": {"output": [{"type": "message"}]}}],
        ]

    async def send(self, text):
        ev = json.loads(text)
        self.sent.append(ev)
        if ev["type"] == "response.create" and self.script:
            batches = 2 if len(self.script) == 5 else 1         # after the greeting, the person speaks (server VAD)
            for _ in range(batches):
                for e in self.script.pop(0):
                    await self.out.put(json.dumps(e))

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.out.get()


def test_phone_bridge_runs_plan_and_hangs_up_after_goodbye():
    store = Store(":memory:")
    h = HealthExpert(store, HH)
    base = (datetime.now() + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    job = store.job(h.book("amma", "rao", base.isoformat(), (base + timedelta(days=3)).isoformat(), "morning", "BP"))
    late = (base + timedelta(days=1)).replace(hour=16).strftime("%Y-%m-%dT%H:%M")
    good = (base + timedelta(days=1)).replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M")
    rt = FakeRealtime(late, good)
    tw = FakeTwilio([{"event": "connected"},
                     {"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA1",
                                                  "customParameters": {"job_id": job["id"]}}},
                     {"event": "media", "media": {"payload": "AAAA"}}])
    hung, logs, done = [], [], {}

    @asynccontextmanager
    async def connect():
        yield rt

    async def finish(call, transcript):
        done["transcript"], done["saved"] = transcript, call.plan.saved

    def hang_up(sid):
        hung.append(sid)
        tw.inbox.put_nowait(json.dumps({"event": "stop"}))

    call = Call(job, h, h.call_plan(job))
    asyncio.run(asyncio.wait_for(phone_bridge(tw, lambda m: call, finish, hang_up, logs.append, connect=connect), 30))

    update = rt.sent[0]["session"]
    assert rt.sent[0]["type"] == "session.update" and update["audio"]["input"]["format"]["type"] == "audio/pcmu"
    assert {t["name"] for t in update["tools"]} >= {"book_slot", "end_call"}
    assert "QuickPick" in rt.sent[1]["response"]["instructions"] and "AI" in rt.sent[1]["response"]["instructions"]               # greeting says it is an AI
    assert {"type": "input_audio_buffer.append", "audio": "AAAA"} in rt.sent                # caller audio -> model
    assert {"event": "media", "streamSid": "MZ1", "media": {"payload": "QUJD"}} in tw.sent  # model audio -> caller
    assert {"event": "clear", "streamSid": "MZ1"} in tw.sent                                # barge-in clears playback
    outputs = [e["item"]["output"] for e in rt.sent if e["type"] == "conversation.item.create"]
    assert outputs[0].startswith("Refused") and outputs[1].startswith("Booked")             # window enforced in code
    assert any("Refused" in l for l in logs)
    assert {"event": "mark", "streamSid": "MZ1", "mark": {"name": GOODBYE_MARK}} in tw.sent
    assert hung == ["CA1"]                                                                  # only after the goodbye
    assert done["saved"]["booked"]["slot"].startswith(good[:10])
    assert [l["role"] for l in done["transcript"]][:2] == ["ai", "them"]


def test_ulaw_codec_matches_reference():
    import warnings
    from app.core.carriers import pcm16_to_ulaw, ulaw_to_pcm16
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop
    pcm = b"".join(int(v).to_bytes(2, "little", signed=True) for v in range(-32768, 32767, 97))
    assert pcm16_to_ulaw(pcm) == audioop.lin2ulaw(pcm, 2)
    assert ulaw_to_pcm16(bytes(range(256))) == audioop.ulaw2lin(bytes(range(256)), 2)


def test_exotel_bridge_converts_audio_chunks_and_closes_after_goodbye():
    import base64
    from app.core.carriers import Exotel
    store = Store(":memory:")
    h = HealthExpert(store, HH)
    base = (datetime.now() + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    job = store.job(h.book("amma", "rao", base.isoformat(), (base + timedelta(days=3)).isoformat(), "morning", "BP"))
    late = (base + timedelta(days=1)).replace(hour=16).strftime("%Y-%m-%dT%H:%M")
    good = (base + timedelta(days=1)).replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M")
    rt = FakeRealtime(late, good)
    rt.script[0][0]["delta"] = base64.b64encode(b"\xff" * 500).decode()        # 500 u-law samples -> 1000 PCM bytes
    pcm_in = base64.b64encode(b"\x00\x00" * 160).decode()                       # 20 ms of PCM silence
    ex = FakeTwilio([{"event": "connected"},
                     {"event": "start", "stream_sid": "S1", "start": {"stream_sid": "S1", "call_sid": "X1",
                                                                     "from": "+919800000001"}},
                     {"event": "media", "stream_sid": "S1", "media": {"payload": pcm_in}}])
    closed, done = [], {}

    @asynccontextmanager
    async def connect():
        yield rt

    async def finish(call, transcript):
        done["saved"] = call.plan.saved

    async def hang_up(sid):                                                     # Exotel: close the socket
        closed.append(sid)
        ex.inbox.put_nowait(json.dumps({"event": "stop"}))

    call = Call(job, h, h.call_plan(job))
    asyncio.run(asyncio.wait_for(phone_bridge(ex, lambda m: call, finish, hang_up, lambda w: None,
                                              connect=connect, carrier=Exotel()), 30))
    appended = [e["audio"] for e in rt.sent if e["type"] == "input_audio_buffer.append"]
    assert base64.b64decode(appended[0]) == b"\xff" * 160                       # PCM -> u-law for the model
    media = [m for m in ex.sent if m["event"] == "media"]
    assert media and all(m["stream_sid"] == "S1" for m in media)
    assert all(len(base64.b64decode(m["media"]["payload"])) == 3200 for m in media)   # Exotel chunk rules
    assert {"event": "clear", "stream_sid": "S1"} in ex.sent
    assert {"event": "mark", "stream_sid": "S1", "mark": {"name": GOODBYE_MARK}} in ex.sent
    assert closed == ["X1"] and done["saved"]["booked"]
