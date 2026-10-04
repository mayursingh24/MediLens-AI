FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies: Tesseract OCR, Poppler, OpenCV headless runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Ensure storage directories exist
RUN mkdir -p uploads/prescriptions uploads/processed logs

# Expose default port
EXPOSE 5000

ENV PORT=5000
ENV FLASK_ENV=production

# Run with Gunicorn using dynamic PORT for Railway / Render / Cloud Run
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 wsgi:app"]
