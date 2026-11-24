# One container: FastAPI serves the API and the built frontend on $PORT.
# Mount a persistent volume at /data (user data + LLM usage log). Plan: docs/deploy/plan.md

FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DATABASE_DIR=/data/database \
    LLM_USAGE_LOG=/data/logs/llm_usage.csv \
    FRONTEND_DIST=/app/frontend/dist \
    PYTHONPATH=/app/backend/src \
    PORT=8000
WORKDIR /app/backend

# Headless Chromium lets read_page render job postings that need JavaScript (~1 GB of the
# image), so it is left out by default: such pages are read from their static HTML only.
# `--build-arg INSTALL_BROWSER=true` adds it. Google search never needs it (SERPER_API_KEY).
ARG INSTALL_BROWSER=false
ENV READ_PAGE_BROWSER=${INSTALL_BROWSER}

COPY backend/requirements.txt ./
# libatomic1: Playwright's bundled node driver needs it before `--with-deps` can run.
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt \
    && if [ "$INSTALL_BROWSER" = "true" ]; then \
         apt-get update && apt-get install -y --no-install-recommends libatomic1 \
         && python -m playwright install --with-deps chromium \
         && rm -rf /var/lib/apt/lists/*; \
       fi

COPY backend/src ./src
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# State lives in /data: mount a persistent volume there (`docker run -v ...:/data`, or a
# Railway / Fly volume). No `VOLUME` instruction: Railway's builder rejects it.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/api/health', timeout=4)"

# One worker on purpose: running searches live in this process's memory.
CMD ["sh", "-c", "exec uvicorn server:app --app-dir src --host 0.0.0.0 --port ${PORT} --workers 1"]
