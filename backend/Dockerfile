FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend code into /app/backend so 'python -m backend.app' resolves the package correctly
COPY . /app/backend

# Create storage directory for database and uploads
RUN mkdir -p /app/backend/storage/videos

ENV HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

CMD ["python", "-m", "backend.app"]
