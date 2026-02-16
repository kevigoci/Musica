"""Musica — Entry point.

Run with:
    python main.py
"""

import uvicorn

from backend.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
