"""Browser calls: run an Expert's CallPlan over OpenAI Realtime (WebRTC) without a phone line.
The browser sends its SDP offer to our server; the server adds the session config (persona, tools,
voice) and calls OpenAI with the real key, so neither the key nor the tool list ever reach the browser.
Tool calls come back to the server and run the Expert's own Python functions, so refusals stay in code."""
import inspect
import json
import os
import time

import httpx

REALTIME_URL = "https://api.openai.com/v1/realtime/calls"


def tool_specs(plan):
    """Realtime function-tool definitions from the plan's plain Python functions."""
    from agents import function_tool
    specs = []
    for f in plan.tools:
        t = function_tool(f)
        specs.append({"type": "function", "name": t.name, "description": t.description or "",
                      "parameters": t.params_json_schema})
    return specs


def session_config(plan, model=None, voice=None):
    return {
        "type": "realtime",
        "model": model or os.getenv("REALTIME_MODEL", "gpt-realtime-2.1"),
        "instructions": plan.instructions,
        "audio": {
            "input": {"transcription": {"model": os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")},
                      "turn_detection": {"type": "semantic_vad"}},
            "output": {"voice": voice or os.getenv("REALTIME_VOICE", "marin")},
        },
        "tools": tool_specs(plan),
        "tool_choice": "auto",
    }


async def answer_sdp(offer_sdp, config, api_key=None, client=None):
    """Exchange the browser's SDP offer for OpenAI's SDP answer (Realtime unified interface)."""
    key = api_key or os.environ["OPENAI_API_KEY"]
    files = {"sdp": (None, offer_sdp), "session": (None, json.dumps(config))}
    async with (client or httpx.AsyncClient(timeout=30)) as c:
        r = await c.post(REALTIME_URL, headers={"Authorization": f"Bearer {key}"}, files=files)
    if r.status_code >= 300:
        raise RuntimeError(f"Realtime session failed ({r.status_code}): {r.text[:300]}")
    return r.text


class Call:
    """One live call: the job, its Expert and the plan whose tools fill `plan.saved`."""

    def __init__(self, job, expert, plan):
        self.job, self.expert, self.plan = job, expert, plan
        self.started = time.time()
        self.deadline = self.started + plan.max_minutes * 60
        self.ended = False
        self.tools = {f.__name__: f for f in plan.tools}

    async def run_tool(self, name, arguments):
        """Run one tool the model asked for. Unknown tools and calls past the time limit are refused."""
        if self.ended or time.time() > self.deadline + 30:
            return "The call time is over. Say goodbye now."
        f = self.tools.get(name)
        if not f:
            return f"Unknown tool {name}."
        try:
            args = json.loads(arguments or "{}")
            out = f(**args)
            if inspect.isawaitable(out):
                out = await out
            return str(out)
        except Exception as err:                      # tell the model, keep the call going
            return f"Tool error: {err}"
