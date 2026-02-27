# ---- builder stage: compile native extensions ----
FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage: slim image without compilers ----
FROM python:3.11-slim

# Install git and ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install git-lfs directly from GitHub (no script dependency)
RUN GIT_LFS_VERSION=3.5.1 && \
    case "$(uname -m)" in \
        x86_64) ARCH="amd64" ;; \
        aarch64) ARCH="arm64" ;; \
        *) echo "Unsupported architecture"; exit 1 ;; \
    esac && \
    curl -L "https://github.com/git-lfs/git-lfs/releases/download/v${GIT_LFS_VERSION}/git-lfs-linux-${ARCH}-v${GIT_LFS_VERSION}.tar.gz" -o /tmp/git-lfs.tar.gz && \
    tar -xzf /tmp/git-lfs.tar.gz -C /tmp && \
    /tmp/git-lfs-${GIT_LFS_VERSION}/install.sh && \
    rm -rf /tmp/git-lfs*

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
