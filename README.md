# Musica — Shazam-like Music Recognition

A real-time music recognition web app that identifies songs from microphone audio using audio fingerprinting. Built with **FastAPI** (Python) and **React**.

---

## How It Works

1. **User clicks "Tap to identify"** — the browser captures microphone audio
2. **Audio streams via WebSocket** — raw PCM chunks are sent to the backend
3. **Backend fingerprints the audio** — spectral peaks are extracted and hashed (Shazam-style algorithm)
4. **Hashes are matched** against the fingerprint database using time-offset alignment
5. **Result is returned** — song title, artist, album, and confidence score

### The Fingerprinting Algorithm

| Step               | Detail                                                                  |
| ------------------ | ----------------------------------------------------------------------- |
| **Spectrogram**    | STFT with 4096-sample window, 2048 hop                                  |
| **Peak detection** | Local maxima above −60 dB in a 20×20 neighbourhood                      |
| **Hashing**        | Combinatorial pairing of nearby peaks → SHA-1 truncated to 20 hex chars |
| **Matching**       | Offset-delta histogram — the song with the tallest aligned peak wins    |

---

## Project Structure

```
Musica/
├── backend/
│   ├── main.py            # FastAPI app (WebSocket + REST)
│   ├── fingerprint.py     # Audio fingerprinting engine
│   ├── database.py        # SQLite database layer
│   ├── models.py          # Pydantic schemas
│   └── config.py          # Configuration & constants
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js         # Main React component
│       └── components/
│           ├── ListenButton.js
│           └── SongResult.js
├── songs/                 # Drop audio files here to index
├── main.py                # Entry point — starts the server
├── ingest.py              # CLI script to index songs
├── requirements.txt
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── README.md
```

---

## Quick Start (Local)

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **ffmpeg** — `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)

### 1. Install Python dependencies

```bash
cd Musica
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Index some songs

Place audio files (`.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`) in the `songs/` directory, then run:

```bash
python ingest.py songs/
```

Or index a single file with metadata:

```bash
python ingest.py track.mp3 --title "Bohemian Rhapsody" --artist "Queen" --album "A Night at the Opera"
```

Check stats:

```bash
python ingest.py --stats
```

### 3. Start the backend

```bash
python main.py
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000` in your browser.

### 5. Use it!

1. Click the microphone button
2. Play a song that's been indexed
3. Wait 5–10 seconds for recognition
4. See the result!

---

## Quick Start (Docker)

```bash
# Place songs in songs/ directory first, then:
docker compose build
docker compose up -d

# Index songs inside the container
docker compose exec backend python ingest.py songs/
```

Open `http://localhost:3000`.

---

## API Endpoints

| Method   | Endpoint          | Description                          |
| -------- | ----------------- | ------------------------------------ |
| `WS`     | `/ws/recognize`   | Real-time microphone recognition     |
| `POST`   | `/api/recognize`  | Upload an audio file for recognition |
| `POST`   | `/api/songs`      | Add a new song to the database       |
| `GET`    | `/api/songs`      | List all indexed songs               |
| `DELETE` | `/api/songs/{id}` | Remove a song                        |
| `GET`    | `/api/stats`      | Database statistics                  |
| `GET`    | `/api/health`     | Health check                         |

### Upload a file for recognition

```bash
curl -X POST http://localhost:8000/api/recognize \
  -F "file=@sample.mp3"
```

### Add a song via API

```bash
curl -X POST http://localhost:8000/api/songs \
  -F "file=@song.mp3" \
  -F "title=My Song" \
  -F "artist=Artist Name" \
  -F "album=Album Name"
```

---

## Configuration

All settings can be overridden with environment variables:

| Variable              | Default                     | Description                          |
| --------------------- | --------------------------- | ------------------------------------ |
| `MUSICA_DB`           | `./musica.db`               | SQLite database path                 |
| `MUSICA_SONGS_DIR`    | `./songs`                   | Default directory for song ingestion |
| `MUSICA_HOST`         | `0.0.0.0`                   | Server bind address                  |
| `MUSICA_PORT`         | `8000`                      | Server port                          |
| `MUSICA_CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins                 |

---

## Tips for Best Results

- **Index full songs** — longer audio = more fingerprints = better matching
- **Recording quality matters** — a quiet environment yields cleaner fingerprints
- **8+ seconds** of audio usually produces a confident match
- The algorithm handles moderate background noise, tempo shifts up to ~5%, and speaker playback

---

## Tech Stack

| Layer      | Technology                  |
| ---------- | --------------------------- |
| Backend    | Python, FastAPI, WebSockets |
| Audio DSP  | librosa, NumPy, SciPy       |
| Database   | SQLite (WAL mode)           |
| Frontend   | React 18, Web Audio API     |
| Deployment | Docker, Nginx               |

---

## License

MIT
