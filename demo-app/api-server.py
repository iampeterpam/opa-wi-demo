#!/usr/bin/env python3
"""
OPA WI Demo — API server
Listens on 127.0.0.1:8765. Zero external dependencies (stdlib only).

Endpoints:
  POST /api/run             — dispatch workflow_dispatch event via GitHub API
  POST /api/clear           — reset state.json to blank template
  GET  /api/workflow-status — poll run status; returns {status: in_progress|completed}
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

# Injected at service start — read from environment
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "<GITHUB_ORG>")
GITHUB_REPO  = os.environ.get("GITHUB_REPO",  "<GITHUB_REPO>")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "opa-workflow.yml")
WORKFLOW_REF  = os.environ.get("WORKFLOW_REF",  "main")


def _github_api(method, path, body=None):
    """Make a GitHub API call. Returns (status_code, parsed_json_or_None)."""
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

    def log_message(self, fmt, *args):  # silence access log noise
        pass

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

    # ── OPTIONS (CORS preflight) ──────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── POST ─────────────────────────────────────────────────────────────
    def do_POST(self):
        if self.path == "/api/run":
            self._handle_run()
        elif self.path == "/api/clear":
            self._handle_clear()
        else:
            self._send_json(404, {"error": "not found"})

    # ── GET ──────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path.startswith("/api/workflow-status"):
            self._handle_workflow_status()
        else:
            self._send_json(404, {"error": "not found"})

    # ── Handlers ─────────────────────────────────────────────────────────

    def _handle_run(self):
        body = self._read_body()
        customer = body.get("customer_name", "Demo Customer")

        path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
        status, resp = _github_api("POST", path, {
            "ref": WORKFLOW_REF,
            "inputs": {"customer_name": customer},
        })

        if status in (200, 201, 204):
            # Fetch the newly queued run id (most recent queued/in_progress run)
            runs_path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/runs?per_page=1&event=workflow_dispatch"
            _, runs = _github_api("GET", runs_path)
            run_id = None
            if runs and runs.get("workflow_runs"):
                run_id = runs["workflow_runs"][0]["id"]
            self._send_json(200, {"ok": True, "run_id": run_id})
        else:
            msg = (resp or {}).get("message", "GitHub API error")
            self._send_json(502, {"error": msg, "github_status": status})

    def _handle_clear(self):
        blank = json.dumps(BLANK_STATE, indent=2).encode()
        try:
            proc = subprocess.run(
                ["sudo", "/usr/bin/tee", STATE_PATH],
                input=blank, capture_output=True, timeout=5
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode())
            self._send_json(200, {"ok": True})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_workflow_status(self):
        # Parse ?run_id=<id> from query string
        run_id = None
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("run_id="):
                    run_id = part[len("run_id="):]

        if not run_id:
            self._send_json(400, {"error": "run_id required"})
            return

        path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}"
        status, data = _github_api("GET", path)

        if status != 200 or not data:
            self._send_json(502, {"error": "GitHub API error", "github_status": status})
            return

        gh_status     = data.get("status", "")   # queued / in_progress / completed
        gh_conclusion = data.get("conclusion")    # success / failure / etc.

        if gh_status == "completed":
            self._send_json(200, {
                "status":     "completed",
                "conclusion": gh_conclusion,
                "run_id":     run_id,
            })
        else:
            self._send_json(200, {"status": "in_progress", "run_id": run_id})


if __name__ == "__main__":
    host, port = "127.0.0.1", 8765
    print(f"OPA demo API server listening on {host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()
