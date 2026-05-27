#!/usr/bin/env bash
# One-time setup: installs the OPA demo API server as a systemd service.
# Upload this file to the VM and run: bash install-api-server.sh

set -euo pipefail

# Prompt for GitHub PAT (never stored in this file)
read -rsp "GitHub PAT (needs workflow scope): " GITHUB_PAT
echo ""

# Write the systemd unit
cat > /etc/systemd/system/opa-demo-api.service <<EOF
[Unit]
Description=OPA Demo API Server
After=network.target

[Service]
Type=simple
User=opa-demo
ExecStart=/usr/bin/python3 /opt/opa-demo/server.py
Restart=on-failure
RestartSec=5
Environment=GITHUB_TOKEN=${GITHUB_PAT}
Environment=GITHUB_OWNER=iampeterpam
Environment=GITHUB_REPO=opa-wi-demo
Environment=WORKFLOW_FILE=opa-workflow.yml
Environment=WORKFLOW_REF=main

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now opa-demo-api
systemctl status opa-demo-api
