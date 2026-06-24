FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Add non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# Add health check on a single line to prevent backslash escapes parsing bugs
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8000/ || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
