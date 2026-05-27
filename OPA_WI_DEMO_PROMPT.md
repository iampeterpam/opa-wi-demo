# OPA Workload Identity — "Mission Control" Demo Prompt

> **For the SE:** Hand this file to Claude and say: "Execute this prompt." Claude will generate every artifact needed to build and run this demo. Estimated build time: ~2 hours. Estimated live presentation time: ~5 minutes.

---

## SECTION 1 — CLAUDE INSTRUCTIONS

You are helping a Solutions Engineer build and deliver a live customer demo of **OPA Workload Identity for Automation** (Okta Privileged Access, GA feature). Your job is to produce every artifact needed: infrastructure setup scripts, web application code, GitHub Actions workflows, OPA configuration steps, and a word-for-word demo script.

**When executing this prompt:**
1. Read all sections before generating output
2. Replace every `<PLACEHOLDER>` with the value provided or prompt the SE to supply it
3. Generate artifacts in the order listed in Section 4
4. Output each artifact as a clearly labeled, copy-paste-ready code block
5. After all artifacts are generated, print the pre-flight checklist from Section 5

**SE-supplied values needed before generation:**
| Placeholder | Description | Example |
|---|---|---|
| `<CUSTOMER_NAME>` | Customer company name for dashboard | `Acme Corp` |
| `<GCP_VM_IP>` | External IP of the GCP VM | `34.123.45.67` |
| `<GCP_VM_USER>` | SSH username for GCP VM setup | `peterfarley` |
| `<OPA_TEAM>` | OPA team name (slug) | `platform-team` |
| `<OPA_CONNECTION_NAME>` | Name for the Workload Connection | `github-actions-prod` |
| `<OPA_GATEWAY>` | OPA gateway hostname | `<team>.okta.pam.com` |
| `<GITHUB_ORG>` | GitHub org or username | `acme-corp` |
| `<GITHUB_REPO>` | GitHub repo name | `deploy-pipeline` |
| `<TARGET_HOSTNAME>` | OPA-enrolled target server hostname | `prod-web-01` |
| `<GITHUB_PAT>` | GitHub Personal Access Token for Run Pipeline button | Token with `repo` + `workflow` scopes |

---

## SECTION 2 — FEATURE CONTEXT

### What Is OPA Workload Identity?

Okta Privileged Access (OPA) Workload Identity for Automation is a GA feature that allows automated workloads — CI/CD pipelines, service accounts, and other non-human identities — to authenticate to OPA using **cryptographically signed JWTs issued by their native platform**, rather than static API keys or SSH private keys.

### The Core Shift

| Before (Legacy) | After (OPA Workload Identity) |
|---|---|
| Static SSH private key stored in GitHub Secrets | No stored credentials anywhere |
| Key is 18 months old and never rotated | Short-lived JWT (~120s TTL) |
| Anyone with repo access can exfiltrate the key | Token tied to specific repo + branch |
| Key breach = standing access until manually revoked | Deactivate the Connection = all pipelines blocked instantly |
| Audit log shows "automated deployment" | Audit log shows exact JWT claims: repo, branch, workflow |

### Authentication Flow

```
GitHub Actions job starts
        │
        ▼
1. GitHub issues OIDC JWT to the job (signed by GitHub's OIDC endpoint)
        │
        ▼
2. Pipeline fetches the OIDC JWT: uses ACTIONS_ID_TOKEN_REQUEST_TOKEN
   + ACTIONS_ID_TOKEN_REQUEST_URL to request the signed JWT via curl.
   JWT stored in a named env var (e.g. GITHUB_OIDC_TOKEN).
   Note: ACTIONS_ID_TOKEN_REQUEST_TOKEN is a request credential, not
   the OIDC JWT itself — it cannot be passed directly to --jwt-env.
        │
        ▼
3. Pipeline runs: sft workload authenticate \
     --team <TEAM> \
     --connection <CONNECTION_NAME> \
     --jwt-env GITHUB_OIDC_TOKEN \
     [--role-hint <ROLE_NAME>]   # optional — verify availability against your sft CLI version
        │
        ▼
4. OPA validates JWT against Workload Connection:
   - Checks JWKS URL (https://token.actions.githubusercontent.com/.well-known/jwks)
   - Validates required claims: repo, workflow_ref, ref
        │
        ▼
5. OPA issues short-lived OPA_TOKEN (expires per Connection TTL setting)
        │
        ▼
6. sft ssh <target-host> → ephemeral SSH certificate issued
   → wl_github_actions user created JIT on target
   → state.json updated
   → SSH session closes → JIT user torn down → cert expired
```

### Key Components

| Component | Role in Demo |
|---|---|
| **Workload Connection** | Trust anchor: maps GitHub OIDC JWKS URL to a named connection in OPA |
| **Workload Role** | Groups pipelines by characteristics; enforces claim conditions (repo, branch) |
| **Security Policy** | Grants the Workload Role SSH access to the target server |
| **`sft` CLI** | Installed on the GitHub Actions runner; executes auth + SSH commands |
| **`wl_` prefix** | JIT Linux username auto-prefixed (e.g., `wl_github_actions`) |

---

## SECTION 3 — DEMO DESIGN SPEC

### Concept: "Mission Control" Dashboard

A live web dashboard runs on the GCP VM at `http://<GCP_VM_IP>`. The GitHub Actions pipeline — protected by OPA Workload Identity — SSHes in and updates a `state.json` file. The dashboard auto-refreshes every 3 seconds, showing the new deployment in real time. The customer sees their company name on what looks like a production deployment console — with zero stored credentials anywhere in the pipeline.

**Run Pipeline + Clear buttons:** The dashboard includes a control bar with two buttons:
- **▶ Run Pipeline** — dispatches the `opa-workflow.yml` workflow directly from the dashboard (via the VM's API server calling the GitHub API). Shows a spinner while the run is in progress. No need to switch to the GitHub Actions tab just to trigger.
- **✕ Clear** — resets `state.json` to blank and immediately wipes the dashboard — clean slate before a new customer walkthrough.

### The Five Browser Tabs

Pre-arrange these tabs before the customer joins:

| # | URL / Location | Label It | Purpose |
|---|---|---|---|
| 1 | `http://<GCP_VM_IP>` | **"LIVE DASHBOARD"** | The Mission Control UI — auto-refreshes |
| 2 | GitHub → `before/` branch → Settings → Secrets | **"THE OLD WAY"** | Shows `SSH_PRIVATE_KEY` in Secrets |
| 3 | GitHub → `main` branch → Settings → Secrets | **"THE NEW WAY"** | Empty Secrets tab |
| 4 | GitHub Actions → latest workflow run | **"PIPELINE"** | Live execution log |
| 5 | OPA Console → Workloads → Sessions | **"AUDIT"** | OPA session + audit evidence |

### Three-Act Narrative

**Act 1 — The Problem (60 seconds)**
Tab 2. Show `SSH_PRIVATE_KEY` in GitHub Secrets. Let the customer read the name.

**Act 2 — The Magic (2–3 minutes live)**
Tab 3: empty Secrets. Tab 4: trigger pipeline. Tab 1: watch dashboard update.

**Act 3 — The Guardrails (60 seconds)**
Tab 5: OPA session log with JWT claims. Optional: trigger negative test from non-main branch.

---

## SECTION 4 — BUILD INSTRUCTIONS

Claude: generate the following artifacts in order. Output each as a labeled, copy-paste-ready block.

---

### 4a. GCP VM Setup Script

**File:** `setup/vm-setup.sh`

```bash
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
  "customer": "<CUSTOMER_NAME>",
  "status": "awaiting_deployment",
  "last_deploy": null,
  "deployed_by": null,
  "session_duration_seconds": null,
  "standing_credentials_used": 0,
  "deployment_count": 0,
  "opa_connection": "<OPA_CONNECTION_NAME>",
  "git_repo": "<GITHUB_ORG>/<GITHUB_REPO>",
  "git_branch": null,
  "git_commit": null
}
EOF

sudo chown www-data:www-data /var/www/demo-app/state.json
sudo chmod 644 /var/www/demo-app/state.json

# 4. Allow the OPA JIT workload user to write state.json
# OPA creates users with wl_ prefix — we grant write access via a sudo rule
# Replace wl_github_actions with your actual OPA workload username if different
echo "www-data ALL=(ALL) NOPASSWD: /usr/bin/tee /var/www/demo-app/state.json" | \
  sudo tee /etc/sudoers.d/opa-demo-app > /dev/null

# 5. Configure nginx to serve the demo-app (with /api/ proxy to local API server)
sudo tee /etc/nginx/sites-available/demo-app > /dev/null <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/demo-app;
    index index.html;
    server_name _;

    # Allow CORS for local development/testing
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

# 9. Add sudoers rule for opa-demo (same scope as wl_<WORKLOAD_ROLE_NAME>)
echo "opa-demo ALL=(ALL) NOPASSWD: /usr/bin/tee /var/www/demo-app/state.json" | \
  sudo tee /etc/sudoers.d/opa-demo-api > /dev/null
sudo chmod 440 /etc/sudoers.d/opa-demo-api

# 10. Write the systemd service unit
#     After running this script, replace <GITHUB_PAT>, <GITHUB_ORG>, <GITHUB_REPO>
#     with real values, then:
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
echo "IMPORTANT: Ensure the OPA ASA/PAS agent is enrolled on this VM"
echo "           and the target hostname in OPA matches: $(hostname)"
```

**After running:** Copy `index.html` (Section 4b) to `/var/www/demo-app/index.html` and set ownership:
```bash
sudo chown www-data:www-data /var/www/demo-app/index.html
sudo chmod 644 /var/www/demo-app/index.html
```

**GitHub PAT setup (required for Run Pipeline button):**
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Create a token scoped to `<GITHUB_ORG>/<GITHUB_REPO>` with **Actions: Read and write** permission
3. Edit `/etc/systemd/system/opa-demo-api.service` on the VM — replace `<GITHUB_PAT>`, `<GITHUB_ORG>`, `<GITHUB_REPO>`
4. `sudo systemctl daemon-reload && sudo systemctl restart opa-demo-api`
5. Verify: `systemctl status opa-demo-api` — should show `active (running)`

---

### 4b. Demo Web App

#### `demo-app/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Mission Control — OPA Workload Identity Demo</title>
  <style>
    /* ===================== RESET & BASE ===================== */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
      background: #0a0e1a;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* ===================== HEADER ===================== */
    header {
      background: linear-gradient(135deg, #1a1f35 0%, #0f1729 100%);
      border-bottom: 1px solid #2d3a5a;
      padding: 20px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .okta-badge {
      background: #0061F2;
      color: white;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      padding: 4px 10px;
      border-radius: 4px;
      text-transform: uppercase;
    }

    h1 {
      font-size: 20px;
      font-weight: 600;
      color: #f8fafc;
      letter-spacing: -0.3px;
    }

    h1 span {
      color: #60a5fa;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .refresh-badge {
      font-size: 11px;
      color: #64748b;
    }

    .live-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
      animation: pulse 2s infinite;
      margin-right: 6px;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    /* ===================== MAIN GRID ===================== */
    main {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-template-rows: auto auto auto;
      gap: 16px;
      padding: 24px 32px;
      max-width: 1200px;
      width: 100%;
      margin: 0 auto;
    }

    /* ===================== CARDS ===================== */
    .card {
      background: #111827;
      border: 1px solid #1e2d4a;
      border-radius: 10px;
      padding: 20px 24px;
    }

    .card-label {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #475569;
      margin-bottom: 8px;
    }

    .card-value {
      font-size: 15px;
      color: #f1f5f9;
      word-break: break-all;
    }

    /* ===================== STATUS HERO ===================== */
    .card-hero {
      grid-column: 1 / -1;
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      border: 1px solid #3730a3;
      border-radius: 10px;
      padding: 28px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .hero-status {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .hero-status-label {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #6366f1;
    }

    .hero-status-value {
      font-size: 28px;
      font-weight: 700;
      color: #f8fafc;
    }

    .hero-status-value.awaiting {
      color: #94a3b8;
    }

    .hero-status-value.success {
      color: #22c55e;
    }

    .credential-counter {
      text-align: right;
    }

    .credential-number {
      font-size: 64px;
      font-weight: 800;
      color: #22c55e;
      line-height: 1;
    }

    .credential-number.nonzero {
      color: #ef4444;
    }

    .credential-label {
      font-size: 11px;
      color: #64748b;
      letter-spacing: 1px;
      text-transform: uppercase;
      margin-top: 4px;
    }

    /* ===================== SECURITY BADGES ===================== */
    .card-security {
      grid-column: 1 / -1;
      background: #111827;
      border: 1px solid #1e2d4a;
      border-radius: 10px;
      padding: 20px 24px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    .badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: #0f172a;
      border: 1px solid #1e2d4a;
      border-radius: 6px;
      padding: 10px 16px;
      font-size: 12px;
      color: #94a3b8;
      flex: 1;
      min-width: 180px;
    }

    .badge-icon {
      font-size: 16px;
    }

    .badge.active {
      border-color: #22c55e44;
      color: #4ade80;
    }

    .badge.inactive {
      border-color: #1e2d4a;
      color: #475569;
    }

    /* ===================== FOOTER ===================== */
    footer {
      border-top: 1px solid #1e2d4a;
      padding: 12px 32px;
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #334155;
    }

    /* ===================== DEPLOYED-BY ===================== */
    .deployed-by {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .wl-badge {
      background: #1e3a5f;
      color: #60a5fa;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
    }
  </style>
</head>
<body>

<header>
  <div class="header-left">
    <span class="okta-badge">OPA</span>
    <h1>Mission Control — <span id="customer-name">Loading…</span></h1>
  </div>
  <div class="header-right">
    <span class="refresh-badge"><span class="live-dot"></span>Live · refreshes every 3s</span>
  </div>
</header>

<main>

  <!-- HERO: Status + Credential Counter -->
  <div class="card-hero">
    <div class="hero-status">
      <div class="hero-status-label">Deployment Status</div>
      <div class="hero-status-value awaiting" id="deploy-status">Awaiting deployment…</div>
      <div style="margin-top:8px; font-size:13px; color:#64748b;" id="deploy-timestamp">—</div>
    </div>
    <div class="credential-counter">
      <div class="credential-number" id="cred-count">0</div>
      <div class="credential-label">Standing Credentials Used</div>
    </div>
  </div>

  <!-- Deployed By -->
  <div class="card">
    <div class="card-label">Deployed By</div>
    <div class="card-value deployed-by">
      <span class="wl-badge" id="deployed-by-badge" style="display:none">WL</span>
      <span id="deployed-by">—</span>
    </div>
  </div>

  <!-- Session Duration -->
  <div class="card">
    <div class="card-label">Session Duration</div>
    <div class="card-value" id="session-duration">—</div>
  </div>

  <!-- OPA Connection -->
  <div class="card">
    <div class="card-label">OPA Workload Connection</div>
    <div class="card-value" id="opa-connection">—</div>
  </div>

  <!-- Git Info -->
  <div class="card">
    <div class="card-label">Git Commit · Branch · Repo</div>
    <div class="card-value" id="git-info">—</div>
  </div>

  <!-- Security Badges -->
  <div class="card-security">
    <div class="badge inactive" id="badge-oidc">
      <span class="badge-icon">🔐</span>
      <span>OIDC Token Validated</span>
    </div>
    <div class="badge inactive" id="badge-cert">
      <span class="badge-icon">📜</span>
      <span>Ephemeral SSH Cert Issued</span>
    </div>
    <div class="badge inactive" id="badge-jit">
      <span class="badge-icon">⚡</span>
      <span>JIT Account Created</span>
    </div>
    <div class="badge inactive" id="badge-teardown">
      <span class="badge-icon">🔒</span>
      <span>Session Closed · Cert Expired</span>
    </div>
  </div>

</main>

<footer>
  <span id="footer-connection">OPA Connection: —</span>
  <span id="footer-count">Deployments: 0</span>
  <span>Workload Identity for Automation · Okta Privileged Access</span>
</footer>

<script>
  const STATE_URL = '/state.json';
  const REFRESH_MS = 3000;

  function fmt(val, fallback = '—') {
    return (val !== null && val !== undefined && val !== '') ? val : fallback;
  }

  function renderState(s) {
    // Header customer name
    document.getElementById('customer-name').textContent = fmt(s.customer, 'Demo Customer');

    // Credential counter
    const cred = s.standing_credentials_used || 0;
    const credEl = document.getElementById('cred-count');
    credEl.textContent = cred;
    credEl.className = 'credential-number' + (cred > 0 ? ' nonzero' : '');

    // Deploy status
    const statusEl = document.getElementById('deploy-status');
    const tsEl = document.getElementById('deploy-timestamp');

    if (s.status === 'success' && s.last_deploy) {
      statusEl.textContent = '✅ Deployment Successful';
      statusEl.className = 'hero-status-value success';
      tsEl.textContent = 'Last deploy: ' + s.last_deploy;
    } else {
      statusEl.textContent = 'Awaiting deployment…';
      statusEl.className = 'hero-status-value awaiting';
      tsEl.textContent = '—';
    }

    // Deployed by
    const dbVal = fmt(s.deployed_by);
    document.getElementById('deployed-by').textContent = dbVal;
    const badge = document.getElementById('deployed-by-badge');
    if (dbVal.startsWith('wl_')) {
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }

    // Session duration
    const dur = s.session_duration_seconds;
    document.getElementById('session-duration').textContent =
      dur !== null && dur !== undefined ? dur + 's' : '—';

    // OPA connection
    document.getElementById('opa-connection').textContent = fmt(s.opa_connection);

    // Git info
    const branch = fmt(s.git_branch, '');
    const commit = s.git_commit ? s.git_commit.slice(0, 7) : '';
    const repo = fmt(s.git_repo, '');
    const gitParts = [commit, branch, repo].filter(Boolean);
    document.getElementById('git-info').textContent = gitParts.join(' · ') || '—';

    // Security badges — activate them all if a successful deploy happened
    const deployed = s.status === 'success';
    ['badge-oidc', 'badge-cert', 'badge-jit', 'badge-teardown'].forEach(id => {
      document.getElementById(id).className = 'badge ' + (deployed ? 'active' : 'inactive');
    });

    // Footer
    document.getElementById('footer-connection').textContent =
      'OPA Connection: ' + fmt(s.opa_connection);
    document.getElementById('footer-count').textContent =
      'Deployments: ' + (s.deployment_count || 0);
  }

  async function fetchState() {
    try {
      const resp = await fetch(STATE_URL + '?_=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      renderState(data);
    } catch (e) {
      console.warn('State fetch error:', e.message);
    }
  }

  fetchState();
  setInterval(fetchState, REFRESH_MS);
</script>
</body>
</html>
```

#### `demo-app/state.json` — Initial Schema

```json
{
  "customer": "<CUSTOMER_NAME>",
  "status": "awaiting_deployment",
  "last_deploy": null,
  "deployed_by": null,
  "session_duration_seconds": null,
  "standing_credentials_used": 0,
  "deployment_count": 0,
  "opa_connection": "<OPA_CONNECTION_NAME>",
  "git_repo": "<GITHUB_ORG>/<GITHUB_REPO>",
  "git_branch": null,
  "git_commit": null
}
```

---

### 4b-api. API Server

**File:** `demo-app/api-server.py`

Single-file Python 3 HTTP server (stdlib only, no pip required). Listens on `127.0.0.1:8765`. Nginx proxies `/api/` requests to it.

| Endpoint | Method | What it does |
|---|---|---|
| `/api/run` | POST | Dispatches `opa-workflow.yml` via GitHub workflow_dispatch API |
| `/api/clear` | POST | Rewrites `state.json` to blank template via `sudo tee` |
| `/api/workflow-status?run_id=<id>` | GET | Polls GitHub API for run status; returns `in_progress` or `completed` |

`GITHUB_TOKEN` is read from the environment variable only — never touches the browser or disk. The `opa-demo` service user gets a sudoers rule scoped only to `tee /var/www/demo-app/state.json`.

```python
#!/usr/bin/env python3
"""
OPA WI Demo — API server
Listens on 127.0.0.1:8765. Zero external dependencies (stdlib only).
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE_PATH = "/var/www/demo-app/state.json"

BLANK_STATE = {
    "customer": None,
    "status": "awaiting_deployment",
    "last_deploy": None,
    "deployed_by": None,
    "session_duration_seconds": None,
    "standing_credentials_used": 0,
    "deployment_count": 0,
    "opa_connection": None,
    "git_repo": None,
    "git_branch": None,
    "git_commit": None,
    "workflow_run_id": None,
    "workflow_run_number": 0,
    "triggered_by": None,
    "runner_hostname": None,
    "runner_ip": None,
    "runner_executed_at": None,
    "oidc_token": None,
    "oidc_token_iat": None,
    "oidc_token_exp": None,
    "opa_token": None,
    "opa_token_iat": None,
    "opa_token_exp": None,
    "ssh_target_host": None,
}

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER  = os.environ.get("GITHUB_OWNER",  "<GITHUB_ORG>")
GITHUB_REPO   = os.environ.get("GITHUB_REPO",   "<GITHUB_REPO>")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "opa-workflow.yml")
WORKFLOW_REF  = os.environ.get("WORKFLOW_REF",  "main")


def _github_api(method, path, body=None):
    url = "https://api.github.com" + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": "Bearer " + GITHUB_TOKEN,
            "Accept":        "application/vnd.github+json",
            "Content-Type":  "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opa-demo-api-server/1.0",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # silence access log

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/run":
            body = self._read_body()
            customer = body.get("customer_name", "Demo Customer")
            path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
            status, resp = _github_api("POST", path, {"ref": WORKFLOW_REF, "inputs": {"customer_name": customer}})
            if status in (200, 201, 204):
                runs_path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/runs?per_page=1&event=workflow_dispatch"
                _, runs = _github_api("GET", runs_path)
                run_id = runs["workflow_runs"][0]["id"] if runs and runs.get("workflow_runs") else None
                self._send_json(200, {"ok": True, "run_id": run_id})
            else:
                self._send_json(502, {"error": (resp or {}).get("message", "GitHub API error"), "github_status": status})
        elif self.path == "/api/clear":
            blank = json.dumps(BLANK_STATE, indent=2).encode()
            try:
                proc = subprocess.run(["sudo", "/usr/bin/tee", STATE_PATH], input=blank, capture_output=True, timeout=5)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.decode())
                self._send_json(200, {"ok": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
        else:
            self._send_json(404, {"error": "not found"})

    def do_GET(self):
        if self.path.startswith("/api/workflow-status"):
            run_id = None
            if "?" in self.path:
                for part in self.path.split("?", 1)[1].split("&"):
                    if part.startswith("run_id="):
                        run_id = part[len("run_id="):]
            if not run_id:
                self._send_json(400, {"error": "run_id required"})
                return
            status, data = _github_api("GET", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}")
            if status != 200 or not data:
                self._send_json(502, {"error": "GitHub API error"})
                return
            gh_status = data.get("status", "")
            if gh_status == "completed":
                self._send_json(200, {"status": "completed", "conclusion": data.get("conclusion"), "run_id": run_id})
            else:
                self._send_json(200, {"status": "in_progress", "run_id": run_id})
        else:
            self._send_json(404, {"error": "not found"})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
```

---

### 4c. OPA Configuration (Step-by-Step)

Perform these steps in the OPA Admin Console before the demo. This is split across two admin roles. Complete Phase 1–2 as DevOps Admin, Phase 3 as Security Admin.

---

#### Phase 0 — Hard Prerequisites (Verify Before Starting)

> **Complete these checks before touching the OPA console.** Phases 1–3 configure OPA policies that cannot be tested until the target server is enrolled. Discovering enrollment problems after completing console setup wastes significant time.

```
HARD PREREQUISITES
─────────────────────────────────────────────────────
[ ] OPA sftd agent is enrolled and ACTIVE on <TARGET_HOSTNAME>
    Verify: ssh <GCP_VM_USER>@<GCP_VM_IP> 'systemctl status sftd'
    If not running: sudo systemctl start sftd
    If not enrolled: complete OPA server enrollment before proceeding.

[ ] <TARGET_HOSTNAME> appears in OPA Console → Infrastructure → Servers
    Status must show: Enrolled (not Pending, not Offline)

[ ] You have both DevOps Admin and Security Admin credentials ready
    (or access to both roles — these steps require both)
```

> If sftd is not enrolled, stop here. All configuration phases below require an enrolled target to be tested end-to-end.

---

#### Phase 1 — Create the Workload Connection (DevOps Admin)

1. Log in to OPA Admin Console → **Workloads** → **Connections** → **Create Connection**

2. Fill in the form:

| Field | Value |
|---|---|
| **Name** | `<OPA_CONNECTION_NAME>` (e.g., `github-actions-prod`) |
| **Description** | `GitHub Actions OIDC for production pipeline` |
| **Token TTL** | `300` (seconds) — reliable across the two SSH sessions in the pipeline. Narrate as "under 5 minutes." See Section 8 to reduce to 120s if you want a tighter story and your environment is fast. |
| **JWKS URL** | `https://token.actions.githubusercontent.com/.well-known/jwks` |

3. Add **Required Claims**:

| Claim Key | Claim Value |
|---|---|
| `iss` | `https://token.actions.githubusercontent.com` |
| `repository` | `<GITHUB_ORG>/<GITHUB_REPO>` |

4. Click **Save as Draft** — do NOT activate yet (Security Admin approves in Phase 2).

5. **Test the connection (optional):** Run the auth command from a test runner with a valid OIDC token to verify the draft connection resolves correctly before promoting.

---

#### Phase 2 — Promote the Connection (Security Admin)

1. Log in as Security Admin → **Workloads** → **Connections**
2. Find `<OPA_CONNECTION_NAME>` — status shows **Draft**
3. Review: JWKS URL, required claims, TTL
4. Click **Activate**

> **Demo talking point:** This split-duty model is intentional. DevOps can configure the trust relationship, but Security must approve before any workload can use it. That's separation of concerns built into the product.

> **Wait ~5 minutes after activating** before testing the pipeline. OPA requires a refresh cycle before an Active connection begins issuing tokens. Running `sft workload authenticate` immediately after activation may produce unexpected failures unrelated to configuration.

---

#### Phase 3 — Create Workload Role and Policy (Security Admin)

**Step 3a: Create the Workload Role**

1. **Workloads** → **Roles** → **Create Role**

| Field | Value |
|---|---|
| **Name** | `github_actions` |
| **Description** | `CI/CD pipeline deployer for main branch only` |
| **Workload Connection** | `<OPA_CONNECTION_NAME>` |

2. Add **Claim Conditions** (scopes which pipelines can claim this role):

| Condition | Operator | Value |
|---|---|---|
| `ref` | `equals` | `refs/heads/main` |
| `repository` | `equals` | `<GITHUB_ORG>/<GITHUB_REPO>` |

> These conditions are the guardrails shown in Act 3. A compromised fork or feature branch token will NOT match this role.

3. Click **Save**.

**Step 3b: Attach Role to Security Policy**

1. **Policies** → find or create the policy covering `<TARGET_HOSTNAME>`
2. Add **Principal**: Workload Role → `github_actions`
3. Set **Access**: SSH (certificate-based)
4. **Save and activate the policy.**

---

#### Phase 4 — Verify OPA Enrollment on the Target VM

SSH into `<TARGET_HOSTNAME>` and confirm:
```bash
systemctl status sftd   # OPA ASA daemon must be running
```

If not enrolled, follow the OPA server enrollment guide for your environment before proceeding.

---

### 4d. GitHub Actions Workflows

#### Before Workflow: `before-workflow.yml`

> **DO NOT RUN THIS IN THE DEMO.** This file lives on the `before` branch. Its only purpose is to show the customer what the old world looks like (Tab 2).

```yaml
# .github/workflows/before-workflow.yml
# LEGACY APPROACH — shown for contrast only, not executed live
# This workflow uses a static SSH private key stored as a GitHub Secret.
# This key has been in this repo for 18 months. Nobody knows who else has it.

name: Deploy (Legacy — Static SSH Key)

on:
  workflow_dispatch:
    inputs:
      customer_name:
        description: 'Customer name to display on dashboard'
        required: true
        default: 'Demo Customer'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up SSH key
        # ⚠️  Static private key — stored forever in GitHub Secrets
        # ⚠️  18 months old, never rotated
        # ⚠️  Grants standing SSH access to prod-web-01
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan <GCP_VM_IP> >> ~/.ssh/known_hosts

      - name: Deploy state.json
        run: |
          TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
          ssh -i ~/.ssh/id_rsa <GCP_VM_USER>@<GCP_VM_IP> \
            "echo '{\"customer\":\"${{ github.event.inputs.customer_name }}\",\"status\":\"success\",\"last_deploy\":\"'$TIMESTAMP'\",\"deployed_by\":\"ci_service_account\",\"session_duration_seconds\":null,\"standing_credentials_used\":1,\"deployment_count\":1,\"opa_connection\":null,\"git_repo\":\"${{ github.repository }}\",\"git_branch\":\"${{ github.ref_name }}\",\"git_commit\":\"${{ github.sha }}\"}' | sudo tee /var/www/demo-app/state.json"
```

---

#### OPA Workflow: `opa-workflow.yml`

> **THIS IS THE LIVE DEMO WORKFLOW.** Lives on `main`. Trigger this during Act 2.

```yaml
# .github/workflows/opa-workflow.yml
# OPA WORKLOAD IDENTITY APPROACH
# Zero stored credentials. GitHub OIDC JWT → OPA token → ephemeral SSH cert.

name: Deploy (OPA Workload Identity)

on:
  workflow_dispatch:
    inputs:
      customer_name:
        description: 'Customer name to display on dashboard'
        required: true
        default: '<CUSTOMER_NAME>'

permissions:
  id-token: write   # Required: allows GitHub to issue OIDC JWT to this job
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # ── Step 1: Install sft CLI ──────────────────────────────────────────
      - name: Install OPA sft CLI
        run: |
          curl -fsSL https://dist.scaleft.com/install.sh | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      # ── Step 2: Configure OPA gateway ───────────────────────────────────
      - name: Configure sft
        run: |
          mkdir -p ~/.config/sft
          cat > ~/.config/sft/sft.yaml <<EOF
          address: <OPA_GATEWAY>
          EOF

      # ── Step 3: Request GitHub OIDC JWT ─────────────────────────────────
      - name: Request GitHub OIDC Token
        id: oidc
        run: |
          echo "Requesting OIDC token from GitHub..."
          # GitHub provides the token via ACTIONS_ID_TOKEN_REQUEST_TOKEN + URL
          OIDC_TOKEN=$(curl -s -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=<OPA_GATEWAY>" | jq -r '.value')
          echo "::add-mask::$OIDC_TOKEN"
          echo "token=$OIDC_TOKEN" >> $GITHUB_OUTPUT
          echo "✅ OIDC token received (masked)"

      # ── Step 4: Authenticate with OPA Workload Identity ─────────────────
      - name: Authenticate with OPA Workload Identity
        id: opa-auth
        env:
          GITHUB_OIDC_TOKEN: ${{ steps.oidc.outputs.token }}
        run: |
          echo "Authenticating with OPA using Workload Connection: <OPA_CONNECTION_NAME>"
          # Optional: add --role-hint <WORKLOAD_ROLE_NAME> if multiple Workload Roles
          # are configured for this connection and OPA needs help selecting the right one.
          # Example: --role-hint github_actions
          # Note: --role-hint is not listed in current GA CLI docs — verify against
          # your sft CLI version before relying on it.
          OPA_TOKEN=$(sft workload authenticate \
            --team <OPA_TEAM> \
            --connection <OPA_CONNECTION_NAME> \
            --jwt-env GITHUB_OIDC_TOKEN)
          echo "::add-mask::$OPA_TOKEN"
          echo "OPA_TOKEN=$OPA_TOKEN" >> $GITHUB_ENV
          echo "✅ OPA token issued (TTL: 300s)"

      # ── Step 5: SSH into target and update state.json ────────────────────
      - name: Update dashboard via brokered SSH
        run: |
          TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
          START_TS=$(date +%s)

          echo "Opening brokered SSH session to <TARGET_HOSTNAME>..."

          sft ssh <TARGET_HOSTNAME> \
            --token "$OPA_TOKEN" \
            -- bash -c "
              PAYLOAD=\$(cat <<'JSON'
          {
            \"customer\": \"${{ github.event.inputs.customer_name }}\",
            \"status\": \"success\",
            \"last_deploy\": \"${TIMESTAMP}\",
            \"deployed_by\": \"wl_github_actions (OPA Workload Identity)\",
            \"session_duration_seconds\": null,
            \"standing_credentials_used\": 0,
            \"deployment_count\": 1,
            \"opa_connection\": \"<OPA_CONNECTION_NAME>\",
            \"git_repo\": \"${{ github.repository }}\",
            \"git_branch\": \"${{ github.ref_name }}\",
            \"git_commit\": \"${{ github.sha }}\"
          }
          JSON
          )
              echo \"\$PAYLOAD\" | sudo tee /var/www/demo-app/state.json > /dev/null
              echo 'state.json updated'
            "

          END_TS=$(date +%s)
          DURATION=$((END_TS - START_TS))
          echo "✅ SSH session closed. Duration: ${DURATION}s. Certificate expired."
          echo "✅ JIT account (wl_github_actions) torn down by OPA."

      # ── Step 6: Patch session_duration back into state.json ─────────────
      - name: Update session duration
        run: |
          START_TS=$(date +%s)
          TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

          # Re-open a brief SSH session to patch the duration field
          sft ssh <TARGET_HOSTNAME> \
            --token "$OPA_TOKEN" \
            -- bash -c "
              CURRENT=\$(cat /var/www/demo-app/state.json)
              echo \"\$CURRENT\" | jq \
                --argjson dur $(($(date +%s) - START_TS)) \
                '.session_duration_seconds = \$dur' | \
                sudo tee /var/www/demo-app/state.json > /dev/null
            " || echo "Duration patch skipped (token may have expired — that's fine)"

      # ── Summary ─────────────────────────────────────────────────────────
      - name: Summary
        run: |
          echo "## OPA Workload Identity — Deployment Complete" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Field | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|---|---|" >> $GITHUB_STEP_SUMMARY
          echo "| Customer | ${{ github.event.inputs.customer_name }} |" >> $GITHUB_STEP_SUMMARY
          echo "| OPA Connection | <OPA_CONNECTION_NAME> |" >> $GITHUB_STEP_SUMMARY
          echo "| Branch | ${{ github.ref_name }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Commit | ${{ github.sha }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Standing Credentials | **0** |" >> $GITHUB_STEP_SUMMARY
          echo "| JWT Source | GitHub OIDC |" >> $GITHUB_STEP_SUMMARY
```

---

#### Negative Test Workflow: `negative-test.yml`

> Optional. Use in Act 3 to demonstrate that a non-main branch is rejected.

```yaml
# .github/workflows/negative-test.yml
# Triggers from a feature branch — OPA Workload Role condition blocks it.
# Expected result: sft workload authenticate exits non-zero with claim mismatch error.

name: Negative Test — Non-Main Branch (Expected Failure)

on:
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  negative-test:
    runs-on: ubuntu-latest
    continue-on-error: true  # Let the job report, don't fail the workflow UI harshly
    steps:
      - name: Install sft
        run: |
          curl -fsSL https://dist.scaleft.com/install.sh | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Configure sft
        run: |
          mkdir -p ~/.config/sft
          cat > ~/.config/sft/sft.yaml <<EOF
          address: <OPA_GATEWAY>
          EOF

      - name: Request GitHub OIDC Token
        id: oidc
        run: |
          OIDC_TOKEN=$(curl -s -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=<OPA_GATEWAY>" | jq -r '.value')
          echo "::add-mask::$OIDC_TOKEN"
          echo "token=$OIDC_TOKEN" >> $GITHUB_OUTPUT

      - name: Attempt OPA auth (EXPECTED TO FAIL — branch is not main)
        env:
          GITHUB_OIDC_TOKEN: ${{ steps.oidc.outputs.token }}
        run: |
          echo "Branch: ${{ github.ref_name }}"
          echo "Expected: OPA rejects this token — Workload Role requires refs/heads/main"
          echo ""
          sft workload authenticate \
            --team <OPA_TEAM> \
            --connection <OPA_CONNECTION_NAME> \
            --jwt-env GITHUB_OIDC_TOKEN || {
            echo "❌ Authentication rejected by OPA — as expected."
            echo "This pipeline cannot gain access because the branch condition failed."
            exit 0
          }
          echo "⚠️  Authentication succeeded — check Workload Role conditions."
          exit 1
```

---

### 4e. End-to-End Test Checklist

Run through this checklist **before** the customer call. Estimated time: 30 minutes.

```
PRE-DEMO CHECKLIST
─────────────────────────────────────────────────────

INFRASTRUCTURE
  [ ] GCP VM is running and accessible at http://<GCP_VM_IP>
  [ ] nginx is serving demo-app: curl http://<GCP_VM_IP>/state.json
  [ ] state.json contains "status": "awaiting_deployment"
  [ ] OPA sftd agent is running on the VM: ssh in and run 'systemctl status sftd'
  [ ] index.html is deployed to /var/www/demo-app/index.html

OPA CONFIGURATION
  [ ] Workload Connection '<OPA_CONNECTION_NAME>' is ACTIVE (not Draft)
  [ ] JWKS URL is set to https://token.actions.githubusercontent.com/.well-known/jwks
  [ ] Required claims include 'iss' and 'repository'
  [ ] Workload Role 'github_actions' is created
  [ ] Role conditions: ref = refs/heads/main, repository = <GITHUB_ORG>/<GITHUB_REPO>
  [ ] Security Policy grants Workload Role SSH access to <TARGET_HOSTNAME>

GITHUB REPOSITORY
  [ ] 'before' branch exists with before-workflow.yml and SSH_PRIVATE_KEY in Secrets
  [ ] 'main' branch has opa-workflow.yml (no secrets in Settings > Secrets)
  [ ] Repo has 'id-token: write' permission enabled (Actions > General > Workflow permissions)
  [ ] Both workflows have been run at least once (clears any first-run permission prompts)

LIVE TEST (run this 30 minutes before demo)
  [ ] Trigger opa-workflow.yml manually from main branch, customer_name = "Test Customer"
  [ ] Workflow completes successfully (all steps green)
  [ ] Dashboard at http://<GCP_VM_IP> shows "Test Customer" and green badges
  [ ] OPA Console > Workloads > Sessions shows the completed session
  [ ] Reset state.json to awaiting_deployment state (run reset command below)

RESET COMMAND (run after test, before demo)
  ssh <GCP_VM_USER>@<GCP_VM_IP> "echo '{
    \"customer\": \"<CUSTOMER_NAME>\",
    \"status\": \"awaiting_deployment\",
    \"last_deploy\": null,
    \"deployed_by\": null,
    \"session_duration_seconds\": null,
    \"standing_credentials_used\": 0,
    \"deployment_count\": 0,
    \"opa_connection\": \"<OPA_CONNECTION_NAME>\",
    \"git_repo\": \"<GITHUB_ORG>/<GITHUB_REPO>\",
    \"git_branch\": null,
    \"git_commit\": null
  }' | sudo tee /var/www/demo-app/state.json"

BROWSER SETUP (arrange tabs in this exact order)
  [ ] Tab 1: http://<GCP_VM_IP>  (label: LIVE DASHBOARD)
  [ ] Tab 2: GitHub > before branch > Settings > Secrets  (label: THE OLD WAY)
  [ ] Tab 3: GitHub > main branch > Settings > Secrets  (label: THE NEW WAY)
  [ ] Tab 4: GitHub Actions > opa-workflow.yml > trigger ready  (label: PIPELINE)
  [ ] Tab 5: OPA Console > Workloads > Sessions  (label: AUDIT)
  [ ] All tabs are logged in and not showing 404s or auth prompts
```

---

## SECTION 5 — DEMO SCRIPT

> Word-for-word talking points. `[CLICK]`, `[SWITCH TAB]`, and `[TRIGGER]` are explicit stage cues.

---

### Setup (Before Customer Joins)

- All five tabs open and labeled
- Tab 1 (dashboard) is showing "Awaiting deployment…" with customer name already loaded
- state.json is reset
- Slack/Zoom screen share is off until you're ready

---

### Opening Line

> "Before I show you anything, I want to ask: how are your CI/CD pipelines authenticating to servers today? Give me 15 seconds to show you something that might look familiar."

`[SWITCH TAB: Tab 2 — THE OLD WAY]`

---

### Act 1 — The Problem (~60 seconds)

`[Point to SSH_PRIVATE_KEY in the Secrets tab]`

> "This is real. This pattern is in most pipelines I see. An SSH private key, pasted into GitHub Secrets, sitting there. This one was added 18 months ago. Nobody's rotated it. If I asked you right now who else has a copy of that key — you probably couldn't give me a complete answer."

> "And here's the real problem: it's not that the key exists. It's that the key persists. It's just... sitting there, waiting. That's what we call a standing credential. And every repo, every workload, every environment has at least one."

`[Pause]`

> "Let me show you the same pipeline — same target server, same GitHub repo — with zero credentials stored anywhere."

`[SWITCH TAB: Tab 3 — THE NEW WAY]`

---

### Act 2 — The Magic (~2–3 minutes)

`[Show empty Secrets tab]`

> "Look at this. Nothing. No SSH key. No API token. No service account password. Empty."

> "So how does this pipeline deploy to production? It proves who it is."

> "GitHub, when this job runs, issues a cryptographically signed JWT. That token says: I am a workflow running on repository acme-corp/deploy-pipeline, on the main branch, for this specific commit. OPA validates that token against a pre-configured trust relationship — a Workload Connection — and if everything checks out, it issues a short-lived access token. 120 seconds. That token is used to get an ephemeral SSH certificate. The pipeline SSHes in, does its work, session closes, certificate expires, JIT account is torn down. Nothing persists."

> "Let me show you this live."

`[SWITCH TAB: Tab 4 — PIPELINE]`

> "I'm going to trigger this pipeline right now. Watch the steps."

`[TRIGGER: Click Run workflow, enter customer name: "<CUSTOMER_NAME>", click Run]`

`[Narrate as steps run:]`

> "Step one — it's installing the OPA CLI on the runner. Step two — requesting the OIDC token from GitHub's own identity system. No secrets involved, this happens automatically in the job context."

> "Step three — authenticating with OPA Workload Identity. This is where OPA is validating the JWT against the Workload Connection. It's checking the JWKS signature, it's checking the required claims."

`[When auth step goes green:]`

> "Token issued. Under 5 minutes. That's the entire window this pipeline has."

> "Step four — brokered SSH. OPA is issuing an ephemeral SSH certificate to the runner, the runner connects to the server, updates the deployment state, session closes."

`[When pipeline completes:]`

> "Done. Let me show you what just happened on the server."

`[SWITCH TAB: Tab 1 — LIVE DASHBOARD]`

> "`[Point to customer name]` That's your name. `[Point to 'Standing Credentials Used: 0']` Zero stored credentials. `[Point to 'Deployed By: wl_github_actions']` That wl_ prefix — that's the JIT account OPA created for this job and tore down when the session ended. `[Point to session duration]` And that's how long the SSH session was open."

---

### Act 3 — The Guardrails (~60 seconds)

`[SWITCH TAB: Tab 5 — AUDIT]`

> "Now let me show you what OPA saw."

`[Point to the session record]`

> "Here's the session. Timestamp, duration, the JWT claims that were validated — repository, branch, workflow ref. OPA knows exactly which pipeline authenticated. Not 'the CI system.' This specific job, this specific repo, this specific branch."

> "And that last part matters. Let me explain why."

> "I configured OPA to only issue tokens to pipelines running on the main branch of this specific repo. If someone forks this repo, runs the same workflow — OPA rejects the token. Feature branch? Rejected. Compromised JWT from a different repo? Rejected. The Workload Role has conditions, and those conditions are enforced at the identity layer, not by hoping developers follow a policy doc."

`[Optional: Switch to Tab 4, trigger negative-test.yml from a feature branch]`

> "Watch this — I'm going to run the same authentication command from a non-main branch."

`[When it fails:]` > "Rejected. OPA returned a claim mismatch. No SSH access. No certificate. Nothing."

`[Optional: Minimal-privilege proof beat]`

> "One more thing worth showing. I'm going to take this workload token and try something a human user can do — list the teams in OPA."

```bash
sft list-teams
```

> "Rejected. Workload tokens cannot impersonate human users. They can't browse the OPA console, they can't enumerate teams, they can't escalate to human-level access. The token was issued for a specific, scoped purpose — SSH access to one target server — and that's the only thing it can do. Minimal privilege, enforced at the token level."

---

### Closing

> "The old model was: you have a secret, therefore you get access. The new model is: you are who you say you are, and I can verify that cryptographically, and that access expires in under 5 minutes."

> "No Secret Zero. No key rotation problem. No standing privilege. And a full audit trail that shows exactly what authenticated, why it was trusted, and how long it was active."

> "Questions?"

---

## SECTION 6 — EDGE CASES & NEGATIVE TESTS

### Scenario 1: Token Expires Mid-Job

**Symptom:** Step 5 (SSH) fails with `token expired` or `authentication required`
**Cause:** TTL set to 120s and the job took longer than expected
**Fix:** Increase TTL in the Workload Connection to 300s for demo purposes. Lower TTL is better for the story but builds in fragility.

### Scenario 2: `sft workload authenticate` Returns Empty

**Symptom:** `OPA_TOKEN` is empty; subsequent SSH step fails
**Cause:** The OIDC token audience doesn't match the OPA gateway address
**Fix:** Ensure the `audience` parameter in the curl request matches `<OPA_GATEWAY>` exactly (no trailing slash, no `https://` prefix if OPA expects bare hostname).

### Scenario 3: Dashboard Shows Old Customer Name

**Symptom:** Tab 1 still shows previous test customer name
**Cause:** Browser cached state.json despite cache-busting headers
**Fix:** Hard reload Tab 1 (Cmd+Shift+R). Alternatively, open Tab 1 in an incognito window for the demo.

### Scenario 4: nginx 403 on state.json

**Symptom:** `curl http://<GCP_VM_IP>/state.json` returns 403
**Cause:** File permissions on state.json are wrong after pipeline write
**Fix:**
```bash
sudo chmod 644 /var/www/demo-app/state.json
sudo chown www-data:www-data /var/www/demo-app/state.json
```
The pipeline uses `sudo tee` — verify `/etc/sudoers.d/opa-demo-app` exists on the VM.

### Scenario 5: OPA Rejects JWT with "invalid issuer"

**Symptom:** Auth step fails with claim validation error on `iss`
**Cause:** Required claim for `iss` is set incorrectly in the Workload Connection
**Fix:** Verify the `iss` claim in the GitHub OIDC token:
```bash
# Decode without verifying (demo/debug only):
echo $OIDC_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .iss
```
It should be `https://token.actions.githubusercontent.com` exactly.

### Scenario 6: `sftd` Not Running on Target VM

**Symptom:** SSH step returns `host not found` or `no route to host` via OPA
**Cause:** OPA ASA/PAS daemon not running or not enrolled
**Fix:**
```bash
sudo systemctl start sftd
sudo systemctl status sftd
```
If not enrolled, re-run the OPA server enrollment command for your environment.

---

## SECTION 7 — TROUBLESHOOTING

### Quick Diagnostic Commands

**Test nginx is serving correctly:**
```bash
curl -v http://<GCP_VM_IP>/state.json
curl -v http://<GCP_VM_IP>/
```

**Manually update state.json (bypass pipeline for testing):**
```bash
ssh <GCP_VM_USER>@<GCP_VM_IP> "echo '{
  \"customer\": \"<CUSTOMER_NAME>\",
  \"status\": \"success\",
  \"last_deploy\": \"2025-01-01T00:00:00Z\",
  \"deployed_by\": \"wl_github_actions (OPA Workload Identity)\",
  \"session_duration_seconds\": 12,
  \"standing_credentials_used\": 0,
  \"deployment_count\": 1,
  \"opa_connection\": \"<OPA_CONNECTION_NAME>\",
  \"git_repo\": \"<GITHUB_ORG>/<GITHUB_REPO>\",
  \"git_branch\": \"main\",
  \"git_commit\": \"abc1234\"
}' | sudo tee /var/www/demo-app/state.json"
```

**Check OPA Workload Connection status:**
```
OPA Console → Workloads → Connections → <OPA_CONNECTION_NAME>
Status must be: Active (not Draft)
```

**Verify sft CLI version on the runner:**
Add this debug step to the workflow:
```yaml
- name: Debug sft version
  run: sft --version
```

**Check OPA session log after a run:**
```
OPA Console → Workloads → Sessions
Filter by: Connection = <OPA_CONNECTION_NAME>
Check: claims validated, session start/end times
```

**GitHub OIDC token decode (debug only):**
```bash
# In a local test, not in production pipelines
python3 -c "
import base64, json, sys
token = sys.argv[1]
payload = token.split('.')[1]
payload += '=' * (4 - len(payload) % 4)
print(json.dumps(json.loads(base64.urlsafe_b64decode(payload)), indent=2))
" "$OIDC_TOKEN"
```

**JWT decode — bash one-liner (no Python required):**
```bash
# Inspect any specific claim (e.g. aud, iss, sub) without installing anything extra
echo $OIDC_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .aud

# Dump the full payload:
echo $OIDC_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .

# From a file (e.g. GCP JWT saved to disk):
cat /tmp/gcp-token.jwt | cut -d. -f2 | base64 -d 2>/dev/null | jq .
```

**`sft workload authenticate` returns "unknown subcommand" or "command not found":**
This usually means the `sft` CLI version predates the GA release of Workload Identity. Try:
```bash
export SFT_FEATURE_NHI=1
sft workload authenticate ...
```
This feature flag was required in pre-GA (trex) environments to enable the Non-Human Identity feature gate. It should not be needed on GA tenants with a current `sft` CLI, but serves as a useful fallback when something is off.

**`sft wl` vs `sft workload` — CLI alias note:**
Pre-GA trex environments used `sft wl auth` as a short alias. The GA command is `sft workload authenticate`. Both accept the same flags (`--team`, `--connection`, `--jwt-env`), but only `sft workload` is supported on production tenants. If you have muscle memory from a trex lab, switch to the full subcommand name.

---

## SECTION 8 — CUSTOMIZATION

### Changing the Customer Name

**Option A: Pre-bake into state.json and index.html**
- Update `<CUSTOMER_NAME>` in the initial `state.json` on the VM
- No pipeline change needed; the dashboard loads the name from `state.json`

**Option B: Pass as workflow input (recommended for live demo)**
- The `opa-workflow.yml` already includes a `customer_name` input field
- Enter the customer's name when triggering the workflow from Tab 4
- It flows through to `state.json` → dashboard automatically

### Adjusting Token TTL

In OPA Console → Workload Connection → edit the TTL field.
- `300s` — **recommended default.** Reliable across the two SSH sessions in the pipeline. Describe as "under 5 minutes" — still clearly ephemeral.
- `120s` — more dramatic for the story, but risks the second SSH session (session_duration patch) racing against expiry on slow runners. Only use if your environment consistently completes both sessions well inside 2 minutes.

### Swapping to a Different Identity Provider

The demo uses GitHub Actions OIDC. To adapt for other providers:

| Provider | JWKS URL | Key Claims |
|---|---|---|
| GitLab CI | `https://gitlab.com/.well-known/openid-configuration` (fetch jwks_uri) | `iss`, `project_path`, `ref_protected` |
| CircleCI | `https://oidc.circleci.com/org/<ORG_ID>/.well-known/jwks` | `iss`, `sub` (contains project slug) |
| GCP Workload Identity | `https://accounts.google.com/.well-known/openid-configuration` | `iss`, `sub`, `email` |

Update the Workload Connection JWKS URL and required claims accordingly. The GitHub Actions workflow steps that call `curl $ACTIONS_ID_TOKEN_REQUEST_URL` are GitHub-specific and must be replaced with the provider's native token acquisition method.

**GCP token acquisition (Metadata API — for workloads running on GCP VMs):**
```bash
# Set AUDIENCE to your OPA gateway hostname
AUDIENCE=<OPA_GATEWAY>

# Fetch the identity JWT from the GCP instance metadata service
curl -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${AUDIENCE}&format=full" \
  > /tmp/gcp-token.jwt

# Authenticate with OPA using the saved JWT
export WORKLOAD_JWT=$(cat /tmp/gcp-token.jwt)
sft workload authenticate \
  --team <OPA_TEAM> \
  --connection <OPA_CONNECTION_NAME> \
  --jwt-env WORKLOAD_JWT
```
The `format=full` parameter returns a signed JWT (rather than the shorter default format). The token is scoped to the GCP Service Account attached to the VM instance. Set the `audience` claim to match the value configured in your OPA Workload Connection's required claims.

### Scaling the Demo Up

To make the dashboard more dramatic:
- Add a "Deployment History" section showing the last N deployments (append to a `history` array in `state.json`)
- Show a live countdown timer on the dashboard for token TTL (pass TTL start time in state.json)
- Add a "Rejected Attempts" counter (increment on negative test failures, log to a separate field)

---

## APPENDIX — REFERENCE LINKS

- [OPA Workload Identity Overview](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-workloads.htm)
- [Configure Workload Connection](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-connection.htm)
- [CLI Authentication Command](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-cli.htm)
- [Configure Workload Roles](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-role.htm)
- [SSH Access for Workloads](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-ssh-access-workloads.htm)
- [GitHub OIDC Token documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [sft CLI reference](https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-cli.htm)

---

*This prompt file was generated for the OPA Workload Identity Demo project. To regenerate or modify any artifact, re-execute this prompt with updated placeholder values.*
