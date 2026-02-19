FROM python:3.11-slim

WORKDIR /app

# System dependencies for faiss-cpu and pandas
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir FlagEmbedding || true

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p /app/data/sessions/history \
             /app/data/collection \
             /app/data/logs \
             /app/outputs \
             /app/logs

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
