"""Outbound calls. Twilio dials the person, then streams the call audio to our /media-stream
WebSocket, where the Realtime agent (adapted from openai-agents-python examples/realtime/twilio)
runs the Expert's CallPlan. The job id travels as a <Parameter> inside <Stream>."""
import os
from xml.sax.saxutils import quoteattr


def stream_twiml(public_host, job_id):
    url = f"wss://{public_host}/media-stream"
    return ("<Response><Connect>"
            f"<Stream url={quoteattr(url)}><Parameter name=\"job_id\" value={quoteattr(job_id)} /></Stream>"
            "</Connect></Response>")


def make_dial(twilio_client, from_number=None, public_host=None, max_minutes=None):
    host = public_host or os.environ["PUBLIC_HOST"]          # e.g. abcd-1234.ngrok-free.app (no https://)
    sender = from_number or os.environ["TWILIO_FROM"]        # your Twilio number in E.164 (+1...)
    limit = int(max_minutes or os.getenv("CALL_MAX_MINUTES", "6")) * 60

    def dial(to, job_id):
        call = twilio_client.calls.create(
            to=to, from_=sender, twiml=stream_twiml(host, job_id),
            time_limit=limit,                                # hard stop for cost and runaway calls
            status_callback=f"https://{host}/calls/status",
            status_callback_event=["completed"])
        return call.sid
    return dial


def job_id_from_start(message):
    """Twilio's 'start' message carries our <Parameter> values in start.customParameters."""
    if message.get("event") != "start":
        return None
    return ((message.get("start") or {}).get("customParameters") or {}).get("job_id")


def hang_up(twilio_client, call_sid):
    """After end_call: wait about 3 seconds so the goodbye plays, then hang up."""
    twilio_client.calls(call_sid).update(status="completed")
