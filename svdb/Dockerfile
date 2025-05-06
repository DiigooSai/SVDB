FROM rust:1.63-slim-bullseye as rust-builder

# Install build dependencies for RocksDB
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libclang-dev \
    libssl-dev \
    pkg-config \
    python3-dev \
    python3-pip

# Set working directory
WORKDIR /build

# Copy storage engine code
COPY storage_engine/ .

# Build Rust components and Python bindings
RUN cd src && cargo build --release
RUN pip3 install maturin
RUN cd python && maturin build --release

# Second stage: Python base image
FROM python:3.9-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SVDB_DB_PATH=/data \
    SVDB_MONITOR_DB=/data/svdb_monitor.db

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create data directory
RUN mkdir -p /data

# Copy Python wheel from builder
COPY --from=rust-builder /build/python/target/wheels/*.whl /tmp/

# Install the wheel
RUN pip install /tmp/*.whl && rm /tmp/*.whl

# Copy the rest of the application
COPY api/ api/
COPY blockchain_bridge/ blockchain_bridge/
COPY verification/ verification/
COPY admin_tools/ admin_tools/
COPY integrations/ integrations/
COPY .env .env

# Install Python dependencies
RUN pip install -r api/requirements.txt
RUN pip install -e integrations/

# Set default command
CMD ["python", "api/app.py"] 