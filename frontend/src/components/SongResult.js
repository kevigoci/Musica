import React from "react";
import "./SongResult.css";

/**
 * Card that displays the recognized song + AI analysis.
 */
export default function SongResult({ song, confidence, analysis, onReset }) {
  if (!song) return null;

  const initial = (song.title || "?")[0].toUpperCase();
  const ai = analysis || {};

  return (
    <div className="result">
      <div className="result-badge">🎯 Match Found</div>

      {/* ── Song identity card ───────────────────────────────────────── */}
      <div className="result-card">
        {song.artwork_url ? (
          <img src={song.artwork_url} alt="Album art" className="result-art" />
        ) : (
          <div className="result-art placeholder">
            <span>{initial}</span>
          </div>
        )}

        <div className="result-info">
          <h2 className="result-title">{song.title}</h2>
          <p className="result-artist">{song.artist}</p>
          {song.album && <p className="result-album">{song.album}</p>}
        </div>
      </div>

      {/* ── Confidence bar ───────────────────────────────────────────── */}
      <div className="confidence">
        <div className="confidence-label">
          <span>Confidence</span>
          <span className="confidence-value">{confidence.toFixed(0)}%</span>
        </div>
        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${Math.min(confidence, 100)}%` }}
          />
        </div>
      </div>

      {/* ── AI Analysis section ──────────────────────────────────────── */}
      {Object.keys(ai).length > 0 && (
        <div className="analysis">
          <h3 className="analysis-heading">
            <span className="analysis-icon">🧠</span> AI Analysis
          </h3>

          <div className="analysis-grid">
            {/* Mood */}
            {ai.mood && (
              <div className="analysis-chip">
                <span className="chip-emoji">🎭</span>
                <div className="chip-body">
                  <span className="chip-label">Mood</span>
                  <span className="chip-value">{ai.mood}</span>
                </div>
              </div>
            )}

            {/* Genre blend */}
            {ai.genre_blend && (
              <div className="analysis-chip">
                <span className="chip-emoji">🎸</span>
                <div className="chip-body">
                  <span className="chip-label">Genre</span>
                  <span className="chip-value">{ai.genre_blend}</span>
                </div>
              </div>
            )}
          </div>

          {/* Emotional explanation */}
          {ai.emotional_explanation && (
            <div className="analysis-block">
              <p className="block-label">💡 Emotional Feel</p>
              <p className="block-text">{ai.emotional_explanation}</p>
            </div>
          )}

          {/* Lyrics meaning */}
          {ai.lyrics_meaning && (
            <div className="analysis-block">
              <p className="block-label">📝 Lyrics & Themes</p>
              <p className="block-text">{ai.lyrics_meaning}</p>
            </div>
          )}

          {/* Similar vibes */}
          {ai.similar_vibes && ai.similar_vibes.length > 0 && (
            <div className="analysis-block">
              <p className="block-label">🔗 Similar Vibes</p>
              <ul className="similar-list">
                {ai.similar_vibes.map((s, i) => (
                  <li key={i} className="similar-item">{s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Audio features (from heuristic) */}
          {ai.audio_features && (
            <div className="audio-features">
              {ai.audio_features.tempo_bpm && (
                <div className="feature-pill">
                  <span className="pill-label">BPM</span>
                  <span className="pill-value">{ai.audio_features.tempo_bpm}</span>
                </div>
              )}
              {ai.audio_features.energy !== undefined && (
                <div className="feature-pill">
                  <span className="pill-label">Energy</span>
                  <span className="pill-value">{(ai.audio_features.energy * 100).toFixed(0)}%</span>
                </div>
              )}
              {ai.audio_features.valence !== undefined && (
                <div className="feature-pill">
                  <span className="pill-label">Valence</span>
                  <span className="pill-value">{(ai.audio_features.valence * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Duration ─────────────────────────────────────────────────── */}
      {song.duration > 0 && (
        <p className="result-duration">
          Duration: {Math.floor(song.duration / 60)}:
          {String(Math.floor(song.duration % 60)).padStart(2, "0")}
        </p>
      )}

      <button className="btn-again" onClick={onReset}>
        🎤 Listen Again
      </button>
    </div>
  );
}
