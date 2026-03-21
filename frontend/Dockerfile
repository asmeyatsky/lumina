# =============================================================================
# LUMINA Frontend — Multi-stage Dockerfile (Vite + Nginx)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder — install deps & build production bundle
# ---------------------------------------------------------------------------
FROM node:22-slim AS builder

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY package.json package-lock.json* ./

RUN npm ci --no-audit --no-fund

# Copy the rest of the frontend source
COPY . .

# Build the production bundle
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: runtime — serve with nginx
# ---------------------------------------------------------------------------
FROM nginx:alpine AS runtime

# Remove default nginx website
RUN rm -rf /usr/share/nginx/html/*

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root: nginx alpine image supports running as nginx user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
