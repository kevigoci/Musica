import React from "react";
import "./SongResult.css";

/* ── Palette for initial-letter backgrounds ─────────────────────────────── */
const COLORS = [
  ["#6c5ce7", "#a29bfe"],
  ["#00b894", "#55efc4"],
  ["#e17055", "#fab1a0"],
  ["#0984e3", "#74b9ff"],
  ["#d63031", "#ff7675"],
  ["#fdcb6e", "#ffeaa7"],
];
const pickColor = (str) => {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  return COLORS[Math.abs(h) % COLORS.length];
};

/* ── SVG Icons ───────────────────────────────────────────────────────────── */
const SpotifyIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
    <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
  </svg>
);

const YouTubeIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

export default function SongResult({ song, confidence, analysis, onReset }) {
  if (!song) return null;

  const initial = (song.title || "?")[0].toUpperCase();
  const [c1, c2] = pickColor(song.title || "");
  const ai = analysis || {};
  const hasAnalysis =
    ai.mood || ai.genre_blend || ai.lyrics_meaning ||
    ai.emotional_explanation || ai.fun_fact ||
    (ai.similar_vibes && ai.similar_vibes.length > 0);

  return (
    <div className="sr">
      {/* ── Artwork ──────────────────────────────────────────────── */}
      <div className="sr-art-wrap">
        {song.artwork_url ? (
          <img className="sr-art" src={song.artwork_url} alt="" />
        ) : (
          <div
            className="sr-art sr-art--init"
            style={{ background: `linear-gradient(135deg, ${c1}, ${c2})` }}
          >
            {initial}
          </div>
        )}
        <span className="sr-conf">{confidence.toFixed(0)}%</span>
      </div>

      {/* ── Title block ──────────────────────────────────────────── */}
      <h2 className="sr-title">{song.title}</h2>
      <p className="sr-artist">{song.artist}</p>
      {song.album && <p className="sr-album">{song.album}</p>}

      {/* ── Tags ─────────────────────────────────────────────────── */}
      <div className="sr-tags">
        {ai.category && <span className="sr-tag">{ai.category}</span>}
        {ai.language && <span className="sr-tag sr-tag--alt">{ai.language}</span>}
        {song.genre && !ai.category && <span className="sr-tag">{song.genre}</span>}
        {song.duration > 0 && (
          <span className="sr-tag sr-tag--dim">
            {Math.floor(song.duration / 60)}:{String(Math.floor(song.duration % 60)).padStart(2, "0")}
          </span>
        )}
      </div>

      {/* ── Action links ─────────────────────────────────────────── */}
      {(song.spotify_url || song.youtube_url) && (
        <div className="sr-links">
          {song.spotify_url && (
            <a href={song.spotify_url} target="_blank" rel="noopener noreferrer" className="sr-link sr-link--spotify">
              <SpotifyIcon /> Spotify
            </a>
          )}
          {song.youtube_url && (
            <a href={song.youtube_url} target="_blank" rel="noopener noreferrer" className="sr-link sr-link--yt">
              <YouTubeIcon /> YouTube
            </a>
          )}
        </div>
      )}

      {/* ── Analysis ─────────────────────────────────────────────── */}
      {hasAnalysis && (
        <div className="sr-analysis">
          {(ai.mood || ai.genre_blend) && (
            <div className="sr-row">
              {ai.mood && (
                <div className="sr-stat">
                  <span className="sr-stat-label">Mood</span>
                  <span className="sr-stat-val">{ai.mood}</span>
                </div>
              )}
              {ai.genre_blend && (
                <div className="sr-stat">
                  <span className="sr-stat-label">Genre</span>
                  <span className="sr-stat-val">{ai.genre_blend}</span>
                </div>
              )}
            </div>
          )}

          {ai.lyrics_meaning && (
            <div className="sr-block">
              <h4 className="sr-block-title">About this song</h4>
              <p className="sr-block-text">{ai.lyrics_meaning}</p>
            </div>
          )}

          {ai.emotional_explanation && (
            <div className="sr-block">
              <h4 className="sr-block-title">Musical style</h4>
              <p className="sr-block-text">{ai.emotional_explanation}</p>
            </div>
          )}

          {ai.fun_fact && (
            <div className="sr-block sr-block--highlight">
              <h4 className="sr-block-title">Fun fact</h4>
              <p className="sr-block-text">{ai.fun_fact}</p>
            </div>
          )}

          {ai.similar_vibes && ai.similar_vibes.length > 0 && (
            <div className="sr-block">
              <h4 className="sr-block-title">You might also like</h4>
              <div className="sr-similar">
                {ai.similar_vibes.map((s, i) => (
                  <span key={i} className="sr-similar-pill">{s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Reset ────────────────────────────────────────────────── */}
      <button className="sr-reset" onClick={onReset}>Listen Again</button>
    </div>
  );
}
