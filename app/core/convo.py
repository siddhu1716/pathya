"""Rules every call follows, whatever the Expert:
- Language: reply in the language of the person's most recent sentence (the greeting opens in the default, Telugu).
- Wrap-up: after each task, recap and ask whether anything else is pending; end_call is refused (in code) until the
  person confirms nothing is left, unless they said goodbye, there is an emergency, or the time is over (rule 8)."""
from typing import Literal

GOODBYE = "Say goodbye now."
NOT_YET = ("Not yet. In their language, recap what you did in one sentence and ask whether anything else is pending. "
           "Call end_call again with person_confirmed_done=true only after they say nothing else is needed.")
WRAP_UP = ("BEFORE ENDING: after each task, recap it in one sentence and ask whether anything else is pending. "
           "Call end_call with person_confirmed_done=true and why=all_done only after they say nothing else is needed. "
           "Exceptions: they say goodbye or must go (why=person_said_goodbye), an emergency (why=emergency), "
           "or you are told the time is over (why=time_up).")


def language_rule(default):
    return (f"LANGUAGE: open in {default}. From then on ALWAYS reply in the language of the person's most recent sentence "
            "(Telugu, Hindi, English, Tamil, Kannada or any other); if they mix languages, mix the same way; if they ask "
            "for a language, use it for the rest of the call. Never switch back on your own.")


def instructions(plan, default="Telugu"):
    """The full prompt sent to the Realtime model: language rule first and last (models drift), the Expert's prompt,
    how to sound (accent, pace, the family's notes: below the rules, never above them), then the wrap-up rule."""
    from app.core import voice
    rule = language_rule(getattr(plan, "language", "") or default)
    return f"{rule}\n\n{plan.instructions}\n\n{voice.style(getattr(plan, 'voice', None))}{WRAP_UP}\n\n{rule}"


def end_call_tool(saved):
    """The end_call every CallPlan uses. Writes saved["summary"]; refused while the person may still need something."""
    def end_call(summary: str, person_confirmed_done: bool,
                 why: Literal["all_done", "person_said_goodbye", "emergency", "time_up"]) -> str:
        """Finish the call. summary: one line in English. Use why=all_done only after the person confirmed nothing else
        is pending (person_confirmed_done=true)."""
        if why == "all_done" and not person_confirmed_done:
            return NOT_YET
        saved["summary"], saved["ended_because"] = summary, why
        return GOODBYE
    return end_call


def ends_call(name, output):
    return name == "end_call" and str(output).endswith(GOODBYE)
