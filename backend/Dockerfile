FROM python:3.11-slim
WORKDIR /app
ARG SKIP_SENTINEL=false
RUN apt-get update && apt-get install -y \
    postgresql-client libpq-dev gcc g++ cmake curl ffmpeg \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libffi-dev shared-mime-info \
    fonts-noto-core fonts-noto-ui-core fonts-noto-mono \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Install only production dependencies (NOT requirements-dev.txt)
RUN pip install --no-cache-dir setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
# Sentinel LLM — skip in CI builds to save ~80min compile time
RUN if [ "$SKIP_SENTINEL" != "true" ]; then \
    CMAKE_ARGS="-DGGML_NATIVE=OFF" pip install --no-cache-dir llama-cpp-python>=0.3.0 && \
    mkdir -p /app/models && \
    curl -L -o /app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"; \
    fi
RUN mkdir -p /tmp/recordings
COPY . .
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]