# ==========================================
# Stage 1: Build Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Serve Frontend (Nginx)
# ==========================================
FROM nginx:alpine AS frontend
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://backend:8000/api/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header Connection ""; \
        proxy_http_version 1.1; \
        chunked_transfer_encoding off; \
        proxy_buffering off; \
        proxy_cache off; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# ==========================================
# Stage 3: Build Backend (Python)
# ==========================================
FROM python:3.11-slim AS backend
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY backend/ ./backend/

# Copy built frontend assets from Stage 1 so FastAPI can serve them statically
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p .data

# Pre-seed the demo database during build
# This bakes the vector store into the Docker image and pre-downloads HuggingFace models
COPY sample_docs/ ./sample_docs/
RUN GROQ_API_KEY=dummy_key python -m backend.cli ingest sample_docs/

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Render sets the PORT environment variable. We should bind to it.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
