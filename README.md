# OPA Workload Identity for Automation — Demo Kit

A demo kit for Solutions Engineers to showcase **Workload Identity for Automation**, a GA feature in Okta Privileged Access (OPA). The demo shows how CI/CD pipelines can authenticate to OPA using GitHub's native OIDC identity — no static keys, no Secret Zero.

A live GitHub Actions pipeline deploys to a GCP VM with zero stored credentials. The customer watches a Mission Control dashboard update in real time while OPA validates a GitHub OIDC JWT, issues a short-lived token, and grants ephemeral brokered SSH access.

**Three-act structure:**
1. **The Problem** — static SSH key sitting in GitHub Secrets for 18 months
2. **The Magic** — empty Secrets tab, live pipeline run, dashboard updates
3. **The Guardrails** — OPA session log with JWT claims; negative test rejecting a non-main branch

---

## Prerequisites

- GCP VM running Ubuntu 22.04, enrolled in OPA (`sftd` active)
- OPA tenant with DevOps Admin + Security Admin access
- GitHub repo with Actions enabled and `id-token: write` permission
- `sft` CLI available (installed by the workflow at runtime on the runner)
- GitHub Personal Access Token with `repo` + `workflow` scopes

---

## Placeholder Substitution

After cloning, substitute the following placeholders across all files before deploying:

| Placeholder | What to substitute | Example |
|---|---|---|
| `<OPA_TEAM_URL>` | Your OPA tenant hostname | `myteam.pam.oktapreview.com` |
| `<OPA_TEAM>` | Your OPA team slug | `myteam` |
| `<WORKLOAD_CONNECTION_NAME>` | Name of the Workload Connection you create in OPA | `github-actions-prod` |
| `<WORKLOAD_ROLE_NAME>` | Name of the Workload Role you create in OPA | `github_actions` |
| `<TARGET_SERVER_HOSTNAME>` | Hostname of the target GCP VM enrolled in OPA | `target-server-01` |
| `<GITHUB_ORG>/<GITHUB_REPO>` | Your GitHub org and repo where this code lives | `myorg/opa-wi-demo` |
| `<GITHUB_ORG>` | Your GitHub org name | `myorg` |
| `<GITHUB_PAT>` | GitHub Personal Access Token (needs `repo` + `workflow` scopes) | — |
| `<CUSTOMER_NAME>` | Customer name to display on the Mission Control dashboard | `acme_corp` |

---

## Deployment Steps

1. **Clone this repo** and substitute all placeholders above across all files.

2. **Run `setup/vm-setup.sh`** on your target GCP VM (Ubuntu 22.04):
   ```bash
   bash setup/vm-setup.sh
   ```

3. **Copy dashboard files** to the VM:
   ```bash
   scp demo-app/index.html <VM_USER>@<VM_IP>:/var/www/demo-app/index.html
   scp demo-app/state.json <VM_USER>@<VM_IP>:/var/www/demo-app/state.json
   scp demo-app/api-server.py <VM_USER>@<VM_IP>:/var/www/demo-app/api-server.py
   ```

4. **Install and start the API server**:
   ```bash
   bash setup/install-api-server.sh
   ```
   Then edit `/etc/systemd/system/api-server.service` to fill in `<GITHUB_PAT>`, `<GITHUB_ORG>`, `<GITHUB_REPO>`, and reload:
   ```bash
   sudo systemctl daemon-reload && sudo systemctl restart api-server
   ```

5. **Configure OPA** — in your OPA tenant, complete these four steps in order:
   - Create a **Workload Connection** named `<WORKLOAD_CONNECTION_NAME>` (GitHub OIDC provider)
   - Create a **Workload Role** named `<WORKLOAD_ROLE_NAME>` scoped to `repo:<GITHUB_ORG>/<GITHUB_REPO>:ref:refs/heads/main`
   - Create a **Security Policy** granting the Workload Role SSH access to `<TARGET_SERVER_HOSTNAME>`
   - Wait ~5 minutes after promoting the Workload Connection to Active before testing

6. **Push to GitHub** — push your customised repo to `<GITHUB_ORG>/<GITHUB_REPO>` on the `main` branch.

7. **Trigger the demo** — from the GitHub Actions tab, trigger the `Deploy (OPA Workload Identity)` workflow. Watch the Mission Control dashboard at `http://<VM_IP>/` update in real time.

---

## File Inventory

| File | Purpose |
|---|---|
| `setup/vm-setup.sh` | Installs nginx, creates demo-app dir, configures sudo rule for OPA JIT user |
| `setup/install-api-server.sh` | Installs api-server.py as a systemd service |
| `setup/fix-nginx.sh` | Patches nginx config to add `/api/` proxy block |
| `demo-app/index.html` | Mission Control dashboard (auto-polls `state.json` every 3s) |
| `demo-app/state.json` | Initial blank state — written by GitHub Actions workflow via SSH |
| `demo-app/api-server.py` | Python API server — Run Pipeline + Clear buttons backend |
| `.github/workflows/opa-workflow.yml` | Act 2 live demo workflow (OPA Workload Identity) |
| `.github/workflows/negative-test.yml` | Act 3 negative test workflow (non-main branch rejected) |
| `CLAUDE.md` | Project context for Claude Code — loaded automatically when working in this folder |
