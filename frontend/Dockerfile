# Compile the browser app, then serve static files and proxy API requests through nginx.
# Application APIs retain their own OpenAPI-described surfaces.
# Use the repository root as build context so ops/nginx/default.conf is available to COPY.
FROM node:22-alpine AS builder
WORKDIR /app
# Copy dependency manifests first so source edits can reuse the installed dependency layer.
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ops/nginx/default.conf /etc/nginx/conf.d/default.conf
