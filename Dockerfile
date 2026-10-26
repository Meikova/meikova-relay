FROM node:22-slim AS base

WORKDIR /app

# Install curl, ca-certificates, and cloudflared for Quick Tunnel support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb \
    && dpkg -i /tmp/cloudflared.deb \
    && rm -f /tmp/cloudflared.deb

WORKDIR /app/relay-server
COPY relay-server/package*.json ./
RUN npm ci --omit=dev

WORKDIR /app
COPY . .

WORKDIR /app/relay-server
EXPOSE 8080

ENV PORT=8080 \
    NODE_ENV=production

CMD ["node", "--experimental-sqlite", "server.js"]
