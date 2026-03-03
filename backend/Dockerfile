FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    postgresql-client libpq-dev gcc curl ffmpeg \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libffi-dev shared-mime-info \
    fonts-noto-core fonts-noto-ui-core fonts-noto-mono \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]