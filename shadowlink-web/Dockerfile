# ============================================================
# ShadowLink Web — Multi-stage Dockerfile
# ============================================================

# ── Stage 1: Build ──
FROM node:20-alpine AS builder

WORKDIR /build

# Copy dependency files first for layer caching
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: Runtime (Nginx) ──
FROM nginx:1.25-alpine AS runtime

LABEL maintainer="ShadowLink Team"
LABEL description="ShadowLink Web Frontend"
LABEL version="0.1.0"

# Remove default Nginx config
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /build/dist /usr/share/nginx/html

# SPA-friendly Nginx config
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {\n\
        expires 30d;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
    location /health {\n\
        access_log off;\n\
        return 200 "ok";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
