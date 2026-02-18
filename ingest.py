from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import librosa

from backend.config import SAMPLE_RATE, SONGS_DIR
from backend.database import Database
from backend.fingerprint import generate_fingerprints

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_metadata(path: Path) -> dict[str, str]:
    """Try to read ID3 / Vorbis tags; fall back to filename parsing."""
    meta: dict[str, str] = {"title": path.stem, "artist": "Unknown", "album": ""}
    try:
        from mutagen import File as MutagenFile

        tags = MutagenFile(path, easy=True)
        if tags:
            meta["title"] = (tags.get("title") or [path.stem])[0]
            meta["artist"] = (tags.get("artist") or ["Unknown"])[0]
            meta["album"] = (tags.get("album") or [""])[0]
    except Exception:
        # Fallback: parse "Artist - Title.ext"
        parts = path.stem.split(" - ", 1)
        if len(parts) == 2:
            meta["artist"], meta["title"] = parts[0].strip(), parts[1].strip()
    return meta


def ingest_file(
    db: Database,
    path: Path,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
) -> bool:
    """Index a single audio file. Returns True on success."""
    fhash = _file_hash(path)
    if db.song_exists(fhash):
        print(f"  ⏭  Already indexed: {path.name}")
        return False

    meta = _extract_metadata(path)
    title = title or meta["title"]
    artist = artist or meta["artist"]
    album = album or meta["album"]

    print(f"  🎵 Loading: {path.name} …", end=" ", flush=True)
    t0 = time.time()

    try:
        audio, sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    except Exception as exc:
        print(f"FAILED ({exc})")
        return False

    duration = len(audio) / sr
    fps = generate_fingerprints(audio, sr)

    if not fps:
        print("FAILED (no fingerprints extracted)")
        return False

    song_id = db.add_song(title, artist, album, duration, fhash)
    if song_id is None:
        print("FAILED (database error)")
        return False

    db.add_fingerprints(song_id, fps)
    elapsed = time.time() - t0

    print(f"OK — {len(fps):,} fingerprints in {elapsed:.1f}s")
    print(f"       Title: {title}  |  Artist: {artist}  |  Album: {album}  |  Duration: {duration:.1f}s")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Musica — Index songs for recognition")
    parser.add_argument("path", nargs="?", default=SONGS_DIR, help="Audio file or directory to index")
    parser.add_argument("--title", help="Song title (overrides metadata)")
    parser.add_argument("--artist", help="Artist name (overrides metadata)")
    parser.add_argument("--album", help="Album name (overrides metadata)")
    parser.add_argument("--stats", action="store_true", help="Show database stats and exit")
    args = parser.parse_args()

    db = Database()

    if args.stats:
        s = db.get_stats()
        print(f"📊  Songs: {s['songs']}  |  Fingerprints: {s['fingerprints']:,}")
        db.close()
        return

    target = Path(args.path)

    if not target.exists():
        print(f"❌  Path not found: {target}")
        sys.exit(1)

    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        files = sorted(f for f in target.rglob("*") if f.suffix.lower() in AUDIO_EXTENSIONS)

    if not files:
        print(f"⚠️  No audio files found in {target}")
        print(f"   Supported formats: {', '.join(sorted(AUDIO_EXTENSIONS))}")
        sys.exit(1)

    print(f"\n🎶 Musica Ingestion — {len(files)} file(s)\n")

    ok = 0
    for f in files:
        if ingest_file(db, f, args.title, args.artist, args.album):
            ok += 1

    stats = db.get_stats()
    print(f"\n✅  Done — {ok} new song(s) indexed")
    print(f"📊  Total: {stats['songs']} songs, {stats['fingerprints']:,} fingerprints\n")
    db.close()


if __name__ == "__main__":
    main()
