"""Version 2 - Reliable AI Escape Room (Streamlit UI).
Run:  streamlit run v2_reliable/app.py
"""
import streamlit as st

from controller import process_turn
from engine import GameEngine
from llm import get_client

st.set_page_config(page_title="AI Escape Room v2", page_icon="🗝️")

if "engine" not in st.session_state:
    st.session_state.engine = GameEngine()
    st.session_state.messages = [{"role": "assistant", "content": st.session_state.engine.cfg["intro"]}]
    st.session_state.client = get_client()

engine: GameEngine = st.session_state.engine

st.title("🗝️ The Locked Library - v2 (Reliable)")
st.caption("Python validates every action. The LLM only understands your words and narrates the result.")

with st.sidebar:
    st.header("How to play")
    st.markdown("Type what you want to do, e.g. *examine the desk*, *take the key*, *use X on Y*, "
                "*enter 1234 on the drawer*, *open the door*. Type **help** for commands.")
    if st.button("🔄 Restart game", use_container_width=True):
        engine.reset()
        st.session_state.messages = [{"role": "assistant", "content": engine.cfg["intro"]}]
        st.rerun()
    pub = engine.public_state()
    st.header("Inventory")
    st.write(", ".join(pub["inventory"]) if pub["inventory"] else "_empty_")
    st.header("Progress")
    st.write(f"Puzzles solved: {len([s for s in pub['solved'] if s != 'escape'])}/3")
    st.write(f"Turns: {pub['turns']}")
    use_llm = st.toggle("Use Gemini", value=st.session_state.client is not None,
                        disabled=st.session_state.client is None,
                        help="Set GEMINI_API_KEY in .env to enable. Without it the game runs in offline rule mode.")
    if st.session_state.client is None:
        st.info("No GEMINI_API_KEY found: running in offline mode (rule parser, plain narration).")
    debug = st.toggle("Debug: show validated action & state", value=False)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if engine.state["flags"]["escaped"]:
    st.success("🎉 You escaped! Press 'Restart game' to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("..."):
            out = process_turn(engine, prompt, st.session_state.client if use_llm else None,
                               st.session_state.messages)
        st.markdown(out["reply"])
        if debug:
            st.json({"parsed_action": out["action"], "parser": out["parser"], "engine_result": out["result"]})
    st.session_state.messages.append({"role": "assistant", "content": out["reply"]})
    st.rerun() if engine.state["flags"]["escaped"] else None

if debug:
    with st.expander("Full game state (debug)"):
        st.json(engine.state)
