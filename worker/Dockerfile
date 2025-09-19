FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for lxml and other packages
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (overridden in docker compose)
CMD ["python", "-m", "reader_worker.main"] 