"""Musica - ACRCloud music recognition.

Uses ACRCloud's official Python SDK (pyacrcloud) with native fingerprint
extraction for accurate audio identification -- same technology as Shazam.

Setup:
1. Create free account at https://console.acrcloud.com/
2. Create a project (Audio & Music Recognition)
3. Copy Host, Access Key, and Access Secret
4. Set in .env:
   ACRCLOUD_HOST=identify-eu-west-1.acrcloud.com
   ACRCLOUD_ACCESS_KEY=your_access_key
   ACRCLOUD_ACCESS_SECRET=your_access_secret
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

# Official ACRCloud SDK
from acrcloud.recognizer import ACRCloudRecognizer, ACRCloudRecognizeType

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# -- Configuration ------------------------------------------------------------

ACRCLOUD_HOST = os.getenv("ACRCLOUD_HOST", "")
ACRCLOUD_ACCESS_KEY = os.getenv("ACRCLOUD_ACCESS_KEY", "")
ACRCLOUD_ACCESS_SECRET = os.getenv("ACRCLOUD_ACCESS_SECRET", "")

# Lazy-initialized recognizer instance
_recognizer: ACRCloudRecognizer | None = None


def is_configured() -> bool:
    """True if ACRCloud credentials are set."""
    return bool(ACRCLOUD_HOST and ACRCLOUD_ACCESS_KEY and ACRCLOUD_ACCESS_SECRET)


def _get_recognizer() -> ACRCloudRecognizer:
    """Get or create the ACRCloud recognizer instance."""
    global _recognizer
    if _recognizer is None:
        config = {
            "host": ACRCLOUD_HOST,
            "access_key": ACRCLOUD_ACCESS_KEY,
            "access_secret": ACRCLOUD_ACCESS_SECRET,
            "recognize_type": ACRCloudRecognizeType.ACR_OPT_REC_BOTH,
            "debug": False,
            "timeout": 10,
        }
        _recognizer = ACRCloudRecognizer(config)
    return _recognizer


def _audio_to_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    """Convert numpy audio to WAV bytes for the SDK."""
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    # Skip first 0.5s of mic startup noise
    skip_samples = min(int(sr * 0.5), len(audio) // 4)
    audio = audio[skip_samples:]

    # Peak-normalize to ensure good signal level
    peak = np.max(np.abs(audio))
    if peak > 0.001:
        audio = audio / peak * 0.95
        print(f"[acrcloud] Audio normalized: peak was {peak:.4f}, now 0.95")
    else:
        print(f"[acrcloud] WARNING: Audio is nearly silent (peak={peak:.6f})")

    duration = len(audio) / sr
    print(f"[acrcloud] Audio: {duration:.1f}s, {len(audio)} samples @ {sr} Hz")

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def recognize(audio: np.ndarray, sr: int) -> dict[str, Any] | None:
    """
    Identify a song using ACRCloud's official SDK.

    Uses recognize_by_filebuffer which:
    1. Generates audio fingerprint with native acrcloud_extr_tool
    2. Generates humming fingerprint as fallback
    3. Sends both to ACRCloud API for matching

    Returns a result dict or None if not identified.
    """
    if not is_configured():
        print("[acrcloud] Not configured - set ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET")
        return None

    wav_bytes = _audio_to_wav_bytes(audio, sr)
    recognizer = _get_recognizer()

    # Use the official SDK method -- it handles fingerprint generation,
    # API signing, multipart encoding, and submission correctly
    print(f"[acrcloud] Sending {len(wav_bytes)} bytes to SDK recognize_by_filebuffer...")
    result_str = recognizer.recognize_by_filebuffer(wav_bytes, 0)

    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[acrcloud] Failed to parse response: {e}")
        print(f"[acrcloud] Raw response: {result_str[:500] if result_str else 'None'}")
        return None

    status = data.get("status", {})
    code = status.get("code")
    msg = status.get("msg", "")
    print(f"[acrcloud] Response status: {code} - {msg}")

    if code != 0:
        print(f"[acrcloud] No match: {msg}")
        return None

    # Parse the music metadata - prefer fingerprint matches over humming
    metadata = data.get("metadata", {})
    music_list = metadata.get("music", [])
    humming_list = metadata.get("humming", [])

    if music_list:
        match = music_list[0]
        print(f"[acrcloud] Got {len(music_list)} fingerprint match(es)")
    elif humming_list:
        match = humming_list[0]
        hum_score = match.get("score", 0)
        print(f"[acrcloud] Got {len(humming_list)} humming match(es), top score: {hum_score}")
        if hum_score < 40:
            print(f"[acrcloud] Humming score too low ({hum_score}), rejecting")
            return None
    else:
        available_keys = list(metadata.keys())
        print(f"[acrcloud] Status 0 but no matches. Metadata keys: {available_keys}")
        print(f"[acrcloud] Full response: {json.dumps(data, indent=2)[:500]}")
        return None

    # Extract song info
    title = match.get("title", "Unknown")
    artists = match.get("artists", [{}])
    artist = artists[0].get("name", "Unknown") if artists else "Unknown"
    album = match.get("album", {}).get("name", "")
    genres = match.get("genres", [{}])
    genre = genres[0].get("name", "") if genres else ""
    release_date = match.get("release_date", "")
    score = match.get("score", 0)
    duration_ms = match.get("duration_ms", 0)
    if isinstance(duration_ms, str):
        try:
            duration_ms = int(duration_ms)
        except ValueError:
            duration_ms = 0
    label = match.get("label", "")

    # External metadata (Spotify, YouTube, etc.)
    external = match.get("external_metadata", {})
    spotify = external.get("spotify", {})
    youtube = external.get("youtube", {})

    # Build artwork URL from Spotify if available
    artwork_url = ""
    if spotify and spotify.get("album", {}).get("images"):
        artwork_url = spotify["album"]["images"][0].get("url", "")

    # Spotify track URL
    spotify_url = ""
    if spotify and spotify.get("track", {}).get("id"):
        spotify_url = f"https://open.spotify.com/track/{spotify['track']['id']}"

    # YouTube URL
    youtube_url = ""
    if youtube and youtube.get("vid"):
        youtube_url = f"https://www.youtube.com/watch?v={youtube['vid']}"

    print(f"[acrcloud] Identified: {title} by {artist} (score: {score})")

    return {
        "status": "match_found",
        "song": {
            "title": title,
            "artist": artist,
            "album": album,
            "genre": genre,
            "release_date": release_date,
            "duration": round(duration_ms / 1000, 1) if duration_ms else 0,
            "label": label,
            "artwork_url": artwork_url,
            "spotify_url": spotify_url,
            "youtube_url": youtube_url,
        },
        "confidence": round(score, 1),
        "source": "acrcloud",
    }
