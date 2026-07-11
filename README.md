# Inam Medical Chat Bot

A conversational assistant for exploring possible causes of symptoms, from text
descriptions and optional photos (e.g. a rash or visible skin condition).

> **Not medical advice.** This tool provides general informational guidance only
> and does not replace an in-person examination by a licensed healthcare
> professional. In a medical emergency, call your local emergency number.

## Setup

```
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Gemini API key:

```
cp .env.example .env
```

Then edit `.env` and set `GEMINI_API_KEY`. Get a key from
[Google AI Studio](https://aistudio.google.com/apikey) — it should start with
`AIzaSy`.

## Run

```
streamlit run app.py
```

## Configuration

The active model and response length are set in `config.py`:

- `MODEL_ID` — defaults to `gemini-3.5-flash`. Swap to `gemini-2.5-flash-lite`
  for a cheaper, still vision-capable alternative, or `gemini-3.1-pro` for
  higher quality.
- `MAX_TOKENS` — response length cap.

The assistant's persona and output format live in `system_prompt.py`, kept
separate from the app logic so it can be edited independently.
