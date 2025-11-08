# Use a slim Python base
FROM python:3.11-slim

# Avoid buffering and set working dir
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps required by Pillow/wordcloud
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy app files
COPY . /app

# Expose default port (Render will provide $PORT at runtime)
EXPOSE 8000

# Use a small start script to honor $PORT
CMD ["sh", "/app/start.sh"]
