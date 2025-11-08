# Backend (FastAPI) — despliegue en Render

Este repositorio contiene un servidor FastAPI minimal que acepta uploads `.bib`, genera una nube de palabras con `wordcloud_minimal.py` y expone endpoints (incluyendo `/api/image`).

A continuación instrucciones para desplegar en Render, con y sin Docker.

## Dependencias
Se incluyen en `requirements.txt`. Si no usas Docker, Render instalará estas dependencias en el build step.

## Ejecutar localmente
Instala dependencias y ejecuta:

```powershell
pip install -r requirements.txt
python -m uvicorn server_fastapi:app --reload --host 127.0.0.1 --port 8000
```

La API estará en `http://127.0.0.1:8000`.

## Desplegar en Render — opción simple (sin Docker)
1. Añade este repositorio a Render.
2. Crea un nuevo "Web Service" (Python).
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn server_fastapi:app --host 0.0.0.0 --port $PORT`
5. Branch: `main` (o la rama que uses).

Render proporcionará `$PORT` automáticamente.

Notas:
- El filesystem de la instancia en Render es efímero: archivos escritos en `data/` o `outputs/` persistirán mientras el servicio esté corriendo, pero se perderán después de un redeploy o si Render recrea la instancia. Para persistencia recomendamos usar un storage externo (S3, DigitalOcean Spaces, etc.).

## Desplegar en Render — opción Docker
Si tu app necesita control del sistema (por ejemplo, dependencias nativas), puedes usar Docker.

1. Marca "Docker" al crear el servicio en Render.
2. Render construirá la imagen usando el `Dockerfile` en la raíz.
3. El CMD de la imagen ejecuta `/app/start.sh`, que respeta `$PORT`.

## Archivos creados
- `requirements.txt` — lista de dependencias Python.
- `Dockerfile` — imagen ligera basada en `python:3.11-slim` con dependencias del sistema para Pillow/wordcloud.
- `start.sh` — arranca uvicorn leyendo `$PORT`.
- `.dockerignore` — evita copiar archivos innecesarios a la imagen.

## Endpoints importantes
- `POST /upload_bib` — subir `.bib` (devuelve `/static/data/<file>`)
- `POST /run_wordcloud` — ejecuta `wordcloud_minimal.py` y genera `outputs/nube_palabras.png` (bloqueante en la implementación actual)
- `GET /api/image` — devuelve `outputs/nube_palabras.png` (si existe)
- `GET /api/outputs/{filename}` — sirve un archivo dentro de `outputs/`

## Endpoints (URL pública en Render)
Base URL: https://backend-proyecto-analisis-algoritmos.onrender.com

- POST https://backend-proyecto-analisis-algoritmos.onrender.com/api/upload_bib
	- Descripción: Subir un archivo `.bib` (multipart/form-data, campo `file`).
	- Respuesta: JSON con `saved_path` y `filename`.

- POST https://backend-proyecto-analisis-algoritmos.onrender.com/api/upload_data
	- Descripción: Subir `records.csv` o `frequencies.json` (multipart/form-data, campo `file`).
	- Restricción: solo acepta `records.csv` o `frequencies.json` como nombre de archivo.
	- Respuesta: JSON con `saved_path` y `filename`.

- POST https://backend-proyecto-analisis-algoritmos.onrender.com/api/run_wordcloud?timeout=300
	- Descripción: Ejecuta `wordcloud_minimal.py` en el servidor. Parámetro opcional `timeout` (segundos).
	- Respuesta: JSON con `ok`, `returncode`, `stdout`, `stderr`, `png_url`, `pdf_url`.

- GET https://backend-proyecto-analisis-algoritmos.onrender.com/api/image
	- Descripción: Devuelve `nube_palabras.png` si existe (Content-Type: image/png). Retorna 404 si no existe.

- GET https://backend-proyecto-analisis-algoritmos.onrender.com/api/outputs/{filename}
	- Descripción: Serve archivos dentro de `outputs/` (p.ej. `nube_palabras.png`).

Puedes probar y depurar usando Swagger UI en:
https://backend-proyecto-analisis-algoritmos.onrender.com/docs

Ejemplos rápidos (PowerShell)
```powershell
# Status
Invoke-RestMethod -Uri 'https://backend-proyecto-analisis-algoritmos.onrender.com/api/status' -Method Get

# Subir sample.bib (form-data)
Invoke-RestMethod -Uri 'https://backend-proyecto-analisis-algoritmos.onrender.com/api/upload_bib' -Method Post -Form @{ file = Get-Item '.\sample.bib' }

# Subir records.csv o frequencies.json
Invoke-RestMethod -Uri 'https://backend-proyecto-analisis-algoritmos.onrender.com/api/upload_data' -Method Post -Form @{ file = Get-Item '.\records.csv' }

# Ejecutar generación (timeout en segundos)
Invoke-RestMethod -Uri 'https://backend-proyecto-analisis-algoritmos.onrender.com/api/run_wordcloud?timeout=300' -Method Post

# Descargar la imagen generada
Invoke-WebRequest -Uri 'https://backend-proyecto-analisis-algoritmos.onrender.com/api/image' -OutFile .\nube_palabras.png
```

## Recomendaciones
- Para tareas largas (generación que puede tardar), mover la generación a un worker (Celery, RQ) o usar un background worker en Render.
- Restringir CORS en producción.
- Añadir monitorización y persistencia de outputs si necesitas conservar imágenes generadas entre deploys.

---
Si quieres que empuje estos cambios a una rama o añada un `render.yaml` para infraestructura-as-code en Render, dime y lo creo.