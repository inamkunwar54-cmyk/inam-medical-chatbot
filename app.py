import os
import random
import time

import streamlit as st
from google import genai
from google.genai import types
from google.genai import errors
from dotenv import load_dotenv

from system_prompt import SYSTEM_PROMPT
from config import MODEL_ID, MAX_TOKENS

load_dotenv()
st.set_page_config(page_title="Inam Medical Chat Bot", page_icon="\U0001FA7A")

# Intro splash (landing card -> walk animation -> welcome animation), ported
# from index.html's JS-timer version to Streamlit session-state + time.sleep
# staging, since a deployed app has no separate localhost server to iframe
# into and st.components.v1.html can't cover the full page. Plays once per
# browser session; skipped entirely once "done".
WALK_SECONDS = 3.6
WELCOME_SECONDS = 2.4
CONFETTI_EMOJI = ["\U0001F389", "✨", "\U0001F499", "\U0001FA7A", "\U0001F38A", "\U0001F49A", "⭐"]

# The intro is rendered in Streamlit's own normal element flow (not a
# position:fixed overlay div) — an earlier version used a fixed full-page div
# for the visual "card", which visually looked right but sat in front of the
# real st.button in stacking order and silently swallowed all clicks. Instead,
# style Streamlit's actual containers (stAppViewContainer / stMainBlockContainer)
# so the intro content and the real button share one flow and one click target.
def _intro_container_css(background):
    return f"""
    <style>
      [data-testid="stHeader"] {{ display: none; }}
      [data-testid="stToolbar"] {{ display: none; }}
      [data-testid="stStatusWidget"] {{ display: none; }}
      [data-testid="stDecoration"] {{ display: none; }}
      [data-testid="stAppViewContainer"] {{ background: {background}; padding: 0; }}
      [data-testid="stMainBlockContainer"] {{
        min-height: 100vh; padding: 0 !important; margin: 0 !important; max-width: 100% !important;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center; position: relative; overflow: hidden;
      }}
      [data-testid="stVerticalBlock"] {{
        align-items: center !important; justify-content: center !important; height: 100%;
      }}
      html, body {{ overflow: hidden; }}
      .intro-card {{
        text-align: center; padding: 2.5rem 3rem; border-radius: 12px;
        background: #1e293b; box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        max-width: 420px; margin: 0 auto;
      }}
      .intro-card h1 {{ font-size: 1.4rem; margin: 0 0 0.5rem; color: #e2e8f0; }}
      .intro-card p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }}
      div[data-testid="stButton"] button {{
        padding: 0.75rem 2rem; background: #2563eb; color: white; border: none;
        border-radius: 8px; font-weight: 700; font-size: 1.1rem; letter-spacing: 0.03em;
      }}
      div[data-testid="stButton"] button:hover {{ background: #1d4ed8; color: white; }}
      .intro-credit {{
        text-align: center; font-size: clamp(1.5rem, 4vw, 2.5rem); font-weight: 800;
        letter-spacing: 0.02em; color: #e2e8f0; opacity: 0.5; padding: 0 1rem 1.5rem;
        max-width: 900px; margin: 0 auto;
      }}
      .intro-scene {{
        position: relative; width: 90%; max-width: 900px; height: 160px;
        border-bottom: 3px solid #334155; margin: 0 auto;
      }}
      .intro-walker {{ position: absolute; bottom: 8px; left: -8%; font-size: 3.5rem; animation: intro-walk 3.5s ease-in-out forwards; }}
      .intro-walker-sprite {{ display: inline-block; transform: scaleX(-1); animation: intro-bob 0.5s ease-in-out infinite; }}
      .intro-hospital {{ position: absolute; bottom: 0; right: 4%; font-size: 4.5rem; }}
      @keyframes intro-walk {{ 0% {{ left: -8%; }} 95% {{ left: 82%; }} 100% {{ left: 84%; }} }}
      @keyframes intro-bob {{ 0%, 100% {{ transform: scaleX(-1) translateY(0); }} 50% {{ transform: scaleX(-1) translateY(-6px); }} }}
      .intro-doctor {{ font-size: clamp(3rem, 8vw, 5.5rem); text-align: center; margin-bottom: 0.25rem; animation: intro-doctor-bounce 1.8s ease-in-out infinite; }}
      @keyframes intro-doctor-bounce {{ 0%, 100% {{ transform: translateY(0) rotate(-3deg); }} 50% {{ transform: translateY(-10px) rotate(3deg); }} }}
      .intro-welcome-text {{
        font-size: clamp(2rem, 6vw, 4rem); font-weight: 800; text-align: center; padding: 0 1rem;
        max-width: 900px; margin: 0 auto;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #34d399, #38bdf8);
        background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: intro-pop-in 0.6s cubic-bezier(.34, 1.56, .64, 1) both,
                   intro-float-text 2.2s ease-in-out 0.6s infinite,
                   intro-shimmer 3s linear infinite;
      }}
      @keyframes intro-pop-in {{ 0% {{ transform: scale(0.3); opacity: 0; }} 70% {{ transform: scale(1.12); opacity: 1; }} 100% {{ transform: scale(1); opacity: 1; }} }}
      @keyframes intro-float-text {{ 0%, 100% {{ translate: 0 0; }} 50% {{ translate: 0 -10px; }} }}
      @keyframes intro-shimmer {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 300% 50%; }} }}
      .intro-confetti-piece {{ position: absolute; bottom: -8%; font-size: 1.9rem; opacity: 0; animation: intro-rise 2.6s ease-in forwards; }}
      @keyframes intro-rise {{ 0% {{ transform: translateY(0) rotate(0deg); opacity: 0; }} 12% {{ opacity: 1; }} 100% {{ transform: translateY(-480px) rotate(360deg); opacity: 0; }} }}
    </style>
    """


def _render_confetti():
    pieces = ""
    for i in range(14):
        emoji = CONFETTI_EMOJI[i % len(CONFETTI_EMOJI)]
        left = random.uniform(5, 95)
        delay = random.uniform(0, 0.8)
        pieces += (
            f'<span class="intro-confetti-piece" '
            f'style="left:{left:.1f}%; animation-delay:{delay:.2f}s;">{emoji}</span>'
        )
    return pieces


if "intro_stage" not in st.session_state:
    st.session_state.intro_stage = "landing"

if st.session_state.intro_stage != "done":
    # Streamlit only prunes a widget that an earlier *completed* run produced
    # once the current run itself finishes — so a widget key simply dropped
    # mid-run (e.g. no longer calling st.button once we leave the landing
    # stage) stays visible on screen for as long as this run keeps going,
    # which is the entire multi-second sleep() below. Re-emitting st.button
    # with the *same* key on every stage (just hidden via CSS once we're past
    # landing) keeps it a live, continuously-updated element instead, so nothing
    # is ever "dropped" for Streamlit to defer cleaning up. It can only be
    # called once per run (a duplicate key in the same run is an error), so it's
    # rendered a single time per run, outside the walk/welcome content swap.
    intro_slot = st.empty()
    button_slot = st.empty()

    def _render_med_tech_button(show):
        with button_slot.container():
            st.markdown(
                f'<style>div[data-testid="stButton"] {{ display: {"revert" if show else "none"}; }}</style>',
                unsafe_allow_html=True,
            )
            _, center, _ = st.columns([1, 1, 1])
            with center:
                return st.button("MED TECH", key="med_tech_btn")

    if st.session_state.intro_stage == "landing":
        st.markdown(_intro_container_css("#0f172a"), unsafe_allow_html=True)
        with intro_slot.container():
            st.markdown(
                '<div class="intro-card">'
                "<h1>\U0001FA7A Inam Medical Chat Bot</h1>"
                "<p>Press the button below to continue to the chatbot.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        if _render_med_tech_button(show=True):
            st.session_state.intro_stage = "walk"
            st.rerun()

    else:
        # Walk and welcome run back-to-back within a single script execution
        # (no st.rerun() between them).
        st.markdown(_intro_container_css("#0f172a"), unsafe_allow_html=True)
        with intro_slot.container():
            st.markdown(
                '<div class="intro-credit">Chatbot made by Inam Kunwar</div>'
                '<div class="intro-scene">'
                '<div class="intro-walker"><span class="intro-walker-sprite">\U0001F6B6</span></div>'
                '<div class="intro-hospital">\U0001F3E5</div>'
                "</div>",
                unsafe_allow_html=True,
            )
        _render_med_tech_button(show=False)
        time.sleep(WALK_SECONDS)

        st.markdown(
            _intro_container_css(
                "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 55%, #dbeafe 100%)"
            ),
            unsafe_allow_html=True,
        )
        with intro_slot.container():
            st.markdown(
                '<div class="intro-doctor">\U0001F9D1‍⚕️</div>'
                '<div class="intro-welcome-text">Welcome to Inam Medical Chat Bot</div>'
                + _render_confetti(),
                unsafe_allow_html=True,
            )
        time.sleep(WELCOME_SECONDS)

        intro_slot.empty()
        button_slot.empty()
        st.session_state.intro_stage = "done"
        st.rerun()

    st.stop()

api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error(
        "GEMINI_API_KEY is not set. Copy .env.example to .env, add your key, "
        "and restart the app."
    )
    st.stop()

client = genai.Client(api_key=api_key)

st.title("Inam Medical Chat Bot")

# Rendered on every rerun (Streamlit reruns the whole script each interaction),
# so this stays visible throughout the conversation, not just at the end of a reply.
st.warning(
    "This tool provides general informational guidance only and is **not** a "
    "substitute for professional medical advice, diagnosis, or treatment. Always "
    "consult a qualified healthcare provider. In an emergency, call your local "
    "emergency number.",
    icon="⚠️",
)

if "messages" not in st.session_state:
    # Gemini roles are "user" / "model" (not "assistant").
    # Each entry: {"role": "user"|"model", "parts": [{"type": "text", "text": ...} |
    #                                                 {"type": "image", "mime_type": ..., "data": bytes}]}
    st.session_state.messages = []

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

for msg in st.session_state.messages:
    display_role = "assistant" if msg["role"] == "model" else "user"
    with st.chat_message(display_role):
        for part in msg["parts"]:
            if part["type"] == "text":
                st.markdown(part["text"])
            elif part["type"] == "image":
                st.caption("(uploaded image)")

uploaded_image = st.file_uploader(
    "Attach a photo (optional)",
    type=["png", "jpg", "jpeg", "webp"],
    key=f"uploader_{st.session_state.uploader_key}",
)
user_text = st.chat_input("Describe your symptoms...")

if user_text:
    parts = []
    if uploaded_image is not None:
        parts.append(
            {
                "type": "image",
                "mime_type": uploaded_image.type or "image/jpeg",
                "data": uploaded_image.getvalue(),
            }
        )
    parts.append({"type": "text", "text": user_text})

    st.session_state.messages.append({"role": "user", "parts": parts})

    with st.chat_message("user"):
        if uploaded_image is not None:
            st.image(uploaded_image)
        st.markdown(user_text)

    contents = []
    for msg in st.session_state.messages:
        api_parts = []
        for part in msg["parts"]:
            if part["type"] == "text":
                api_parts.append(types.Part.from_text(text=part["text"]))
            elif part["type"] == "image":
                api_parts.append(
                    types.Part.from_bytes(data=part["data"], mime_type=part["mime_type"])
                )
        contents.append(types.Content(role=msg["role"], parts=api_parts))

    with st.chat_message("assistant"):
        try:
            def stream_response():
                for chunk in client.models.generate_content_stream(
                    model=MODEL_ID,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=MAX_TOKENS,
                    ),
                ):
                    if chunk.text:
                        yield chunk.text

            assistant_text = st.write_stream(stream_response())
            st.session_state.messages.append(
                {"role": "model", "parts": [{"type": "text", "text": assistant_text}]}
            )

        except errors.ClientError as e:
            if e.code == 401 or (e.code == 400 and "api key not valid" in (e.message or "").lower()):
                st.error("Invalid API key. Check your GEMINI_API_KEY value.")
            elif e.code == 429:
                st.error("Rate limited by the Gemini API — please wait and try again.")
            else:
                st.error(f"API error ({e.code}): {e.message}")
        except errors.ServerError as e:
            st.error(f"Gemini API server error ({e.code}): {e.message}")
        except errors.APIError as e:
            st.error(f"API error: {e.message}")

    # Bump the uploader's key so the same image isn't silently re-attached
    # to the next message after a successful send.
    if uploaded_image is not None:
        st.session_state.uploader_key += 1
        st.rerun()
