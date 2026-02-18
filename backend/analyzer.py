"""Musica — AI-powered song analysis.

After the fingerprint engine identifies a song, this module produces a rich
analysis including mood, genre blend, emotional explanation, lyrics meaning,
and similar-vibes recommendations.

Supports two modes:
  1. **OpenAI / compatible API** — set MUSICA_LLM_API_KEY env var
  2. **Audio-feature heuristic** — zero-dependency fallback using librosa
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Any

import librosa
import numpy as np

# ── LLM configuration ───────────────────────────────────────────────────────

LLM_API_KEY = os.getenv("MUSICA_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("MUSICA_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("MUSICA_LLM_MODEL", "gpt-4o-mini")

# ── Public API ───────────────────────────────────────────────────────────────


GEMINI_API_KEY = os.getenv("MUSICA_GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("MUSICA_GEMINI_MODEL", "gemini-2.5-flash")


def analyze_song(
    title: str,
    artist: str,
    album: str = "",
    audio: np.ndarray | None = None,
    sr: int = 22050,
) -> dict[str, Any]:
    """Return an AI analysis dict for a recognized song.

    Tries Gemini first, then OpenAI, then heuristic fallback.
    """
    # Try Gemini analysis (richer, free tier)
    if GEMINI_API_KEY:
        try:
            return _gemini_analysis(title, artist, album)
        except Exception as e:
            print(f"[analyzer] Gemini analysis failed: {e}")

    # Try LLM-based analysis (OpenAI)
    if LLM_API_KEY:
        try:
            return _llm_analysis(title, artist, album)
        except Exception:
            pass

    # Heuristic path -- works offline, uses audio features
    return _heuristic_analysis(title, artist, album, audio, sr)


# ── LLM path ────────────────────────────────────────────────────────────────

def _llm_analysis(title: str, artist: str, album: str) -> dict[str, Any]:
    """Call an OpenAI-compatible chat endpoint for song analysis."""
    import urllib.request

    prompt = textwrap.dedent(f"""\
        You are a music expert. Analyze this song and return ONLY valid JSON
        (no markdown fences, no extra text).

        Song: "{title}"
        Artist: "{artist}"
        Album: "{album}"

        Return this exact JSON structure:
        {{
          "mood": "short mood description (2-4 words)",
          "genre_blend": "Genre1 + Genre2",
          "emotional_explanation": "1-2 sentences explaining the emotional feel",
          "lyrics_meaning": "1-2 sentences about the lyrical themes",
          "similar_vibes": ["Song1 - Artist1", "Song2 - Artist2", "Song3 - Artist3"]
        }}
    """)

    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300,
    }).encode()

    req = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    raw = data["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


# ── Gemini path ──────────────────────────────────────────────────────────────

def _gemini_analysis(title: str, artist: str, album: str) -> dict[str, Any]:
    """Call Gemini API for rich song analysis."""
    import urllib.request

    prompt = textwrap.dedent(f"""\
        You are a music expert and cultural analyst. Analyze this song in detail.

        Song: "{title}"
        Artist: "{artist}"
        Album: "{album or 'Unknown'}" 

        Return ONLY valid JSON (no markdown fences, no extra text) with this structure:
        {{
          "mood": "2-4 word mood description (e.g. Energetic and powerful, Melancholic and deep)",
          "genre_blend": "Primary Genre + Secondary Genre (e.g. Hip-Hop + Trap, Pop + R&B, Rock + Alternative)",
          "category": "One of: Rap, Pop, Rock, R&B, Electronic, Country, Jazz, Latin, Reggaeton, Folk, Classical, Metal, Indie, K-Pop, Afrobeats, Dancehall, Funk, Soul, Blues, World Music, Turbofolk, Tallava, Manele",
          "language": "Language the song is sung in (e.g. English, Albanian, Spanish, Turkish)",
          "emotional_explanation": "2-3 sentences about the emotional feel and musical style of the song",
          "lyrics_meaning": "2-3 sentences about what the song is about - the story, themes, and message",
          "fun_fact": "One interesting fact about this song or artist",
          "similar_vibes": ["Song1 - Artist1", "Song2 - Artist2", "Song3 - Artist3"]
        }}
    """)

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }).encode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    result = json.loads(raw)
    print(f"[analyzer] Gemini analysis: {result.get('category', '?')} / {result.get('mood', '?')}")
    return result


# ── Heuristic (offline) path ────────────────────────────────────────────────

# Mood / genre maps derived from audio features
_ENERGY_MOODS = [
    (0.2, "Calm and peaceful"),
    (0.4, "Mellow and relaxed"),
    (0.6, "Upbeat and groovy"),
    (0.8, "Energetic and driving"),
    (1.0, "Intense and powerful"),
]

_VALENCE_LABELS = [
    (0.25, "melancholic"),
    (0.50, "bittersweet"),
    (0.75, "uplifting"),
    (1.00, "euphoric"),
]

_TEMPO_GENRES = [
    (80, "Ambient"),
    (100, "R&B"),
    (120, "Pop"),
    (135, "Dance"),
    (150, "Electronic"),
    (999, "Drum & Bass"),
]

_SPECTRAL_GENRES = [
    (2000, "Jazz"),
    (3000, "Soul"),
    (4500, "Pop"),
    (6000, "Rock"),
    (9999, "Electronic"),
]

_SIMILAR_DB: dict[str, list[str]] = {
    "Pop": ["Shape of You - Ed Sheeran", "Blinding Lights - The Weeknd", "Levitating - Dua Lipa"],
    "Rock": ["Bohemian Rhapsody - Queen", "Smells Like Teen Spirit - Nirvana", "Back in Black - AC/DC"],
    "Electronic": ["Midnight City - M83", "Strobe - Deadmau5", "Around the World - Daft Punk"],
    "Dance": ["Don't Start Now - Dua Lipa", "One More Time - Daft Punk", "Titanium - David Guetta"],
    "R&B": ["Blinding Lights - The Weeknd", "Kiss It Better - Rihanna", "Best Part - Daniel Caesar"],
    "Jazz": ["Take Five - Dave Brubeck", "So What - Miles Davis", "Fly Me to the Moon - Frank Sinatra"],
    "Soul": ["Superstition - Stevie Wonder", "Ain't No Sunshine - Bill Withers", "Respect - Aretha Franklin"],
    "Ambient": ["Weightless - Marconi Union", "An Ending - Brian Eno", "Intro - The xx"],
    "Drum & Bass": ["Hold Your Colour - Pendulum", "Witchcraft - Pendulum", "Compression - Sub Focus"],
}


def _heuristic_analysis(
    title: str,
    artist: str,
    album: str,
    audio: np.ndarray | None,
    sr: int,
) -> dict[str, Any]:
    """Derive mood / genre from audio features when no LLM is available."""

    # Defaults when no audio is provided
    if audio is None or len(audio) < sr:
        return {
            "mood": "Vibrant and catchy",
            "genre_blend": "Pop + Contemporary",
            "emotional_explanation": (
                f'"{title}" by {artist} carries a distinctive musical identity '
                "that resonates with listeners across genres."
            ),
            "lyrics_meaning": "Themes of personal expression and emotional connection.",
            "similar_vibes": ["Blinding Lights - The Weeknd", "Levitating - Dua Lipa", "Heat Waves - Glass Animals"],
        }

    # ── Extract features ─────────────────────────────────────────────────
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    # Tempo
    tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
    tempo_val = float(np.atleast_1d(tempo)[0])

    # RMS energy (0-1 normalised)
    rms = float(np.mean(librosa.feature.rms(y=audio)))
    energy = min(rms / 0.15, 1.0)

    # Spectral centroid (brightness)
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)))

    # Chroma — rough major/minor proxy  (valence-ish)
    chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
    chroma_std = float(np.std(chroma))
    valence = min(chroma_std / 0.35, 1.0)

    # Spectral contrast → timbral richness
    contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
    richness = float(np.mean(contrast)) / 30.0  # normalise

    # ── Derive labels ────────────────────────────────────────────────────
    mood_base = next(m for thr, m in _ENERGY_MOODS if energy <= thr)
    valence_label = next(v for thr, v in _VALENCE_LABELS if valence <= thr)
    mood = f"{mood_base}, {valence_label}"

    genre_tempo = next(g for thr, g in _TEMPO_GENRES if tempo_val <= thr)
    genre_spectral = next(g for thr, g in _SPECTRAL_GENRES if centroid <= thr)
    if genre_tempo == genre_spectral:
        genre_blend = f"{genre_tempo} + Contemporary"
    else:
        genre_blend = f"{genre_tempo} + {genre_spectral}"

    if energy > 0.6:
        emo = (
            f"The driving {tempo_val:.0f} BPM tempo and bright instrumentation "
            f"create a {valence_label} energy that pulls you in."
        )
    elif energy > 0.3:
        emo = (
            f"A mid-tempo groove at {tempo_val:.0f} BPM gives a {valence_label} "
            "feel, balancing movement with introspection."
        )
    else:
        emo = (
            f"The gentle {tempo_val:.0f} BPM pulse and warm textures "
            f"evoke a {valence_label}, contemplative atmosphere."
        )

    lyrics = (
        f'"{title}" by {artist} explores themes of '
        + ("emotional intensity and self-discovery." if energy > 0.5
           else "reflection, longing, and inner feeling.")
    )

    # Pick similar vibes from the closest genre
    primary = genre_tempo if genre_tempo in _SIMILAR_DB else genre_spectral
    similar = list(_SIMILAR_DB.get(primary, _SIMILAR_DB["Pop"]))
    # Remove the actual song if it's in the list
    similar = [s for s in similar if title.lower() not in s.lower()][:3]
    if len(similar) < 3:
        similar += _SIMILAR_DB["Pop"]
        similar = list(dict.fromkeys(similar))[:3]  # dedupe

    return {
        "mood": mood,
        "genre_blend": genre_blend,
        "emotional_explanation": emo,
        "lyrics_meaning": lyrics,
        "similar_vibes": similar,
        "audio_features": {
            "tempo_bpm": round(tempo_val, 1),
            "energy": round(energy, 2),
            "brightness": round(centroid, 0),
            "valence": round(valence, 2),
        },
    }
