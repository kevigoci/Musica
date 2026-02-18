import React from "react";
import "./ListenButton.css";

/* ── Icons ───────────────────────────────────────────────────────────────── */
const MicIcon = () => (
  <svg className="btn-icon" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
  </svg>
);

const StopIcon = () => (
  <svg className="btn-icon" viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
);

/**
 * Beautiful circular button with microphone icon and animated rings.
 */
export default function ListenButton({ status, onClick }) {
  const isActive = status === "listening" || status === "analyzing";
  const isIdle = status === "idle";
  const isDone = status === "found" || status === "not_found" || status === "error";

  return (
    <div className="listen-wrapper">
      {/* Animated rings */}
      {isActive && (
        <>
          <span className="pulse-ring ring-1" />
          <span className="pulse-ring ring-2" />
          <span className="pulse-ring ring-3" />
        </>
      )}

      {/* Outer glow */}
      <div className={`listen-glow ${isActive ? "active" : ""}`} />

      <button
        className={`listen-btn ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}
        onClick={onClick}
        aria-label={isActive ? "Stop listening" : "Start listening"}
      >
        <span className="btn-content">
          {isActive ? <StopIcon /> : <MicIcon />}
        </span>
      </button>

      {/* Label */}
      {isIdle && <p className="listen-label">Tap to identify</p>}
    </div>
  );
}
