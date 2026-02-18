"""Musica — Audio fingerprinting engine.

Implements a Shazam-style algorithm:
1. Compute a spectrogram (STFT).
2. Detect spectral peaks (local maxima above a threshold).
3. Pair nearby peaks and hash each pair → (hash, time_offset).
4. Match query hashes against the database using offset alignment.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

import librosa
import numpy as np
from scipy.ndimage import maximum_filter

from backend.config import (
    AMPLITUDE_THRESHOLD,
    FAN_OUT,
    FFT_SIZE,
    HOP_LENGTH,
    MAX_TIME_DELTA,
    MIN_MATCH_THRESHOLD,
    MIN_TIME_DELTA,
    PEAK_NEIGHBORHOOD,
    SAMPLE_RATE,
)

if TYPE_CHECKING:
    from backend.database import Database


# ── Public API ───────────────────────────────────────────────────────────────

def generate_fingerprints(
    audio: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> list[tuple[str, int]]:
    """Return a list of (hash_hex, time_offset) fingerprints for *audio*."""
    if len(audio) < sr:  # less than 1 second — too short
        return []

    # Mono / resample
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    if sr != SAMPLE_RATE:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)

    # STFT → magnitude spectrogram (dB)
    S = np.abs(librosa.stft(audio, n_fft=FFT_SIZE, hop_length=HOP_LENGTH))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Find spectral peaks
    peaks = _find_peaks(S_db)
    if len(peaks) < 2:
        return []

    # Generate combinatorial hashes from peak pairs
    return _hash_peaks(peaks)


def find_match(
    query_fps: list[tuple[str, int]],
    db: "Database",
) -> tuple[int | None, float]:
    """Match *query_fps* against the database.

    Returns ``(song_id, confidence)`` or ``(None, 0.0)``.
    """
    if not query_fps:
        return None, 0.0

    # Build hash → [query_offset, …] map
    h2q: dict[str, list[int]] = defaultdict(list)
    for h, off in query_fps:
        h2q[h].append(off)

    unique_hashes = list(h2q.keys())

    # Batch DB lookups (SQLite has a 999-variable limit)
    BATCH = 900
    db_rows: list[tuple[str, int, int]] = []
    for i in range(0, len(unique_hashes), BATCH):
        db_rows.extend(db.get_matches(unique_hashes[i : i + BATCH]))

    if not db_rows:
        return None, 0.0

    # Accumulate offset-deltas per song
    song_deltas: dict[int, list[int]] = defaultdict(list)
    for db_hash, song_id, db_offset in db_rows:
        for q_off in h2q[db_hash]:
            song_deltas[song_id].append(db_offset - q_off)

    # Find the song whose delta histogram has the tallest peak
    best_id: int | None = None
    best_count = 0
    for song_id, deltas in song_deltas.items():
        top_count = Counter(deltas).most_common(1)[0][1]
        if top_count > best_count:
            best_count = top_count
            best_id = song_id

    if best_id is not None and best_count >= MIN_MATCH_THRESHOLD:
        confidence = min(100.0, best_count * 2.0)
        return best_id, confidence

    return None, 0.0


# ── Internal helpers ─────────────────────────────────────────────────────────

def _find_peaks(
    spectrogram: np.ndarray,
    neighborhood: int = PEAK_NEIGHBORHOOD,
    threshold: float = AMPLITUDE_THRESHOLD,
) -> list[tuple[int, int]]:
    """Return ``[(freq_bin, time_frame), …]`` of spectral peaks."""
    local_max = maximum_filter(spectrogram, size=neighborhood)
    mask = (spectrogram == local_max) & (spectrogram > threshold)
    freq_idx, time_idx = np.nonzero(mask)
    # Sort by time, then frequency
    order = np.lexsort((freq_idx, time_idx))
    return list(zip(freq_idx[order].tolist(), time_idx[order].tolist()))


def _hash_peaks(
    peaks: list[tuple[int, int]],
    fan_out: int = FAN_OUT,
) -> list[tuple[str, int]]:
    """Pair each peak with its *fan_out* nearest future neighbours and hash."""
    hashes: list[tuple[str, int]] = []
    n = len(peaks)
    for i in range(n):
        f1, t1 = peaks[i]
        for j in range(1, fan_out + 1):
            if i + j >= n:
                break
            f2, t2 = peaks[i + j]
            dt = t2 - t1
            if MIN_TIME_DELTA <= dt <= MAX_TIME_DELTA:
                raw = f"{f1}|{f2}|{dt}".encode()
                h = hashlib.sha1(raw).hexdigest()[:20]
                hashes.append((h, t1))
    return hashes
