FROM python:3.12-slim

# System deps for Playwright, lxml, Pillow, pycryptodome, bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install OSINT tools (maigret, sherlock)
RUN pip install --no-cache-dir maigret sherlock-project || true

# Install Playwright + Chromium for PDF export and scraping
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create data directories for SQLite persistence
RUN mkdir -p /app/data /app/data/leaks /app/data/demo \
    /app/app/static/uploads /app/app/static/reports /app/app/static/identity_cards

# Non-root user for security
RUN useradd -m -r ibp && chown -R ibp:ibp /app
USER ibp

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120"]
