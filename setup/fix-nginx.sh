#!/usr/bin/env bash
# Adds /api/ proxy block to nginx config and reloads.
# Upload to VM and run: bash fix-nginx.sh

set -euo pipefail

cat > /etc/nginx/sites-available/demo-app <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/demo-app;
    index index.html;
    server_name _;

    add_header Access-Control-Allow-Origin *;

    location / {
        try_files $uri $uri/ =404;
    }

    location /state.json {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0";
        add_header Pragma "no-cache";
        expires off;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 30s;
    }
}
NGINX

nginx -t && systemctl reload nginx
echo "nginx reloaded — /api/ proxy active"
