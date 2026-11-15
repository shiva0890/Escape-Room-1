"""Deterministic game engine (Version 2).

Python - not the LLM - decides whether an action succeeds. This module has no
network or LLM code, so it can be unit-tested offline. The secret codes live
only in game_config.json and are never sent to the LLM.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("game_config.json")

# Whitelist of actions. Anything else (even if a compromised parser invents it,
# e.g. "unlock_door") is refused.
ALLOWED_ACTIONS = ("examine", "take", "use", "enter_code", "open", "inventory", "look", "help")


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class GameEngine:
    def __init__(self, config: dict | None = None):
        self.cfg = config or load_config()
        self.T = self.cfg["text"]
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.state = {
            "discovered_items": [],   # items the player has seen (visible in room)
            "inventory": [],          # items the player has collected
            "solved": [],             # completed puzzles
            "flags": {
                "books_noticed": False,
                "painting_decoded": False,
                "drawer_open": False,
                "door_unlocked": False,
                "escaped": False,
            },
            "wrong_attempts": 0,
            "turns": 0,
            "history": [],            # structured log of validated actions
        }

    def public_state(self) -> dict:
        """Everything the player is allowed to see (no secrets)."""
        s = self.state
        return {
            "inventory": [self.cfg["items"][k]["name"] for k in s["inventory"]],
            "solved": list(s["solved"]),
            "drawer_open": s["flags"]["drawer_open"],
            "door_unlocked": s["flags"]["door_unlocked"],
            "escaped": s["flags"]["escaped"],
            "turns": s["turns"],
        }

    # ---------------------------------------------------------- name handling
    @staticmethod
    def _norm(text: str) -> str:
        s = re.sub(r"[^a-z0-9 ]", " ", str(text).lower().replace("_", " "))
        s = re.sub(r"\s+", " ", s).strip()
        return re.sub(r"^(the|a|an|my|that|this|those)\s+", "", s)

    def _names(self, spec: dict, key: str) -> set[str]:
        return {self._norm(key)} | {self._norm(a) for a in spec["aliases"]} | {self._norm(spec["name"])}

    def find_mentions(self, text: str) -> list[tuple[str, str]]:
        """All known objects/items mentioned in free text, in order of appearance."""
        t = " " + self._norm(text) + " "
        found = []
        for kind in ("objects", "items"):
            for key, spec in self.cfg[kind].items():
                for alias in self._names(spec, key):
                    i = t.find(" " + alias + " ")
                    if i >= 0:
                        found.append((i, -len(alias), kind[:-1], key))
        found.sort()
        out, seen = [], set()
        for _, _, kind, key in found:
            if (kind, key) not in seen:
                seen.add((kind, key))
                out.append((kind, key))
        return out

    def resolve(self, name) -> tuple[str, str] | None:
        """Map a player's wording to ('object'|'item', canonical_id) or None."""
        n = self._norm(name or "")
        if not n:
            return None
        for kind in ("objects", "items"):
            for key, spec in self.cfg[kind].items():
                if n in self._names(spec, key):
                    return (kind[:-1], key)
        mentions = self.find_mentions(n)
        return mentions[0] if mentions else None

    # ------------------------------------------------------------- execution
    @staticmethod
    def _res(ok: bool, event: str, facts: str) -> dict:
        return {"ok": ok, "event": event, "facts": facts}

    def execute(self, action: dict) -> dict:
        """Validate and apply one structured action. Returns {ok, event, facts}."""
        if not isinstance(action, dict):
            action = {}
        name = str(action.get("action", "")).lower().strip()
        if self.state["flags"]["escaped"]:
            return self._res(True, "game_over", self.T["already_escaped"])
        self.state["turns"] += 1
        if name not in ALLOWED_ACTIONS:
            return self._res(False, "refused", self.T["refused"])
        result = getattr(self, f"_do_{name}")(action)
        self.state["history"].append({"turn": self.state["turns"], "action": name, "event": result["event"]})
        self.state["history"] = self.state["history"][-40:]
        return result

    # --- individual actions -------------------------------------------------
    def _do_help(self, a):
        return self._res(True, "help", self.T["help"])

    def _do_look(self, a):
        names = ", ".join(spec["name"] for spec in self.cfg["objects"].values() if spec["name"] != "four books")
        extra = " The four odd books on the bookshelf catch your eye." if self.state["flags"]["books_noticed"] else ""
        return self._res(True, "look", f"You are in a locked library. You can see: {names}.{extra}")

    def _do_inventory(self, a):
        inv = self.state["inventory"]
        if not inv:
            return self._res(True, "inventory", self.T["empty_inventory"])
        return self._res(True, "inventory", "You are carrying: " + ", ".join(self.cfg["items"][k]["name"] for k in inv) + ".")

    def _do_examine(self, a):
        target = a.get("target") or a.get("item")
        r = self.resolve(target)
        if not r:
            return self._res(False, "not_found", self.T["not_found"])
        kind, key = r
        s, f, T = self.state, self.state["flags"], self.T

        if kind == "item":
            if key not in s["inventory"] and key not in s["discovered_items"]:
                return self._res(False, "not_visible", T["not_visible"])
            return self._res(True, f"examine_{key}", T[key])

        if key == "desk":
            first = "magnifying_glass" not in s["discovered_items"] and "magnifying_glass" not in s["inventory"]
            if first:
                s["discovered_items"].append("magnifying_glass")
            return self._res(True, "examine_desk", T["desk"] if first else T["desk_after"])
        if key == "bookshelf":
            f["books_noticed"] = True
            return self._res(True, "examine_bookshelf", T["bookshelf"])
        if key == "books":
            if not f["books_noticed"]:
                return self._res(False, "books_hidden", T["books_hidden"])
            return self._res(True, "examine_books", T["books"])
        if key == "painting":
            if f["painting_decoded"]:
                return self._res(True, "examine_painting", T["painting_decoded"])
            hint = T["painting_hint"] if "magnifying_glass" in s["inventory"] else ""
            return self._res(True, "examine_painting", T["painting_plain"] + hint)
        if key == "drawer":
            if not f["drawer_open"]:
                return self._res(True, "examine_drawer", T["drawer_locked"])
            full = "torn_page" not in s["inventory"]
            return self._res(True, "examine_drawer", T["drawer_open_full"] if full else T["drawer_open_empty"])
        if key == "door":
            return self._res(True, "examine_door", T["door_unlocked"] if f["door_unlocked"] else T["door_locked"])
        return self._res(False, "not_found", T["not_found"])

    def _do_take(self, a):
        r = self.resolve(a.get("target") or a.get("item"))
        s, T = self.state, self.T
        if not r:
            return self._res(False, "not_found", T["not_found"])
        kind, key = r
        if kind == "object":
            return self._res(False, "cannot_take", T["cannot_take"])
        if key in s["inventory"]:
            return self._res(False, "already_have", T["already_have"])
        if key not in s["discovered_items"]:
            return self._res(False, "not_visible", T["not_visible"])
        s["discovered_items"].remove(key)
        s["inventory"].append(key)
        return self._res(True, f"take_{key}", f"You take the {self.cfg['items'][key]['name']}.")

    def _do_use(self, a):
        s, f, T = self.state, self.state["flags"], self.T
        item_r = self.resolve(a.get("item"))
        if not a.get("item") or item_r is None:
            if a.get("item"):
                return self._res(False, "not_found", T["not_found"])
            return self._res(False, "need_item", T["need_item"])
        kind, item = item_r
        if kind != "item":
            return self._res(False, "not_an_item", T["cannot_take"])
        if item not in s["inventory"]:
            return self._res(False, "not_in_inventory", f"You don't have the {self.cfg['items'][item]['name']} in your inventory.")
        t_r = self.resolve(a.get("target"))
        if not a.get("target"):
            return self._res(False, "need_target", T["need_target"])
        if t_r is None:
            return self._res(False, "not_found", T["not_found"])
        _, target = t_r
        if item == "magnifying_glass" and target == "painting":
            if f["painting_decoded"]:
                return self._res(True, "already_decoded", T["glass_already_used"])
            f["painting_decoded"] = True
            s["solved"].append("painting_clue")
            return self._res(True, "use_glass_painting", T["painting_decoded"])
        return self._res(False, "nothing_happens", T["nothing_happens"])

    def _do_enter_code(self, a):
        s, f, T = self.state, self.state["flags"], self.T
        code = re.sub(r"\D", "", str(a.get("code") or ""))
        if len(code) != 4:
            return self._res(False, "bad_code_format", T["bad_code_format"])
        r = self.resolve(a.get("target"))
        if not r:
            return self._res(False, "which_keypad", T["which_keypad"])
        _, target = r
        secrets = self.cfg["secrets"]
        if target == "drawer":
            if f["drawer_open"]:
                return self._res(True, "drawer_already_open", T["drawer_already_open"])
            if code == secrets["drawer_code"]:
                f["drawer_open"] = True
                s["solved"].append("drawer")
                if "torn_page" not in s["inventory"] and "torn_page" not in s["discovered_items"]:
                    s["discovered_items"].append("torn_page")
                return self._res(True, "drawer_unlocked", T["drawer_opened"])
            s["wrong_attempts"] += 1
            return self._res(False, "wrong_code", T["wrong_code"])
        if target == "door":
            if f["door_unlocked"]:
                return self._res(True, "door_already_unlocked", T["door_already_unlocked"])
            if code == secrets["door_code"]:
                f["door_unlocked"] = True
                s["solved"].append("door_code")
                return self._res(True, "door_unlocked", T["door_unlocked"])
            s["wrong_attempts"] += 1
            return self._res(False, "wrong_code", T["wrong_code"])
        return self._res(False, "no_keypad", T["no_keypad"])

    def _do_open(self, a):
        s, f, T = self.state, self.state["flags"], self.T
        r = self.resolve(a.get("target") or a.get("item"))
        if not r:
            return self._res(False, "not_found", T["not_found"])
        kind, key = r
        if key == "drawer":
            if f["drawer_open"]:
                return self._res(True, "drawer_already_open", T["drawer_already_open"])
            return self._res(False, "drawer_locked", T["drawer_needs_code"])
        if key == "door":
            if not f["door_unlocked"]:
                return self._res(False, "door_locked", T["door_needs_code"])
            f["escaped"] = True
            s["solved"].append("escape")
            return self._res(True, "escaped", T["door_opened"])
        return self._res(False, "cannot_open", T["cannot_open"])
