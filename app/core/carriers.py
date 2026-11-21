"""Phone carriers for the call bridge. The OpenAI side always speaks G.711 u-law at 8 kHz; each carrier
adapter translates its own stream protocol and audio format to that.
- Twilio Media Streams: u-law 8 kHz, camelCase fields (streamSid, callSid), hang up via the REST API.
- Exotel Voicebot applet: raw 16-bit 8 kHz PCM, snake_case fields (stream_sid, call_sid), audio back in
  chunks of 3.2 KB..100 KB in multiples of 320 bytes; hang up by closing the WebSocket (the flow moves on)."""
import base64
import sys
from array import array

# ---- G.711 u-law <-> 16-bit PCM (pure Python; audioop is gone in Python 3.13) ----
_BIAS = 0x84
_SEG_END = (0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF)


def _ulaw_to_lin(u):
    u = ~u & 0xFF
    sample = ((((u & 0x0F) << 3) + _BIAS) << ((u >> 4) & 0x07)) - _BIAS
    return -sample if u & 0x80 else sample


def _lin_to_ulaw(s):
    """The ITU G.711 reference encoder (14-bit), as in CPython's audioop.lin2ulaw."""
    v = s >> 2
    v, mask = (-v, 0x7F) if v < 0 else (v, 0xFF)
    v = min(v, 8159) + (_BIAS >> 2)
    seg = next((i for i, end in enumerate(_SEG_END) if v <= end), 8)
    if seg >= 8:
        return 0x7F ^ mask
    return ((seg << 4) | ((v >> (seg + 1)) & 0x0F)) ^ mask


_DEC = array("h", [_ulaw_to_lin(i) for i in range(256)])
_ENC = bytes(_lin_to_ulaw(i if i < 32768 else i - 65536) for i in range(65536))


def pcm16_to_ulaw(pcm: bytes) -> bytes:
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return bytes(_ENC[s & 0xFFFF] for s in samples)


def ulaw_to_pcm16(ulaw: bytes) -> bytes:
    samples = array("h", (_DEC[b] for b in ulaw))
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes()


# ---- carrier adapters ----
class Twilio:
    name = "twilio"

    def start(self, msg):
        s = msg.get("start") or {}
        return {"stream": s.get("streamSid") or msg.get("streamSid"), "call": s.get("callSid"),
                "params": s.get("customParameters") or {}, "from": s.get("from")}

    def to_model(self, payload):                         # caller audio -> u-law base64
        return payload

    def media(self, stream, ulaw_b64):                   # model audio -> messages for the carrier
        return [{"event": "media", "streamSid": stream, "media": {"payload": ulaw_b64}}]

    def flush(self, stream):
        return []

    def clear(self, stream):
        return {"event": "clear", "streamSid": stream}

    def mark(self, stream, name):
        return {"event": "mark", "streamSid": stream, "mark": {"name": name}}


class Exotel:
    name = "exotel"
    CHUNK = 3200                                         # 100 ms of 8 kHz 16-bit audio (Exotel's minimum)

    def __init__(self):
        self.buf = bytearray()

    def start(self, msg):
        s = msg.get("start") or {}
        return {"stream": s.get("stream_sid") or msg.get("stream_sid"), "call": s.get("call_sid"),
                "params": s.get("custom_parameters") or {}, "from": s.get("from")}

    def to_model(self, payload):
        return base64.b64encode(pcm16_to_ulaw(base64.b64decode(payload))).decode()

    def _send(self, stream, pcm):
        return {"event": "media", "stream_sid": stream, "media": {"payload": base64.b64encode(pcm).decode()}}

    def media(self, stream, ulaw_b64):
        self.buf += ulaw_to_pcm16(base64.b64decode(ulaw_b64))
        out = []
        while len(self.buf) >= self.CHUNK:
            out.append(self._send(stream, bytes(self.buf[: self.CHUNK])))
            del self.buf[: self.CHUNK]
        return out

    def flush(self, stream):
        """End of a reply: pad the tail with silence to a full chunk so nothing is cut off."""
        if not self.buf:
            return []
        pcm = bytes(self.buf) + b"\x00" * (self.CHUNK - len(self.buf))
        self.buf.clear()
        return [self._send(stream, pcm)]

    def clear(self, stream):
        self.buf.clear()
        return {"event": "clear", "stream_sid": stream}

    def mark(self, stream, name):
        return {"event": "mark", "stream_sid": stream, "mark": {"name": name}}
