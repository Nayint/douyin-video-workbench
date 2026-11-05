FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.standalone.config.ts ./
COPY frontend/src ./src
COPY frontend/public/duo ./public/duo
RUN npm run build:standalone

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 VIRALLAB_STANDALONE=1 VIRALLAB_DATA=/app/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg poppler-utils libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
RUN python -m pip install -r requirements.lock
COPY backend ./backend
COPY config/author-skills ./config/author-skills
COPY --from=web /build/frontend/dist-standalone ./frontend/dist-standalone
COPY LICENSE ./LICENSE
EXPOSE 8765
CMD ["python", "-m", "backend.standalone", "--host", "0.0.0.0", "--no-browser"]
