import React, { useState, useRef, useCallback, useEffect } from "react";
import ListenButton from "./components/ListenButton";
import SongResult from "./components/SongResult";
import "./App.css";

/* ── WebSocket URL ───────────────────────────────────────────────────────── */
const WS_URL =
  process.env.REACT_APP_WS_URL ||
  (process.env.NODE_ENV === "development"
    ? "ws://localhost:8000/ws/recognize"
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/recognize`);

const API_URL =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

/* ── Icons ───────────────────────────────────────────────────────────────── */
const SearchIcon = () => (
  <svg className="state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/>
    <path d="m21 21-4.35-4.35"/>
    <path d="M11 8v6M8 11h6"/>
  </svg>
);

const AlertIcon = () => (
  <svg className="state-icon state-icon--error" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <line x1="12" y1="8" x2="12" y2="12"/>
    <line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
);

/* ── State machine ───────────────────────────────────────────────────────── */
// idle → listening → analyzing → found | not_found | error

export default function App() {
  const [status, setStatus] = useState("idle"); // idle|listening|analyzing|found|not_found|error
  const [duration, setDuration] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [stats, setStats] = useState(null);

  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const ctxRef = useRef(null);
  const procRef = useRef(null);

  /* ── Fetch stats on mount ──────────────────────────────────────────────── */
  useEffect(() => {
    fetch(`${API_URL}/api/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  /* ── Cleanup on unmount ────────────────────────────────────────────────── */
  useEffect(() => {
    return () => stopListening();
  }, []); // eslint-disable-line

  /* ── Stop everything ───────────────────────────────────────────────────── */
  const stopListening = useCallback(() => {
    if (procRef.current) {
      try { procRef.current.disconnect(); } catch (_) {}
      procRef.current = null;
    }
    if (ctxRef.current) {
      try { ctxRef.current.close(); } catch (_) {}
      ctxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "stop" }));
        }
        wsRef.current.close();
      } catch (_) {}
      wsRef.current = null;
    }
  }, []);

  /* ── Handle incoming WS messages ───────────────────────────────────────── */
  const handleMessage = useCallback(
    (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.status) {
          case "listening":
            setDuration(data.duration || 0);
            setStatus("listening");
            break;
          case "analyzing":
            setStatus("analyzing");
            break;
          case "match_found":
            setResult(data);
            setStatus("found");
            stopListening();
            break;
          case "no_match":
            setError(data.message || "No matching song found");
            setStatus("not_found");
            stopListening();
            break;
          case "error":
            setError(data.message || "An error occurred");
            setStatus("error");
            stopListening();
            break;
          default:
            break;
        }
      } catch (_) {}
    },
    [stopListening]
  );

  /* ── Start listening ───────────────────────────────────────────────────── */
  const startListening = useCallback(async () => {
    setStatus("listening");
    setDuration(0);
    setResult(null);
    setError("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      ctxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor: deprecated but universally supported
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      procRef.current = processor;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "config", sampleRate: audioCtx.sampleRate }));
      };

      ws.onmessage = handleMessage;

      ws.onerror = () => {
        setError("Cannot connect to backend. Is the server running?");
        setStatus("error");
        stopListening();
      };

      ws.onclose = () => {};

      source.connect(processor);
      processor.connect(audioCtx.destination);

      processor.onaudioprocess = (e) => {
        if (ws.readyState === WebSocket.OPEN) {
          const pcm = e.inputBuffer.getChannelData(0);
          ws.send(pcm.buffer);
        }
      };
    } catch (err) {
      setError("Microphone access denied. Please allow microphone access and try again.");
      setStatus("error");
    }
  }, [handleMessage, stopListening]);

  /* ── Click handler ─────────────────────────────────────────────────────── */
  const handleClick = useCallback(() => {
    if (status === "listening" || status === "analyzing") {
      stopListening();
      setStatus("idle");
    } else {
      startListening();
    }
  }, [status, startListening, stopListening]);

  /* ── Reset to idle ─────────────────────────────────────────────────────── */
  const reset = useCallback(() => {
    stopListening();
    setStatus("idle");
    setResult(null);
    setError("");
    setDuration(0);
  }, [stopListening]);

  /* ── Render ────────────────────────────────────────────────────────────── */
  const isActive = status === "listening" || status === "analyzing";

  return (
    <div className="app">
      {/* Background glow */}
      <div className={`bg-glow ${isActive ? "active" : ""} ${status === "found" ? "found" : ""}`} />

      <div className="container">
        {/* Header */}
        <header className="header">
          <h1 className="logo">Musica</h1>
          <p className="tagline">Identify any song in seconds</p>
        </header>

        {/* Main card */}
        <div className="card">
          <ListenButton
            status={status}
            duration={duration}
            onClick={handleClick}
          />

          {/* Status text */}
          {status === "listening" && (
            <p className="status-text">
              Listening... <span className="duration">{duration.toFixed(1)}s</span>
            </p>
          )}
          {status === "analyzing" && (
            <p className="status-text analyzing">Analyzing audio</p>
          )}

          {/* Result */}
          {status === "found" && result && (
            <SongResult
              song={result.song}
              confidence={result.confidence}
              analysis={result.analysis}
              onReset={reset}
            />
          )}

          {/* No match */}
          {status === "not_found" && (
            <div className="no-match">
              <SearchIcon />
              <h3 className="state-title">No Match Found</h3>
              <p className="no-match-text">{error}</p>
              <button className="btn-retry" onClick={reset}>
                Try Again
              </button>
            </div>
          )}

          {/* Error */}
          {status === "error" && (
            <div className="error-box">
              <AlertIcon />
              <h3 className="state-title state-title--error">Something Went Wrong</h3>
              <p className="error-text">{error}</p>
              <button className="btn-retry" onClick={reset}>
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* Stats */}
        {stats && (
          <p className="stats">
            {stats.songs} song{stats.songs !== 1 ? "s" : ""} indexed • {stats.fingerprints.toLocaleString()} fingerprints
          </p>
        )}
      </div>
    </div>
  );
}
