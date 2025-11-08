#!/usr/bin/env sh
# Start script that uses $PORT if provided (Render sets $PORT automatically)
PORT=${PORT:-8000}
exec uvicorn server_fastapi:app --host 0.0.0.0 --port "$PORT"
