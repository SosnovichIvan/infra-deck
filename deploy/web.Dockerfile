FROM node:24.12.0-bookworm-slim AS build
ENV CYPRESS_INSTALL_BINARY=0
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm exec -- vite build --outDir dist

FROM nginx:1.28-alpine
COPY deploy/nginx-container.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx", "-g", "daemon off;"]
