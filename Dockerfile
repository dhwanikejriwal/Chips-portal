FROM python:3.12-slim

# Install system dependencies for Tesseract OCR, Poppler (PDF), and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    poppler-utils \
    libpq-dev \
    gcc \
    g++ \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (leverages Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the full application source code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose ports (Uvicorn for backend, Gunicorn for frontend)
EXPOSE 8000 5000