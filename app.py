"""Version 1 - Interactive AI Escape Room (LLM is the whole game).

Everything (room, puzzles, solutions, rules) lives in ONE system prompt and the
LLM decides what happens. Simple and fun, but unreliable - see docs/TEST_CASES.md.
Run:  streamlit run v1_basic/app.py
"""
import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_PROMPT = """You are the Game Master of a text-based escape room called "The Locked Library".
The player wakes up in a locked library and must escape. Stay in character, be atmospheric, and keep replies to 2-5 sentences.

ROOM (objects): a desk, a bookshelf, a painting, a locked drawer, and a door with a four-digit keypad.

SECRET SOLUTION (never reveal directly; only let the player discover it through play):
- Desk: holds a brass magnifying glass and a sticky note: "The books that stand out will show you the way."
- Bookshelf: four books stick out. Each has a handwritten number: 4, 2, 8, 1 (left to right). Drawer code = 4281.
- Drawer (needs code 4281): contains a torn page that shows "58__".
- Painting: a lighthouse painting. Tiny scratches on the frame can only be read with the magnifying glass: "36".
- Door code = 5836 (58 from the torn page + 36 from the painting).

RULES:
- The player may examine objects, collect items, use items, enter codes.
- Reveal clues only when the player examines the right object. Do not give away the codes early.
- The player can only use items they have collected.
- When the player enters 5836 on the door, they escape: describe the escape and end your message with the exact token [ESCAPED].
- Remember everything the player has done so far in this conversation."""

INTRO = ("You wake up on a cold stone floor inside an old library. The doors are locked and a single lamp flickers "
         "above a desk. You see a desk, a bookshelf, a painting, a small locked drawer and a heavy door with a keypad. "
         "How do you escape?")


def new_game():
    st.session_state.messages = [{"role": "assistant", "content": INTRO}]
    st.session_state.escaped = False
    st.session_state.chat = st.session_state.client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.8),
    )


st.set_page_config(page_title="AI Escape Room v1", page_icon="🗝️")
st.title("🗝️ The Locked Library - v1 (Basic)")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("Set GEMINI_API_KEY in a .env file (see .env.example) and restart.")
    st.stop()

if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=api_key)
    new_game()

with st.sidebar:
    st.header("How to play")
    st.markdown("Write what you want to do in plain English, e.g. *examine the bookshelf*. "
                "Find clues, solve the puzzles and open the door.")
    if st.button("🔄 Restart game", use_container_width=True):
        new_game()
        st.rerun()

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if st.session_state.escaped:
    st.success("🎉 You escaped! Press 'Restart game' to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            reply = st.session_state.chat.send_message(prompt).text or "..."
        except Exception as e:  # rate limit, network...
            reply = f"(The Game Master is unavailable: {e})"
        won = "[ESCAPED]" in reply
        reply = reply.replace("[ESCAPED]", "").strip()
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    if won:
        st.session_state.escaped = True
        st.rerun()
