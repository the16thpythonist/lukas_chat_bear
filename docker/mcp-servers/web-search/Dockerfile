# Dockerfile for web-search-mcp server with Supergateway SSE bridge
#
# This container runs the web-search-mcp server (stdio-based) and exposes it
# over SSE (Server-Sent Events) using Supergateway for network access.
#
# Architecture: Supergateway → stdio → web-search-mcp → Playwright browsers

FROM node:20-slim

# Install dependencies for Playwright browsers and netcat for health checks
RUN apt-get update && apt-get install -y \
    git \
    wget \
    netcat-openbsd \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone web-search-mcp repository
RUN git clone https://github.com/mrkrsl/web-search-mcp.git web-search-mcp

# Install web-search-mcp dependencies
WORKDIR /app/web-search-mcp
RUN npm install && \
    npx playwright install chromium firefox && \
    npm run build

# Install Supergateway globally for SSE bridge
RUN npm install -g supergateway

# Environment variables for web-search-mcp configuration
ENV MAX_CONTENT_LENGTH=500000
ENV DEFAULT_TIMEOUT=6000
ENV MAX_BROWSERS=3
ENV BROWSER_TYPES=chromium,firefox

# Default port (can be overridden via environment variable)
ENV MCP_PORT=8080

# Expose SSE endpoint port (both default and common dev port)
EXPOSE 8080 9765

# Health check endpoint (checks dynamically based on MCP_PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD sh -c 'nc -z localhost ${MCP_PORT:-8080} || exit 1'

# Create startup script that runs Supergateway bridge
# Note: This uses runtime environment variable substitution
RUN printf '#!/bin/sh\nset -e\nPORT=${MCP_PORT:-8080}\necho "Starting web-search-mcp server via Supergateway SSE bridge..."\necho "MCP Server will be available at http://0.0.0.0:${PORT}/sse"\nexec supergateway --stdio "node /app/web-search-mcp/dist/index.js" --port ${PORT} --host 0.0.0.0 --transport sse --log info\n' > /app/start.sh && chmod +x /app/start.sh

CMD ["/bin/sh", "/app/start.sh"]
