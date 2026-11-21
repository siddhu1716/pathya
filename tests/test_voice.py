"""Voice settings: how Pathya sounds, its turn-taking, and the family's notes (always below the rules)."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import convo, voice
from app.core.browser_call import session_config
from app.core.store import Store
from app.experts.base import CallPlan
from tests.test_home import env


def test_settings_are_validated_and_elders_get_the_slow_patient_setting():
    store = Store(":memory:")
    assert voice.get(store)["accent"] == "indian" and voice.get(store)["interrupt"] is True
    with pytest.raises(ValueError):
        voice.save(store, {"voice": "darth"})
    with pytest.raises(ValueError):
        voice.save(store, {"notes": "x" * (voice.NOTES_MAX + 1)})
    s = voice.save(store, {"voice": "cedar", "pace": "fast", "notes": "  Call her   Amma garu. "})
    assert voice.get(store) == s and s["voice"] == "cedar" and s["notes"] == "Call her Amma garu."
    elder = voice.for_member(s, {"elder": True})
    assert (elder["pace"], elder["patience"]) == ("slow", "patient") and voice.for_member(s, {"elder": False}) == s
    assert voice.for_member({**s, "elders_slow": False}, {"elder": True})["pace"] == "fast"


def test_family_notes_sit_below_the_rules_and_the_session_uses_the_settings():
    plan = CallPlan("EXPERT RULES: never give medical advice.", "Hello", language="Telugu")
    plan.voice = voice.for_member({**voice.DEFAULTS, "voice": "sage", "interrupt": False,
                                   "notes": "Speak respectfully, use 'meeru'."}, {"elder": True})
    prompt = convo.instructions(plan)
    rules, notes, wrap = (prompt.index(x) for x in ("EXPERT RULES", "meeru", "BEFORE ENDING"))
    assert rules < notes < wrap and prompt.rstrip().endswith("Never switch back on your own.")
    assert "never override" in prompt and "Hyderabad" in prompt and "slowly" in prompt
    cfg = session_config(plan, audio_format="audio/pcmu")
    assert cfg["audio"]["output"] == {"voice": "sage", "speed": 0.9, "format": {"type": "audio/pcmu"}}
    assert cfg["audio"]["input"]["turn_detection"] == {"type": "semantic_vad", "eagerness": "low",
                                                       "interrupt_response": False}
    assert cfg["audio"]["input"]["noise_reduction"] == {"type": "near_field"}
    assert "noise_reduction" not in session_config(CallPlan("x", "y"))["audio"]["input"]    # browser: no phone filter


def test_voice_api_and_the_prompt_viewer():
    app, store, _ = env()
    with TestClient(app) as c:
        assert c.put("/api/voice", json={"pace": "sprint"}).status_code == 400
        v = c.put("/api/voice", json={"voice": "coral", "notes": "Say 'garu' after names."}).json()
        assert v["settings"]["voice"] == "coral" and len(v["voices"]) == 10 and "goodbye" in v["call_ends"]
        assert c.get("/api/voice").json()["settings"]["notes"] == "Say 'garu' after names."
        p = c.get("/api/voice/prompt?who=amma").json()
        assert p["who"] == "Amma" and "Say 'garu' after names." in p["prompt"] and "end_call" in p["tools"]
        assert p["voice"]["pace"] == "slow" and p["voice"]["voice"] == "coral"                 # Amma is 60
        assert c.get("/api/voice/prompt?who=nobody").status_code == 404
