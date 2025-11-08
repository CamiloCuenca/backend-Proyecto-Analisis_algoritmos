#!/usr/bin/env python3
"""Minimal FastAPI server to accept .bib uploads and trigger the wordcloud script.

Endpoints:
- POST /upload_bib -> multipart upload of a .bib file, saved to ./data/
- POST /run_wordcloud -> runs wordcloud_minimal.py and returns stdout/stderr and output paths

Static files are mounted at /static so the UI can fetch images at /static/outputs/...
"""
from __future__ import annotations
import sys
import os
import time
import shutil
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Windows event loop policy (helps with uvicorn on Windows)
if sys.platform == 'win32':
    try:
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

BASE = Path(__file__).parent
DATA_DIR = BASE / 'data'
OUT_DIR = BASE / 'outputs'
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='Requerimiento5 helper')

# CORS: during development allow all origins. For production, restrict this
# to your frontend domain(s), e.g. ['https://mi-frontend.vercel.app']
# For security, limit allowed origins to your deployed frontend and localhost.
# Replace the Vercel URL below if it changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "https://proyecto-analisis-algoritmos-nine.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount the folder so index.html + outputs are reachable under /static
app.mount('/static', StaticFiles(directory=str(BASE)), name='static')


@app.post('/upload_bib')
async def upload_bib(file: UploadFile = File(...)):
    """Receive a .bib file and save it into `data/`.

    If a file with the same name exists, append a timestamp to avoid overwrite.
    Returns the saved path (relative to the server static root).
    """
    if not file.filename.lower().endswith('.bib'):
        raise HTTPException(status_code=400, detail='Only .bib files are accepted')

    safe_name = os.path.basename(file.filename)
    dest = DATA_DIR / safe_name
    if dest.exists():
        ts = int(time.time())
        dest = DATA_DIR / f"{dest.stem}_{ts}.bib"

    try:
        content = await file.read()
        with dest.open('wb') as fh:
            fh.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Could not save file: {e}')

    # Return a path the UI can use (served under /static)
    return JSONResponse({'saved_path': f'/static/data/{dest.name}', 'filename': dest.name})


@app.post('/upload_data')
async def upload_data(file: UploadFile = File(...)):
    """Upload a data file (records.csv or frequencies.json) into the server `data/` folder.

    Use this to provide the CSV/JSON that `wordcloud_minimal.py` expects when deploying to Render.
    Returns the saved path under /static.
    """
    safe_name = os.path.basename(file.filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail='Invalid filename')

    # Accept only the expected data filenames for safety
    allowed = {'records.csv', 'frequencies.json'}
    if safe_name not in allowed:
        raise HTTPException(status_code=400, detail=f'Allowed filenames: {allowed}')

    dest = DATA_DIR / safe_name
    try:
        content = await file.read()
        with dest.open('wb') as fh:
            fh.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Could not save file: {e}')

    return JSONResponse({'saved_path': f'/static/data/{dest.name}', 'filename': dest.name})


@app.post('/run_wordcloud')
async def run_wordcloud(timeout: int = 300):
    """Run the local `wordcloud_minimal.py` script and return its stdout/stderr and output locations.

    This runs as a blocking subprocess call to keep the implementation simple.
    """
    script = BASE / 'wordcloud_minimal.py'
    if not script.exists():
        raise HTTPException(status_code=500, detail='wordcloud_minimal.py not found in server folder')

    cmd = [sys.executable, str(script), '--data-dir', str(DATA_DIR), '--out-dir', str(OUT_DIR)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise HTTPException(status_code=504, detail=f'Wordcloud generation timed out: {e}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error running script: {e}')

    png_rel = f'/static/outputs/nube_palabras.png'
    pdf_rel = f'/static/outputs/nube_palabras.pdf'
    result = {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
        'png_url': png_rel if (OUT_DIR / 'nube_palabras.png').exists() else None,
        'pdf_url': pdf_rel if (OUT_DIR / 'nube_palabras.pdf').exists() else None,
    }
    return JSONResponse(result)


@app.get('/status')
async def status():
    return {'status': 'ok', 'data_dir': f'/static/data', 'outputs_dir': f'/static/outputs'}



@app.get('/api/image')
async def get_latest_image():
    """Return the latest generated PNG image (nube_palabras.png) from outputs/.

    Returns 404 if the file does not exist.
    """
    img = OUT_DIR / 'nube_palabras.png'
    if not img.exists():
        raise HTTPException(status_code=404, detail='Image not found')
    return FileResponse(path=str(img), media_type='image/png', filename=img.name)


@app.get('/api/outputs/{filename}')
async def get_output_file(filename: str):
    """Serve a file from the outputs directory safely (prevents path traversal).

    Example: /api/outputs/nube_palabras.png
    """
    safe_name = os.path.basename(filename)
    file_path = OUT_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail='File not found')
    # infer mime type
    try:
        import mimetypes
        media_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
    except Exception:
        media_type = 'application/octet-stream'
    return FileResponse(path=str(file_path), media_type=media_type, filename=safe_name)


# Also expose the same endpoints under the /api prefix so the frontend
# that was configured for Vercel (/api/upload_bib) works against this
# local FastAPI server without editing `index.html`.
app.post('/api/upload_bib')(upload_bib)
app.post('/api/run_wordcloud')(run_wordcloud)
app.get('/api/status')(status)
