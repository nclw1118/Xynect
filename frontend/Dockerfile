# Xynect frontend — Next.js on Cloud Run.
# Build context: ./frontend
#
# NEXT_PUBLIC_API_BASE_URL is inlined into the client bundle at build time,
# so it must be supplied as a build ARG, not just a runtime env var:
#   docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com ...

# ---- Build stage ----
FROM node:20-slim AS builder
WORKDIR /app

# Install deps from the lockfile first for layer caching.
COPY package.json package-lock.json ./
RUN npm ci

# Build the production bundle. The ARG is promoted to ENV so `next build`
# inlines it into the client-side code.
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# ---- Runtime stage ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy only what `next start` needs to serve the prebuilt app.
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

# Cloud Run injects $PORT (8080); fall back to 3000 for plain `docker run`.
EXPOSE 3000
CMD ["sh", "-c", "npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
