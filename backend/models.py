from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SongInfo(BaseModel):
    id: int
    title: str
    artist: str = "Unknown"
    album: str = ""
    duration: float = 0.0
    artwork_url: str = ""


class AIAnalysis(BaseModel):
    mood: str = ""
    genre_blend: str = ""
    emotional_explanation: str = ""
    lyrics_meaning: str = ""
    similar_vibes: list[str] = []
    audio_features: Optional[dict] = None


class RecognitionResult(BaseModel):
    status: str  # match_found | no_match | error
    song: Optional[SongInfo] = None
    confidence: float = 0.0
    analysis: Optional[AIAnalysis] = None
    message: str = ""


class WSStatus(BaseModel):
    status: str
    duration: float = 0.0
    message: str = ""


class AddSongRequest(BaseModel):
    title: str
    artist: str = "Unknown"
    album: str = ""


class StatsResponse(BaseModel):
    songs: int
    fingerprints: int
