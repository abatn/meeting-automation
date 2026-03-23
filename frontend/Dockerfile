# Stage 1: Build mit Node (Using Debian based to prevent esbuild bus errors)
FROM node:20 as builder
ENV NODE_OPTIONS="--max-old-space-size=4096"
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
