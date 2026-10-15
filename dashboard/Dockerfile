# ==============================================================================
# AERIS Dashboard - Production Multi-Stage Dockerfile
# ==============================================================================

# Stage 1: Build React/Vite SPA
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Minimal Production Web Server
FROM nginx:alpine-slim AS runtime

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom Nginx configuration for SPA client routing and security headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
