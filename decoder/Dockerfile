# Mode S Decoder Service
# Multi-stage build for minimal final image

# Build stage
FROM debian:bookworm-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clang \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy source files
COPY include/ include/
COPY src/ src/
COPY Makefile .

# Build the server
RUN make clean && make CXX=clang++ modes_server

# Runtime stage
FROM debian:bookworm-slim

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y \
    curl \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -s /bin/false modes

# Copy binary from builder
COPY --from=builder /app/modes_server /usr/local/bin/

# Set user
USER modes

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["modes_server", "--port", "8080"]
