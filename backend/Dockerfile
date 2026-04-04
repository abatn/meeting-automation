FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    postgresql-client libpq-dev gcc curl ffmpeg \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libffi-dev shared-mime-info \
    fonts-noto-core fonts-noto-ui-core fonts-noto-mono \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
COPY requirements-dev.txt .
# Install setuptools/wheel first to ensure PEP 517 builds work for complex dependencies
RUN pip install --no-cache-dir setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
# Install test dependencies (only used in test environment)
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN mkdir -p /tmp/recordings
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]