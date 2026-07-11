import os

import streamlit as st
from google import genai
from google.genai import types
from google.genai import errors
from dotenv import load_dotenv

from system_prompt import SYSTEM_PROMPT
from config import MODEL_ID, MAX_TOKENS

load_dotenv()
st.set_page_config(page_title="Inam Medical Chat Bot", page_icon="\U0001FA7A")

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
            if e.code == 401:
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
