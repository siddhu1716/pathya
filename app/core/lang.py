"""Call languages. Telugu by default (household.yaml `language:` changes it; each person may set their own).
The first sentence of every call is fixed text in the person's language: it says this is an AI and who it is
for (AGENTS.md rule 8). After it, the model speaks that language and follows the caller if they switch."""

DEFAULT = "Telugu"

# mode: calling (we phoned them) | answering (a household member phoned us) | phone (unknown caller) | self (the user)
GREETINGS = {
    "Telugu": {
        "calling": "నమస్కారం {name}, నేను Pathya, {user} తరపున కాల్ చేస్తున్న AI అసిస్టెంట్‌ని.",
        "answering": "నమస్కారం {name}, నేను Pathya, {user} తరపున మాట్లాడుతున్న AI అసిస్టెంట్‌ని.",
        "phone": "నమస్కారం, నేను Pathya, {user} ఫోన్ ఎత్తిన AI అసిస్టెంట్‌ని.",
        "self": "నమస్కారం {user}, నేను Pathya, మీ AI అసిస్టెంట్‌ని.",
    },
    "Hindi": {
        "calling": "नमस्ते {name}, मैं Pathya हूँ, {user} की ओर से कॉल करने वाला AI असिस्टेंट।",
        "answering": "नमस्ते {name}, मैं Pathya हूँ, {user} की ओर से बात करने वाला AI असिस्टेंट।",
        "phone": "नमस्ते, मैं Pathya हूँ, {user} का फ़ोन उठाने वाला AI असिस्टेंट।",
        "self": "नमस्ते {user}, मैं Pathya हूँ, आपका AI असिस्टेंट।",
    },
    "English": {
        "calling": "Hello {name}, I am Pathya, an AI assistant calling for {user}.",
        "answering": "Hello {name}, I am Pathya, an AI assistant answering for {user}.",
        "phone": "Hello, I am Pathya, an AI assistant answering {user}'s phone.",
        "self": "Hello {user}, I am Pathya, your AI assistant.",
    },
}


def default(hh):
    return str((hh or {}).get("language") or DEFAULT).strip().title()


def of(hh, who=None):
    """The language to open a call in: the person's own, else the household default (Telugu)."""
    return str((who or {}).get("language") or default(hh)).strip().title()


def greet(lang, mode, user, name=""):
    """The exact first sentence. Languages without a template fall back to English (the model then switches)."""
    table = GREETINGS.get(lang) or GREETINGS["English"]
    return table[mode].format(name=name, user=user).replace("  ", " ")


def speak(lang):
    """The prompt line every call uses after the greeting."""
    return (f"After the first sentence, continue in {lang} (mixing in common English words is fine), but always reply in "
            "the language of the person's most recent sentence: if they switch, you switch at once and stay in theirs.")


# Unicode blocks of Indian scripts, and the languages written in each (the first is assumed when switching to it).
# The transcriber writes Hindi in Devanagari, Telugu in Telugu script, and so on.
SCRIPTS = {"Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Gurmukhi": (0x0A00, 0x0A7F),
           "Gujarati": (0x0A80, 0x0AFF), "Odia": (0x0B00, 0x0B7F), "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F),
           "Kannada": (0x0C80, 0x0CFF), "Malayalam": (0x0D00, 0x0D7F), "Arabic": (0x0600, 0x06FF)}
WRITTEN_IN = {"Devanagari": ("Hindi", "Marathi", "Nepali", "Konkani", "Maithili", "Sanskrit", "Dogri", "Bodo"),
              "Bengali": ("Bengali", "Assamese", "Manipuri"), "Gurmukhi": ("Punjabi",), "Gujarati": ("Gujarati",),
              "Odia": ("Odia",), "Tamil": ("Tamil",), "Telugu": ("Telugu",), "Kannada": ("Kannada", "Tulu", "Konkani"),
              "Malayalam": ("Malayalam",), "Arabic": ("Urdu", "Kashmiri")}


def script_of(text):
    """The Indian script most of what was said is written in, or None (English letters, or too little to tell)."""
    counts = {}
    for ch in str(text or ""):
        cp = ord(ch)
        for name, (lo, hi) in SCRIPTS.items():
            if lo <= cp <= hi:
                counts[name] = counts.get(name, 0) + 1
    if not counts:
        return None
    name, n = max(counts.items(), key=lambda kv: kv[1])
    return name if n >= 3 else None


def heard(text):
    """The language most likely spoken, from its script; None for English letters (could be English, or Hindi or
    Telugu typed in English letters), so those are left to the model."""
    script = script_of(text)
    return WRITTEN_IN[script][0] if script else None


def switch_note(language):
    """Sent into the call when the person's language changes: models sometimes keep the opening language."""
    return (f"The person is now speaking {language}. From your next reply, speak only {language} (common English "
            f"words are fine), until they switch again.")


class Follow:
    """Per call: the language the person is speaking, and the note to send when it changes."""

    def __init__(self, opening):
        self.now = opening

    def note(self, text):
        script = script_of(text)
        if not script or self.now.title() in WRITTEN_IN[script]:     # same script as now: e.g. Marathi stays Marathi
            return None
        self.now = WRITTEN_IN[script][0]
        return switch_note(self.now)
