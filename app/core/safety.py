"""Health safety net: every health text QuickPick sends or saves passes Amazon Bedrock
Guardrails (ApplyGuardrail) first. Denied topics: diagnosis, medicine advice, result reading."""
import os
from dataclasses import dataclass


@dataclass
class Verdict:
    status: str      # passed | blocked | unchecked
    text: str        # the text to use (the guardrail's replacement when blocked)


_client = None


def check(text, source="OUTPUT", client=None):
    gid = os.getenv("GUARDRAIL_ID")
    if not gid:
        return Verdict("unchecked", text)
    global _client
    if client is None:
        if _client is None:
            import boto3
            _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        client = _client
    r = client.apply_guardrail(guardrailIdentifier=gid, guardrailVersion=os.getenv("GUARDRAIL_VERSION", "1"),
                               source=source, content=[{"text": {"text": text}}])
    if r.get("action") == "GUARDRAIL_INTERVENED":
        outs = r.get("outputs") or []
        return Verdict("blocked", outs[0].get("text", "") if outs else "")
    return Verdict("passed", text)
