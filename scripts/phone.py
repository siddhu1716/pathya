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
