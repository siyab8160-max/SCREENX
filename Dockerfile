FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     curl     && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configurations
COPY src/ src/
COPY configs/ configs/
COPY data/ data/
COPY pyproject.toml .
COPY README.md .

ENV PYTHONPATH=/app/src
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3     CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python3", "src/sih26170/service/server.py", "--host", "0.0.0.0", "--port", "8000"]
