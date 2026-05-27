# OPA Workload Identity Demo — AI Context File

This file is loaded automatically by Claude Code. It describes the **actual project on disk** — architecture, file map, state schema, UI constraints, and deployment config. Use it as ground truth for all AI-assisted work on this repo.

---

## 1. Project Architecture

```
GitHub Actions Job
        │
        ▼
1. Request OIDC JWT from GitHub's token endpoint
        │
        ▼
2. sft workload authenticate
     --team <OPA_TEAM>
     --connection <WORKLOAD_CONNECTION_NAME>
     --jwt-env ACTIONS_ID_TOKEN_REQUEST_TOKEN
        │
        ▼
3. OPA validates JWT against Workload Connection (JWKS URL + claims)
        │
        ▼
4. OPA issues short-lived OPA_TOKEN
        │
        ▼
5. Workflow writes updated state.json via brokered SSH
   (sft ssh <TARGET_SERVER_HOSTNAME> -- tee /var/www/demo-app/state.json)
        │
        ▼
6. Dashboard JS polls /state.json every 3 seconds → re-renders UI
```

### Supporting Services on GCP VM

| Service | Details |
|---|---|
| **api-server.py** | Python stdlib HTTP server on `127.0.0.1:8765` |
| **nginx** | Serves `/` from `/var/www/demo-app/`; proxies `/api/` to `127.0.0.1:8765` |
| **systemd** | `api-server.service` keeps api-server running persistently |

### Live Okta Event Pulls

The dashboard fetches two live events from the Okta System Log via api-server:

- `pam.user_creds.issue` — matched by `actor.id` == OIDC JWT `sub` claim
- `pam.server.ssh_login` — matched by `target[].displayName` == SSH target hostname

---

## 2. File Map

| File | Purpose |
|---|---|
| `demo-app/index.html` | Single-file dashboard — all HTML, CSS, and JS in one file |
| `demo-app/api-server.py` | Python stdlib HTTP server; 6 endpoints (see below) |
| `demo-app/state.json` | Live state file; written by workflow via SSH, read by dashboard JS every 3s |
| `.github/workflows/opa-workflow.yml` | Primary live demo workflow (Act 2) |
| `.github/workflows/negative-test.yml` | Negative test workflow — expected auth failure |
| `setup/vm-setup.sh` | GCP VM one-time init: nginx, demo-app directory, sftd enrollment |
| `setup/install-api-server.sh` | Installs api-server.py as a systemd service |
| `setup/fix-nginx.sh` | Patches nginx config to add `/api/` proxy block |

### api-server.py Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/run` | Dispatch `workflow_dispatch` event via GitHub API |
| POST | `/api/clear` | Reset state.json to blank template (preserves `workflow_run_number`) |
| GET | `/api/workflow-status` | Poll run status: `{status: in_progress\|completed}` |
| GET | `/api/workflow-steps` | Return step-level progress for a run (filtered to 7 named steps) |
| GET | `/api/audit-event` | Pull live `pam.user_creds.issue` event from Okta System Log |
| GET | `/api/ssh-login-event` | Pull live `pam.server.ssh_login` event from Okta System Log |

---

## 3. State Schema

All 24 fields in `state.json`. Written by the workflow via SSH (`tee`), read by dashboard JS.

| Field | Type | Written By | Example |
|---|---|---|---|
| `customer` | string\|null | workflow input | `"peter_farley"` |
| `status` | string | workflow | `"success"`, `"awaiting_deployment"` |
| `last_deploy` | string\|null | workflow | `"2024-01-15T14:32:01Z"` |
| `deployed_by` | string\|null | workflow (hardcoded) | `"wl_<WORKLOAD_ROLE_NAME> (OPA Workload Identity)"` |
| `session_duration_seconds` | number\|null | workflow Step 6 (second SSH step) | `47` |
| `standing_credentials_used` | number | workflow (always 0) | `0` |
| `deployment_count` | number | workflow (incremented) | `3` |
| `opa_connection` | string\|null | workflow | `"<WORKLOAD_CONNECTION_NAME>"` |
| `git_repo` | string\|null | workflow | `"<GITHUB_ORG>/<GITHUB_REPO>"` |
| `git_branch` | string\|null | workflow | `"main"` |
| `git_commit` | string\|null | workflow | `"a1b2c3d"` |
| `workflow_run_id` | number\|null | workflow | `12345678` |
| `workflow_run_number` | number | workflow (cumulative, never resets) | `12` |
| `triggered_by` | string\|null | workflow | `"iampeterpam"` |
| `runner_hostname` | string\|null | workflow | `"fv-az123-456"` |
| `runner_ip` | string\|null | workflow | `"10.1.0.5"` |
| `runner_executed_at` | string\|null | workflow | `"2024-01-15T14:31:55Z"` |
| `oidc_token` | string\|null | workflow | raw JWT string |
| `oidc_token_iat` | number\|null | workflow | `1705328315` |
| `oidc_token_exp` | number\|null | workflow | `1705331915` |
| `opa_token` | string\|null | workflow | raw OPA token string |
| `opa_token_iat` | number\|null | workflow | `1705328320` |
| `opa_token_exp` | number\|null | workflow | `1705328920` |
| `ssh_target_host` | string\|null | workflow | `"<TARGET_SERVER_HOSTNAME>"` |

> **Note:** `session_duration_seconds` is written in a second SSH step (Step 6) after the main job completes. It may be null if the OPA token expired before that step ran.

---

## 4. UI/UX Rules

Hard constraints for future AI sessions. Do not violate these without explicit instruction.

### Layout

- **Pipeline Execution** (`.steps-panel`) must remain a **vertical checklist** in a fixed **280px left column**. Do not reflow to horizontal or grid.
- **Trust Chain** (`.flow-track`) must remain a **3-node horizontal flex layout**. Do not add nodes, change to grid, or alter the node count.
- **`hero-mid-row`** is a **2-column grid**. Do not modify without testing ≤768px breakpoint.
- **`evidence-card-full`** sections are the **single source of truth** for audit event display. Do not duplicate their data elsewhere on the dashboard.

### Colors (locked palette)

| Token | Value | Usage |
|---|---|---|
| OPA blue | `#0061F2` | Primary brand, active states, links |
| Success green | `#1e7e34` | Success outcomes, done steps |
| Dark text | `#1d1d21` | Body copy |
| Page bg | `#f4f4f4` | Page background |
| Card bg | `#ffffff` | Card surfaces |

### CSS Rules

- Do **not** introduce `overflow: hidden` on any card ancestor — use `overflow-x: clip` to avoid clipping absolutely-positioned tooltips.
- `white-space: nowrap` is **required** on `.flow-arrow-label`. Do not remove it.
- Do **not** add `overflow: hidden` to `.flow-track` or its parents.

### Tooltips

- All tooltips use `position: absolute; top: calc(100% + 8px)`.
- Triggered by `.info-icon-wrapper:hover`.
- Tooltip containers must have a non-`hidden` overflow ancestor — use `overflow-x: clip` on containing cards.

---

## 5. Hardcoded Config Values

Reference values for redeployment. These are baked into the workflow and api-server environment.

| Config | Value |
|---|---|
| OPA tenant URL | `https://<OPA_TEAM_URL>` |
| OPA team | `<OPA_TEAM>` |
| Workload Connection name | `<WORKLOAD_CONNECTION_NAME>` |
| Workload Role (hint) | `<WORKLOAD_ROLE_NAME>` |
| SSH target hostname | `<TARGET_SERVER_HOSTNAME>` |
| GitHub owner/repo | `<GITHUB_ORG>/<GITHUB_REPO>` |
| API server host:port | `127.0.0.1:8765` |
| State file path on VM | `/var/www/demo-app/state.json` |
| JIT workload username | `wl_<WORKLOAD_ROLE_NAME>` |
| Workflow file | `opa-workflow.yml` |
| Workflow ref | `main` |

---

## 6. Known Constraints & Gotchas

- **5-minute activation delay:** OPA requires ~5 minutes after a Workload Connection is promoted to Active before it begins issuing tokens. Do not test immediately after promotion.
- **`session_duration_seconds` may be null:** It is patched via a second SSH step (Step 6). If the OPA token expires before that step runs, this field remains null.
- **`/api/clear` preserves `workflow_run_number`:** This is a cumulative counter that never resets. All other fields return to null/blank.
- **Negative test branch requirement:** The negative-test workflow must run from a **non-`main` branch** to trigger the expected auth failure (the Workload Connection is scoped to `main`).
- **`sftd` enrollment required:** `sftd` must be enrolled on the VM and the enrolled hostname must match `$(hostname)`. SSH brokering will fail if there is a mismatch.
- **No individual token revocation:** To block new token issuance, deactivate the Workload Connection. There is no per-token revocation mechanism.
- **Workload identities not listable:** OPA provides no public API to list or fetch active workload identities.
- **`sft` CLI required on runner:** The GitHub Actions runner must have `sft` installed. The workflow includes an install step for this.
