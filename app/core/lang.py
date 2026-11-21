"""Call languages. Telugu by default (household.yaml `language:` changes it; each person may set their own).
The first sentence of every call is fixed text in the person's language: it says this is an AI and who it is
for (AGENTS.md rule 8). After it, the model speaks that language and follows the caller if they switch."""

DEFAULT = "Telugu"

# mode: calling (we phoned them) | answering (a household member phoned us) | phone (unknown caller) | self (the user)
GREETINGS = {
    "Telugu": {
        "calling": "నమస్కారం {name}, నేను QuickPick, {user} తరపున కాల్ చేస్తున్న AI అసిస్టెంట్‌ని.",
        "answering": "నమస్కారం {name}, నేను QuickPick, {user} తరపున మాట్లాడుతున్న AI అసిస్టెంట్‌ని.",
        "phone": "నమస్కారం, నేను QuickPick, {user} ఫోన్ ఎత్తిన AI అసిస్టెంట్‌ని.",
        "self": "నమస్కారం {user}, నేను QuickPick, మీ AI అసిస్టెంట్‌ని.",
    },
    "Hindi": {
        "calling": "नमस्ते {name}, मैं QuickPick हूँ, {user} की ओर से कॉल करने वाला AI असिस्टेंट।",
        "answering": "नमस्ते {name}, मैं QuickPick हूँ, {user} की ओर से बात करने वाला AI असिस्टेंट।",
        "phone": "नमस्ते, मैं QuickPick हूँ, {user} का फ़ोन उठाने वाला AI असिस्टेंट।",
        "self": "नमस्ते {user}, मैं QuickPick हूँ, आपका AI असिस्टेंट।",
    },
    "English": {
        "calling": "Hello {name}, I am QuickPick, an AI assistant calling for {user}.",
        "answering": "Hello {name}, I am QuickPick, an AI assistant answering for {user}.",
        "phone": "Hello, I am QuickPick, an AI assistant answering {user}'s phone.",
        "self": "Hello {user}, I am QuickPick, your AI assistant.",
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
    return (f"After the first sentence, speak {lang} (mixing in common English words is fine). If the other person "
            "speaks another language (Telugu, Hindi, English or any other), switch to theirs at once and stay in it.")
