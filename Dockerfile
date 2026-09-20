# syntax=docker/dockerfile:1

# Stage 1: Build wanderlog-cli binary with MCP support
FROM golang:latest AS wanderlog-builder

WORKDIR /src

# Clone and compile denysvitali/wanderlog-cli
RUN git clone --depth 1 https://github.com/denysvitali/wanderlog-cli.git . && \
    CGO_ENABLED=0 go build -ldflags="-s -w" -o /wanderlog .

# Stage 2: Runtime image with Antigravity CLI and Wanderlog
FROM debian:bookworm-slim

LABEL maintainer="Antigravity Team"
LABEL description="Remote Antigravity CLI environment with Wanderlog CLI & MCP integration"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    bash \
    jq \
    procps \
    openssl \
    openssh-client \
    less \
    tzdata \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Install official Antigravity CLI (agy)
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- --dir /usr/local/bin && \
    chmod +x /usr/local/bin/agy

# Install the compiled wanderlog CLI from builder stage
COPY --from=wanderlog-builder /wanderlog /usr/local/bin/wanderlog
RUN chmod +x /usr/local/bin/wanderlog

# Setup directories and permissions
ENV HOME=/root
ENV WORKSPACE_DIR=/workspace
WORKDIR /workspace

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Environment variables
ENV PATH="/usr/local/bin:/root/.local/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["daemon"]
