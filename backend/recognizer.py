"""Musica — AI‑powered music recognition.

Sends captured audio directly to an AI model (GPT‑4o or Gemini) which
listens to the audio and identifies the song — just like asking a human
"what song is this?"  One API call returns song ID + rich analysis.

Supported providers (auto‑selected based on which key you set):
  • MUSICA_OPENAI_API_KEY  → GPT‑4o‑audio (default)
  • MUSICA_GEMINI_API_KEY  → Gemini 2.0 Flash
"""

from __future__ import annotations

import base64
import io
import json
import os
import textwrap
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

# Load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ── Configuration ────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("MUSICA_OPENAI_API_KEY", os.getenv("MUSICA_LLM_API_KEY", ""))
OPENAI_MODEL = os.getenv("MUSICA_OPENAI_MODEL", "gpt-4o-audio-preview")

GEMINI_API_KEY = os.getenv("MUSICA_GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("MUSICA_GEMINI_MODEL", "gemini-2.0-flash")

# ── Shared prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert music recognition AI. You will receive an audio clip.
    Listen carefully and identify the song.

    Return ONLY valid JSON (no markdown fences, no extra text) with this structure:
    {
      "identified": true,
      "song": "Song Title",
      "artist": "Artist Name",
      "album": "Album Name (or empty string if unknown)",
      "mood": "2-4 word mood description",
      "genre_blend": "Genre1 + Genre2",
      "emotional_explanation": "1-2 sentences about the emotional feel",
      "lyrics_meaning": "1-2 sentences about lyrical themes",
      "similar_vibes": ["Song1 - Artist1", "Song2 - Artist2", "Song3 - Artist3"]
    }

    If you cannot identify the song, return:
    {"identified": false, "reason": "brief explanation"}
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _audio_to_wav_b64(audio: np.ndarray, sr: int) -> str:
    """Convert numpy audio to base64‑encoded WAV."""
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    # Trim to last 15 seconds to stay within API limits
    max_samples = sr * 15
    if len(audio) > max_samples:
        audio = audio[-max_samples:]
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _parse_ai_response(raw: str) -> dict[str, Any] | None:
    """Parse the JSON from the AI response, stripping markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not data.get("identified"):
        return None
    return data


def _ai_result_to_response(data: dict[str, Any]) -> dict[str, Any]:
    """Convert parsed AI JSON into our standard response format."""
    return {
        "song": {
            "title": data.get("song", "Unknown"),
            "artist": data.get("artist", "Unknown"),
            "album": data.get("album", ""),
            "duration": 0,
            "artwork_url": "",
        },
        "confidence": 90.0,
        "analysis": {
            "mood": data.get("mood", ""),
            "genre_blend": data.get("genre_blend", ""),
            "emotional_explanation": data.get("emotional_explanation", ""),
            "lyrics_meaning": data.get("lyrics_meaning", ""),
            "similar_vibes": data.get("similar_vibes", []),
        },
        "source": "ai",
    }


# ── Public API ───────────────────────────────────────────────────────────────

def recognize_with_ai(audio: np.ndarray, sr: int) -> dict[str, Any] | None:
    """Send audio to AI for song recognition. Returns result dict or None."""
    if OPENAI_API_KEY:
        return _recognize_openai(audio, sr)
    if GEMINI_API_KEY:
        return _recognize_gemini(audio, sr)
    return None


def is_configured() -> bool:
    """True if at least one AI recognition provider has an API key."""
    return bool(OPENAI_API_KEY or GEMINI_API_KEY)


def get_provider_name() -> str:
    if OPENAI_API_KEY:
        return f"openai/{OPENAI_MODEL}"
    if GEMINI_API_KEY:
        return f"gemini/{GEMINI_MODEL}"
    return ""


# ── OpenAI GPT‑4o ────────────────────────────────────────────────────────────

def _recognize_openai(audio: np.ndarray, sr: int) -> dict[str, Any] | None:
    """Use GPT‑4o with audio input to identify a song."""
    audio_b64 = _audio_to_wav_b64(audio, sr)

    body = json.dumps({
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What song is playing in this audio clip? Listen carefully and identify it.",
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_b64,
                            "format": "wav",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[recognizer] OpenAI error: {e}")
        return None

    try:
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"[recognizer] OpenAI unexpected response: {data}")
        return None

    parsed = _parse_ai_response(raw)
    if not parsed:
        return None
    return _ai_result_to_response(parsed)


# ── Google Gemini ────────────────────────────────────────────────────────────

def _recognize_gemini(audio: np.ndarray, sr: int) -> dict[str, Any] | None:
    """Use Gemini with audio input to identify a song."""
    audio_b64 = _audio_to_wav_b64(audio, sr)

    body = json.dumps({
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            _SYSTEM_PROMPT
                            + "\n\nWhat song is playing in this audio clip? "
                            "Listen carefully and identify it."
                        ),
                    },
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": audio_b64,
                        },
                    },
                ],
            },
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 500,
        },
    }).encode()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[recognizer] Gemini error: {e}")
        return None

    try:
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return None

    parsed = _parse_ai_response(raw)
    if not parsed:
        return None
    return _ai_result_to_response(parsed)
