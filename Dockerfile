# ==========================================
# Multi-Stage Dockerfile: Full-Stack Application
# Builds React frontend and serves via FastAPI backend
# ==========================================

# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend application
COPY backend/ /app/backend/

# Copy built frontend assets from Stage 1 into the location expected by backend/app.py
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Ensure persistent storage directory exists
RUN mkdir -p /app/backend/storage/videos

ENV HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

CMD ["python", "-m", "backend.app"]

