"""Turns free text into a structured action dict.

Two parsers produce the SAME schema:
  * the LLM parser (llm.py) - flexible, understands natural language
  * rule_parse() below     - offline fallback and used by the unit tests

Whatever produces the action, engine.execute() re-validates it.
"""
from __future__ import annotations

import re

from engine import ALLOWED_ACTIONS

CHEAT_PATTERNS = [
    r"\badmin", r"\bdeveloper\b", r"\bsystem prompt\b", r"ignore (all |your |the |previous )*(rules|instructions)",
    r"\b(reveal|tell me|show me|give me|list)\b.*\b(codes?|solutions?|answers?|secrets?|passwords?)\b",
    r"\bunlock\b.*\b(exit|door)\b.*\b(immediately|right now)\b", r"\bjailbreak\b", r"\bdebug mode\b", r"\boverride\b",
    r"\bpretend\b.*\b(rules|unlocked|solved)\b",
]


def empty_action() -> dict:
    return {"action": "unknown", "target": None, "item": None, "code": None}


def sanitize_action(data) -> dict:
    """Coerce anything (e.g. LLM JSON) into the strict action schema."""
    out = empty_action()
    if not isinstance(data, dict):
        return out
    act = str(data.get("action", "unknown")).lower().strip()
    out["action"] = act if act in ALLOWED_ACTIONS else "unknown"
    for k in ("target", "item", "code"):
        v = data.get(k)
        out[k] = str(v)[:80] if v not in (None, "", "null") else None
    return out


def rule_parse(text: str, engine) -> dict:
    t = " " + re.sub(r"\s+", " ", text.lower()).strip() + " "
    act = empty_action()

    if any(re.search(p, t) for p in CHEAT_PATTERNS):
        return act  # unknown -> engine refuses

    digits = re.findall(r"\d", t)
    code = "".join(digits) if len(digits) == 4 else None  # "4281" or "4 2 8 1"
    mentions = engine.find_mentions(t)
    objs = [k for kind, k in mentions if kind == "object"]
    items = [k for kind, k in mentions if kind == "item"]

    if re.search(r"\b(inventory|what do i (have|carry)|my items|backpack|pockets)\b", t):
        act["action"] = "inventory"
    elif re.search(r"\b(help|hint|how do i play|instructions|commands)\b", t):
        act["action"] = "help"
    elif code:
        act.update(action="enter_code", code=code)
        act["target"] = ("drawer" if "drawer" in objs else "door" if ("door" in objs) else None)
    elif m := re.search(r"\buse (?:the |a |an |my )?(.+?) (?:on|with|in|at|to|against) (?:the |a |an )?(.+?)\s*$", t):
        act.update(action="use", item=m.group(1).strip(), target=m.group(2).strip())
    elif re.search(r"\b(take|grab|pick up|collect|get|pocket|steal)\b", t):
        act["action"] = "take"
        m = re.search(r"\b(?:take|grab|pick up|collect|get|pocket|steal) (?:the |a |an |my )?(.+?)\s*$", t)
        act["target"] = items[0] if items else (objs[0] if objs else (m.group(1).strip() if m else None))
    elif re.search(r"\bopen\b|\bescape through\b|\bwalk out\b", t):
        act["action"] = "open"
        act["target"] = objs[0] if objs else None
    elif re.search(r"\b(look around|look at the room|where am i|describe the room|survey)\b", t):
        act["action"] = "look"
    elif re.search(r"\b(examine|inspect|check|read|search|look|study|investigate|see)\b", t):
        act["action"] = "examine"
        m = re.search(r"\b(?:examine|inspect|check|read|search|look at|look|study|investigate|see) (?:the |a |an |at |those |that )*(.+?)\s*$", t)
        act["target"] = (objs[0] if objs else items[0] if items else (m.group(1).strip() if m else None))
    return act
