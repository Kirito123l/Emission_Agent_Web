# ---- builder stage: compile native extensions ----
FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage: slim image without compilers ----
FROM python:3.11-slim

# Install git and git-lfs for LFS support
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install git-lfs
RUN curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash && \
    apt-get install -y git-lfs && \
    git lfs install

WORKDIR /app

# Copy only the installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code (includes LFS pointer files)
COPY . .

# Pull LFS files to get actual data
RUN git lfs pull

# Create runtime directories
RUN mkdir -p /app/data/sessions/history \
             /app/data/collection \
             /app/data/logs \
             /app/outputs \
             /app/logs

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
