"""Phone mode: open a public HTTPS tunnel to the app so Twilio can reach /media-stream and /calls/status.
python scripts/phone.py        (keep it running; start the app in another terminal; Ctrl+C to stop)
Starts a free cloudflared quick tunnel, writes PUBLIC_HOST and CALL_MODE=twilio into .env, and restores
CALL_MODE=browser on exit. The quick-tunnel address changes each run, so restart the app after this prints."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
CANDIDATES = [shutil.which("cloudflared"), r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
              r"C:\Program Files\cloudflared\cloudflared.exe"]


def set_env(updates):
    lines = ENV.read_text(encoding="utf-8").splitlines()
    for key, value in updates.items():
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                comment = line.split("#", 1)[1] if "#" in line else ""
                lines[i] = f"{key}={value}" + (f"    #{comment}" if comment else "")
                break
        else:
            lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def exotel_secret():
    """The password in Exotel's wss://quickpick:<secret>@host/exotel URL; created once, kept in .env."""
    import secrets
    from dotenv import dotenv_values
    secret = (dotenv_values(ENV).get("EXOTEL_STREAM_SECRET") or "").strip()
    if len(secret) < 16:
        secret = secrets.token_hex(16)
        set_env({"EXOTEL_STREAM_SECRET": secret})
    return secret


def app_key():
    """APP_KEY guards the app's API once it is public; created once, kept in .env."""
    import secrets
    from dotenv import dotenv_values
    key = (dotenv_values(ENV).get("APP_KEY") or "").strip()
    if len(key) < 12:
        key = secrets.token_urlsafe(12)
        set_env({"APP_KEY": key})
    return key


def point_number_here(host):
    """Incoming calls to the Twilio number -> https://<host>/calls/incoming."""
    from dotenv import dotenv_values
    from twilio.rest import Client
    env = dotenv_values(ENV)
    client = Client(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"])
    numbers = client.incoming_phone_numbers.list(phone_number=env["TWILIO_FROM"].split("#")[0].strip(), limit=1)
    if not numbers:
        return print(f"Twilio number {env['TWILIO_FROM']} not found on this account; incoming calls not set up.")
    numbers[0].update(voice_url=f"https://{host}/calls/incoming", voice_method="POST")
    print(f"Incoming calls to {env['TWILIO_FROM']} now reach QuickPick.")


def main(port="8000"):
    exe = next((c for c in CANDIDATES if c and os.path.exists(c)), None)
    if not exe:
        sys.exit("cloudflared not found. Install it: winget install --id Cloudflare.cloudflared")
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        found = False
        for line in proc.stdout:                          # keep draining, or cloudflared blocks on a full pipe
            m = None if found else re.search(r"https://([a-z0-9-]+\.trycloudflare\.com)", line)
            if m:
                found = True
                set_env({"PUBLIC_HOST": m.group(1), "CALL_MODE": "twilio"})
                print(f"Tunnel: https://{m.group(1)}  ->  localhost:{port}", flush=True)
                print("Wrote PUBLIC_HOST and CALL_MODE=twilio to .env.")
                try:
                    point_number_here(m.group(1))
                except Exception as err:
                    print(f"Could not set the incoming-call webhook: {err}")
                print(f"Exotel Voicebot applet URL (paste into your call flow):\n  "
                      f"wss://quickpick:{exotel_secret()}@{m.group(1)}/exotel", flush=True)
                print(f"Open on your phone (the key is remembered after the first visit):\n  "
                      f"https://{m.group(1)}/?key={app_key()}", flush=True)
                print(f"Now (re)start the app: uvicorn app.main:app --port {port}")
                print("Ctrl+C here closes the tunnel and switches back to browser calls.", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        set_env({"CALL_MODE": "browser"})
        print("Tunnel closed; CALL_MODE=browser.")


if __name__ == "__main__":
    main(*sys.argv[1:2])
