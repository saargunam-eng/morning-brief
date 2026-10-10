FROM python:3.11-slim

# Prevent Python from writing pyc files to disc and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY config.yaml .
COPY morning_brief/ ./morning_brief/

# Create data directory for SQLite persistent storage
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/morning_brief.db

CMD ["python", "-m", "morning_brief.main", "schedule"]
