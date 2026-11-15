"""One game turn:  player text -> parse -> VALIDATE (engine) -> narrate."""
from __future__ import annotations

from parser import rule_parse


def process_turn(engine, player_text: str, client=None, chat_history: list[dict] | None = None) -> dict:
    chat_history = chat_history or []
    source = "rules"
    action = None
    if client is not None:
        try:
            from llm import parse_intent
            action = parse_intent(client, player_text)
            source = "llm"
        except Exception:
            action = None  # API error / bad JSON -> fall back
    if action is None:
        action = rule_parse(player_text, engine)

    result = engine.execute(action)   # <- the only place the game state changes

    reply = result["facts"]
    if client is not None:
        try:
            from llm import narrate
            reply = narrate(client, result["facts"], result["ok"], chat_history)
        except Exception:
            reply = result["facts"]
    return {"reply": reply, "action": action, "result": result, "parser": source}
