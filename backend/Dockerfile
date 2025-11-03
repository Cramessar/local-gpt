FROM python:3.11-slim

# System deps needed for OCR (Tesseract) and a few native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python runtime hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Python deps
COPY requirements.txt ./requirements.txt
COPY constraints.txt ./constraints.txt
RUN pip install --upgrade pip setuptools wheel \
 && pip install -v --no-cache-dir -r requirements.txt -c constraints.txt

# App code
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
