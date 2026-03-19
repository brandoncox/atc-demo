# Stage 1 — build
FROM node:20-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .

# API URL is baked in at build time. Override with --build-arg VITE_API_URL=...
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2 — serve
FROM nginx:alpine

# OpenShift runs as a random non-root UID; make nginx writable
RUN chmod -R 777 /var/cache/nginx /var/run /var/log/nginx

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
