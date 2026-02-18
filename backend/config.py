"""Musica — Configuration settings."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = os.getenv("MUSICA_DB", str(BASE_DIR / "musica.db"))
SONGS_DIR = os.getenv("MUSICA_SONGS_DIR", str(BASE_DIR / "songs"))

# ── Audio Processing ─────────────────────────────────────────────────────────
SAMPLE_RATE = 22050          # Target sample rate for fingerprinting
FFT_SIZE = 4096              # FFT window size
HOP_LENGTH = 2048            # STFT hop length (50% overlap)
PEAK_NEIGHBORHOOD = 20       # Local-max filter size (freq × time)
AMPLITUDE_THRESHOLD = -60    # dB threshold for peak detection

# ── Fingerprint Hashing ──────────────────────────────────────────────────────
FAN_OUT = 15                 # Number of peak-pairs per anchor
MIN_TIME_DELTA = 0           # Minimum frame delta between paired peaks
MAX_TIME_DELTA = 200         # Maximum frame delta between paired peaks

# ── Recognition ──────────────────────────────────────────────────────────────
RECOGNITION_WINDOW = 8       # Seconds of audio needed before first attempt
RECOGNITION_INTERVAL = 3     # Seconds between successive recognition attempts
MIN_MATCH_THRESHOLD = 8      # Minimum aligned hashes for a valid match
MAX_LISTEN_DURATION = 35     # Maximum seconds before giving up

# ── AI Analysis ──────────────────────────────────────────────────────────────
LLM_API_KEY = os.getenv("MUSICA_LLM_API_KEY", "")       # OpenAI / compatible key
LLM_BASE_URL = os.getenv("MUSICA_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("MUSICA_LLM_MODEL", "gpt-4o-mini")

# ── AI Recognition (set at least one) ───────────────────────────────────────
# MUSICA_OPENAI_API_KEY  → GPT-4o audio recognition (falls back to MUSICA_LLM_API_KEY)
# MUSICA_GEMINI_API_KEY  → Gemini 2.0 Flash audio recognition

# ── Server ───────────────────────────────────────────────────────────────────
HOST = os.getenv("MUSICA_HOST", "0.0.0.0")
PORT = int(os.getenv("MUSICA_PORT", "8000"))
CORS_ORIGINS = os.getenv(
    "MUSICA_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")
