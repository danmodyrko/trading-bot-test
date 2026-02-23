from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("api.main:app", host=host, port=port, reload=False)
