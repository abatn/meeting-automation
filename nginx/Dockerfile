FROM nginx:1.25-alpine

COPY nginx.dev.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]