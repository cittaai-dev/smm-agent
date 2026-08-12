FROM node:20-slim AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
# Baked in by the Makefile and inlined into the client bundle at build time
# (NEXT_PUBLIC_ prefix) -- surfaced on the System Status page so a stale
# container (built from an old cached image, not the current source) is
# visually obvious instead of silently serving yesterday's UI.
ARG GIT_SHA=unknown
ENV NEXT_PUBLIC_GIT_SHA=${GIT_SHA}
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public

EXPOSE 3000
CMD ["npm", "start"]
