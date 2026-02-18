from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

import librosa
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import (
    CORS_ORIGINS,
    MAX_LISTEN_DURATION,
    RECOGNITION_INTERVAL,
    RECOGNITION_WINDOW,
    SAMPLE_RATE,
)
from backend.analyzer import analyze_song
from backend.database import Database
from backend.fingerprint import find_match, generate_fingerprints
from backend.recognizer import recognize_with_ai, is_configured as ai_is_configured, get_provider_name
from backend import acrcloud

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Musica", version="1.0.0", description="Shazam-like music recognition API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db: Database | None = None


@app.on_event("startup")
async def startup() -> None:
    global db
    db = Database()
    stats = db.get_stats()
    acr_status = "ACRCloud: ready" if acrcloud.is_configured() else "ACRCloud: not configured"
    ai_status = f"AI: {get_provider_name()}" if ai_is_configured() else "AI: not configured"
    print(f"\U0001f3b5 Musica ready - {stats['songs']} songs, {stats['fingerprints']:,} fingerprints | {acr_status} | {ai_status}")


@app.on_event("shutdown")
async def shutdown() -> None:
    if db:
        db.close()


# ── WebSocket: real-time recognition ─────────────────────────────────────────

@app.websocket("/ws/recognize")
async def ws_recognize(ws: WebSocket) -> None:
    await ws.accept()

    client_sr: int = 44100
    audio_chunks: list[np.ndarray] = []
    total_samples: int = 0
    last_process_at: float = 0.0  # duration (s) when we last ran recognition
    ai_called: bool = False  # Track if AI has been called (call only once)

    try:
        while True:
            msg = await ws.receive()

            # ── Client disconnected ──────────────────────────────────────
            if msg["type"] == "websocket.disconnect":
                break

            # ── Text message (JSON control frame) ────────────────────────
            if "text" in msg:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "config":
                    client_sr = int(data.get("sampleRate", 44100))
                elif data.get("type") == "stop":
                    break
                continue

            # ── Binary message (PCM Float32 audio) ───────────────────────
            if "bytes" in msg:
                chunk = np.frombuffer(msg["bytes"], dtype=np.float32).copy()
                audio_chunks.append(chunk)
                total_samples += len(chunk)

                duration = total_samples / client_sr

                # Status heartbeat
                await ws.send_json({"status": "listening", "duration": round(duration, 1)})

                # ACRCloud recognition: first attempt at 12s, retry at 25s
                should_try_acr = (
                    not ai_called
                    and acrcloud.is_configured()
                    and (
                        (duration >= 12 and last_process_at < 12)
                        or (duration >= 25 and last_process_at < 25)
                    )
                )

                if not ai_called and duration >= 12 and not acrcloud.is_configured():
                    await ws.send_json({
                        "status": "error",
                        "message": "ACRCloud not configured. Set ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET in .env",
                    })
                    break

                if should_try_acr:
                    last_process_at = duration
                    await ws.send_json({"status": "analyzing"})
                    audio_all = np.concatenate(audio_chunks)
                    result = await asyncio.to_thread(
                        acrcloud.recognize, audio_all, client_sr
                    )
                    if result:
                        ai_called = True
                        # Enrich with AI analysis if available
                        if ai_is_configured():
                            try:
                                enriched = await asyncio.to_thread(
                                    _enrich_with_ai_analysis, result, audio_all, client_sr
                                )
                                if enriched:
                                    result = enriched
                            except Exception:
                                pass
                        await ws.send_json(result)
                        break
                    elif duration >= 25:
                        # Second attempt also failed — give up
                        ai_called = True
                        await ws.send_json({
                            "status": "no_match",
                            "message": "Could not identify the song. Try again with clearer audio.",
                        })
                        break

    except Exception as exc:
        try:
            await ws.send_json({"status": "error", "message": str(exc)})
        except Exception:
            pass


def _recognize_audio(audio: np.ndarray, sr: int) -> dict | None:
    """Synchronous helper — AI recognition first, fingerprint fallback."""

    # ── Primary: AI recognition (identifies any song) ────────────────
    if ai_is_configured():
        result = recognize_with_ai(audio, sr)
        if result:
            return {"status": "match_found", **result}

    # ── Fallback: local fingerprint matching ─────────────────────────
    fps = generate_fingerprints(audio, sr)
    if not fps:
        return None
    song_id, confidence = find_match(fps, db)  # type: ignore[arg-type]
    if song_id is None:
        return None
    song = db.get_song(song_id)  # type: ignore[union-attr]
    if song is None:
        return None
    song.pop("file_hash", None)
    song.pop("created_at", None)

    try:
        analysis = analyze_song(
            title=song["title"],
            artist=song["artist"],
            album=song.get("album", ""),
            audio=audio,
            sr=sr,
        )
    except Exception:
        analysis = {}

    return {
        "status": "match_found",
        "song": song,
        "confidence": round(confidence, 1),
        "analysis": analysis,
        "source": "fingerprint",
    }


def _recognize_audio_fingerprint_only(audio: np.ndarray, sr: int) -> dict | None:
    """Synchronous helper — fingerprint matching only (no AI calls)."""
    fps = generate_fingerprints(audio, sr)
    if not fps:
        return None
    song_id, confidence = find_match(fps, db)  # type: ignore[arg-type]
    if song_id is None:
        return None
    song = db.get_song(song_id)  # type: ignore[union-attr]
    if song is None:
        return None
    song.pop("file_hash", None)
    song.pop("created_at", None)

    return {
        "status": "match_found",
        "song": song,
        "confidence": round(confidence, 1),
        "analysis": {},
        "source": "fingerprint",
    }


def _recognize_audio_ai_only(audio: np.ndarray, sr: int) -> dict | None:
    """Synchronous helper — AI recognition only (called once as final attempt)."""
    if not is_configured():
        return None
    result = recognize_with_ai(audio, sr)
    if result:
        return {"status": "match_found", **result}
    return None


def _enrich_with_ai_analysis(result: dict, audio: np.ndarray, sr: int) -> dict | None:
    """Enrich fingerprint result with AI-generated analysis."""
    try:
        song = result.get("song", {})
        analysis = analyze_song(
            title=song.get("title", ""),
            artist=song.get("artist", ""),
            album=song.get("album", ""),
            audio=audio,
            sr=sr,
        )
        result["analysis"] = analysis
        return result
    except Exception:
        return None


# ── REST: file upload recognition ────────────────────────────────────────────

@app.post("/api/recognize")
async def recognize_upload(file: UploadFile = File(...)) -> JSONResponse:
    """Upload an audio file and identify the song."""
    suffix = Path(file.filename or "audio.wav").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        audio, sr = librosa.load(tmp.name, sr=SAMPLE_RATE, mono=True)

    result = await asyncio.to_thread(_recognize_audio, audio, sr)
    if result:
        return JSONResponse(result)
    return JSONResponse({"status": "no_match", "message": "No matching song found"})


# ── REST: song management ───────────────────────────────────────────────────

@app.post("/api/songs")
async def add_song(
    file: UploadFile = File(...),
    title: str = Form(...),
    artist: str = Form("Unknown"),
    album: str = Form(""),
) -> JSONResponse:
    """Add a new song to the fingerprint database."""
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()

    if db.song_exists(file_hash):  # type: ignore[union-attr]
        return JSONResponse({"status": "exists", "message": "Song already indexed"}, status_code=409)

    suffix = Path(file.filename or "audio.wav").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        audio, sr = librosa.load(tmp.name, sr=SAMPLE_RATE, mono=True)

    duration = float(len(audio) / sr)
    song_id = db.add_song(title, artist, album, duration, file_hash)  # type: ignore[union-attr]
    if song_id is None:
        return JSONResponse({"status": "error", "message": "Failed to add song"}, status_code=500)

    fps = generate_fingerprints(audio, sr)
    db.add_fingerprints(song_id, fps)  # type: ignore[union-attr]

    return JSONResponse({
        "status": "ok",
        "song_id": song_id,
        "fingerprints": len(fps),
        "duration": round(duration, 1),
    })


@app.get("/api/songs")
async def list_songs() -> JSONResponse:
    return JSONResponse(db.get_all_songs())  # type: ignore[union-attr]


@app.delete("/api/songs/{song_id}")
async def remove_song(song_id: int) -> JSONResponse:
    song = db.get_song(song_id)  # type: ignore[union-attr]
    if not song:
        return JSONResponse({"status": "error", "message": "Song not found"}, status_code=404)
    db.delete_song(song_id)  # type: ignore[union-attr]
    return JSONResponse({"status": "ok", "message": f"Deleted '{song['title']}'"})


@app.get("/api/stats")
async def stats() -> JSONResponse:
    return JSONResponse(db.get_stats())  # type: ignore[union-attr]


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ── Serve React frontend build (production) ─────────────────────────────────

_frontend_build = Path(__file__).resolve().parent.parent / "frontend" / "build"
if _frontend_build.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_build), html=True), name="frontend")
