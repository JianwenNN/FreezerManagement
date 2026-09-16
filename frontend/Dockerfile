# ---- Stage 1: Build the static files ----
FROM node:20-slim AS build

WORKDIR /app

COPY package*.json .

RUN npm install

COPY . .

# Vite reads this at build time and bakes it into the compiled JS —
# must be passed as a build ARG, not a runtime environment variable.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ---- Stage 2: Serve the built static files with nginx ----
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
