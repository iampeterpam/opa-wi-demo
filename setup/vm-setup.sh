#!/usr/bin/env bash
# OPA Workload Identity Demo — GCP VM Setup
# Run as: bash vm-setup.sh
# Tested on: Ubuntu 22.04 LTS

set -euo pipefail

echo "=== OPA WI Demo: VM Setup ==="

# 1. Update and install nginx
sudo apt-get update -y
sudo apt-get install -y nginx jq curl

# 2. Create the demo-app directory
sudo mkdir -p /var/www/demo-app
sudo chown -R www-data:www-data /var/www/demo-app
sudo chmod 755 /var/www/demo-app

# 3. Create the initial state.json
sudo tee /var/www/demo-app/state.json > /dev/null <<'EOF'
{
  "customer": "peter_farley",
  "status": "awaiting_deployment",
  "last_deploy": null,
  "deployed_by": null,
  "session_duration_seconds": null,
  "standing_credentials_used": 0,
  "deployment_count": 0,
  "opa_connection": "github-actions-prod",
  "git_repo": "iampeterpam/opa-wi-demo",
  "git_branch": null,
  "git_commit": null
}
EOF

sudo chown www-data:www-data /var/www/demo-app/state.json
sudo chmod 644 /var/www/demo-app/state.json

# 4. Allow the OPA JIT workload user (wl_github_actions) to write state.json
# OPA creates JIT users with wl_ prefix — this rule grants only tee on this one file
echo "wl_github_actions ALL=(ALL) NOPASSWD: /usr/bin/tee /var/www/demo-app/state.json" | \
  sudo tee /etc/sudoers.d/opa-demo-app > /dev/null
sudo chmod 440 /etc/sudoers.d/opa-demo-app

# 5. Configure nginx to serve the demo-app (with /api/ proxy to API server)
sudo tee /etc/nginx/sites-available/demo-app > /dev/null <<'NGINX'
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

    # Disable caching on state.json so auto-refresh always gets fresh data
    location /state.json {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0";
        add_header Pragma "no-cache";
        expires off;
    }

    # Proxy /api/ requests to the local Python API server
    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 30s;
    }
}
NGINX

# 6. Enable the site and reload nginx
sudo ln -sf /etc/nginx/sites-available/demo-app /etc/nginx/sites-enabled/demo-app
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx


# 7. Create the opa-demo service user (for the API server)
if ! id -u opa-demo &>/dev/null; then
  sudo useradd -r -s /bin/false opa-demo
fi

# 8. Install the Python API server
sudo mkdir -p /opt/opa-demo
sudo cp "$(dirname "$0")/../demo-app/api-server.py" /opt/opa-demo/server.py
sudo chmod 755 /opt/opa-demo/server.py

# 9. Add sudoers rule for opa-demo (same scope as wl_github_actions)
echo "opa-demo ALL=(ALL) NOPASSWD: /usr/bin/tee /var/www/demo-app/state.json" | \
  sudo tee /etc/sudoers.d/opa-demo-api > /dev/null
sudo chmod 440 /etc/sudoers.d/opa-demo-api

# 10. Write the systemd service unit
#     After running this script, replace <GITHUB_PAT> with a real token
#     (needs repo or workflow scope), then:
#       sudo systemctl daemon-reload && sudo systemctl restart opa-demo-api
sudo tee /etc/systemd/system/opa-demo-api.service > /dev/null <<'UNIT'
[Unit]
Description=OPA Demo API Server
After=network.target

[Service]
Type=simple
User=opa-demo
ExecStart=/usr/bin/python3 /opt/opa-demo/server.py
Restart=on-failure
RestartSec=5

# ── GitHub configuration ─────────────────────────────────────────
# Replace the placeholder values below, then:
#   sudo systemctl daemon-reload && sudo systemctl restart opa-demo-api
Environment=GITHUB_TOKEN=<GITHUB_PAT>
Environment=GITHUB_OWNER=<GITHUB_ORG>
Environment=GITHUB_REPO=<GITHUB_REPO>
Environment=WORKFLOW_FILE=opa-workflow.yml
Environment=WORKFLOW_REF=main

[Install]
WantedBy=multi-user.target
UNIT

# 11. Enable and start the API server
sudo systemctl daemon-reload
sudo systemctl enable --now opa-demo-api

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Copy index.html to /var/www/demo-app/index.html"
echo "  2. Edit /etc/systemd/system/opa-demo-api.service"
echo "     Replace <GITHUB_PAT>, <GITHUB_ORG>, <GITHUB_REPO>"
echo "     Token needs: repo + workflow scopes (or actions:write)"
echo "  3. sudo systemctl daemon-reload && sudo systemctl restart opa-demo-api"
echo "  4. Verify: curl http://localhost/state.json"
echo "             systemctl status opa-demo-api"
echo ""
echo "IMPORTANT: sftd must be enrolled and running on this VM."
echo "           Enrolled hostname in OPA must match: $(hostname)"
