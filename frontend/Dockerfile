# Stage 1: Build mit Node
FROM node:20-alpine as builder
RUN apk add --no-cache python3 make g++ cairo-dev jpeg-dev pango-dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Runtime mit nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
