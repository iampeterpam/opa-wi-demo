#!/usr/bin/env python3
"""
OPA WI Demo — API server
Listens on 127.0.0.1:8765. Zero external dependencies (stdlib only).

Endpoints:
  POST /api/run              — dispatch workflow_dispatch event via GitHub API
  POST /api/clear            — reset state.json to blank template
  GET  /api/workflow-status  — poll run status; returns {status: in_progress|completed}
  GET  /api/workflow-steps   — return step-level progress for a run
  GET  /api/audit-event      — pull live pam.user_creds.issue event from Okta System Log
  GET  /api/ssh-login-event  — pull live pam.server.ssh_login event from Okta System Log
"""

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
import urllib.parse
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
OKTA_API_TOKEN  = os.environ.get("OKTA_API_TOKEN", "")
OKTA_TENANT_URL = os.environ.get("OKTA_TENANT_URL", "")  # e.g. https://pfarley.pam.oktapreview.com

STEPS_TO_SHOW = {
    'Checkout',
    'Install OPA sft CLI',
    'Configure sft',
    'Request GitHub OIDC Token',
    'Authenticate with OPA Workload Identity',
    'Update dashboard via brokered SSH',
    'Update session duration',
}


def _okta_api(path, params=None):
    """GET request to Okta System Log API. Returns (status_code, parsed_json_or_None)."""
    url = OKTA_TENANT_URL.rstrip('/') + path
    if params:
        url += '?' + '&'.join(k + '=' + urllib.parse.quote(str(v)) for k, v in params.items())
    req = urllib.request.Request(
        url, method='GET',
        headers={
            'Authorization': 'SSWS ' + OKTA_API_TOKEN,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'opa-demo-api-server/1.0',
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
        elif self.path.startswith("/api/workflow-steps"):
            self._handle_workflow_steps()
        elif self.path.startswith("/api/ssh-login-event"):
            self._handle_ssh_login_event()
        elif self.path.startswith("/api/audit-event"):
            self._handle_audit_event()
        else:
            self._send_json(404, {"error": "not found"})

    # ── Handlers ─────────────────────────────────────────────────────────

    def _handle_run(self):
        body = self._read_body()
        customer = body.get("customer_name", "")

        runs_path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/runs?per_page=1&event=workflow_dispatch"

        # Snapshot the most recent run id before dispatch so we can detect the new one
        _, pre_runs = _github_api("GET", runs_path)
        pre_run_id = None
        if pre_runs and pre_runs.get("workflow_runs"):
            pre_run_id = pre_runs["workflow_runs"][0]["id"]

        path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
        status, resp = _github_api("POST", path, {
            "ref": WORKFLOW_REF,
            "inputs": {"customer_name": customer},
        })

        if status in (200, 201, 204):
            # Poll until GitHub registers the newly queued run (different id from pre-dispatch)
            new_run_id = None
            for _ in range(10):
                time.sleep(1)
                _, runs = _github_api("GET", runs_path)
                if runs and runs.get("workflow_runs"):
                    latest_id = runs["workflow_runs"][0]["id"]
                    if latest_id != pre_run_id:
                        new_run_id = latest_id
                        break
            self._send_json(200, {"ok": True, "run_id": new_run_id})
        else:
            msg = (resp or {}).get("message", "GitHub API error")
            self._send_json(502, {"error": msg, "github_status": status})

    def _handle_clear(self):
        # Preserve the cumulative run number — clear wipes evidence, not history
        preserved_run_number = 0
        try:
            with open(STATE_PATH) as f:
                current = json.load(f)
            preserved_run_number = current.get("workflow_run_number") or 0
        except Exception:
            pass
        blank_with_count = dict(BLANK_STATE)
        blank_with_count["workflow_run_number"] = preserved_run_number
        blank = json.dumps(blank_with_count, indent=2).encode()
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

    def _handle_workflow_steps(self):
        run_id = None
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("run_id="):
                    run_id = part[len("run_id="):]

        if not run_id:
            self._send_json(400, {"error": "run_id required"})
            return

        path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/{run_id}/jobs"
        status, data = _github_api("GET", path)

        if status != 200 or not data:
            self._send_json(502, {"error": "GitHub API error", "github_status": status})
            return

        jobs = data.get("jobs", [])
        steps = []
        if jobs:
            for raw_step in jobs[0].get("steps", []):
                name = raw_step.get("name", "")
                if name in STEPS_TO_SHOW:
                    steps.append({
                        "name":       name,
                        "status":     raw_step.get("status", "queued"),
                        "conclusion": raw_step.get("conclusion"),
                    })

        self._send_json(200, {"steps": steps})

    def _handle_audit_event(self):
        # Parse query string: ?since=<iso>&until=<iso>&actor_id=<url-encoded>
        params = {}
        if '?' in self.path:
            qs = self.path.split('?', 1)[1]
            for part in qs.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = urllib.parse.unquote(v)

        since    = params.get('since')
        until    = params.get('until')
        actor_id = params.get('actor_id')  # decoded JWT sub claim

        if not since or not until or not actor_id:
            self._send_json(400, {'error': 'since, until, and actor_id are required'})
            return

        if not OKTA_API_TOKEN or not OKTA_TENANT_URL:
            self._send_json(503, {'error': 'Okta credentials not configured'})
            return

        status, data = _okta_api('/api/v1/logs', {
            'filter': 'eventType eq "pam.user_creds.issue"',
            'since':  since,
            'until':  until,
            'sortOrder': 'DESCENDING',
            'limit':  '25',
        })

        if status != 200 or not isinstance(data, list):
            self._send_json(502, {'error': 'Okta API error', 'okta_status': status})
            return

        # Find the event whose actor.id matches the workload JWT sub claim
        match = None
        for event in data:
            actor = event.get('actor', {})
            if actor.get('type') == 'WorkloadPrincipal' and actor.get('id') == actor_id:
                match = event
                break

        if not match:
            self._send_json(404, {'found': False})
            return

        # Extract fields from the matched event
        actor   = match.get('actor', {})
        client  = match.get('client', {})
        outcome = match.get('outcome', {})
        targets = match.get('target', [])
        debug   = match.get('debugContext', {}).get('debugData', {})

        result = {
            'found':             True,
            'uuid':              match.get('uuid'),
            'published':         match.get('published'),
            'severity':          match.get('severity'),
            'display_message':   match.get('displayMessage'),
            'outcome':           outcome.get('result'),
            'actor_type':        actor.get('type'),
            'actor_id':          actor.get('id'),
            'client_ip':         client.get('ipAddress'),
            'user_agent':        (client.get('userAgent') or {}).get('rawUserAgent'),
            'target0_name':      targets[0].get('displayName') if len(targets) > 0 else None,
            'target1_name':      targets[1].get('displayName') if len(targets) > 1 else None,
            'x509_fingerprint':  debug.get('x509KeyFingerprint'),  # null if not present
            'server_hostnames':  debug.get('ServerHostnames'),
        }
        self._send_json(200, result)

    def _handle_ssh_login_event(self):
        # Parse query string: ?since=<iso>&until=<iso>&target_host=<hostname>
        params = {}
        if '?' in self.path:
            qs = self.path.split('?', 1)[1]
            for part in qs.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = urllib.parse.unquote(v)

        since       = params.get('since')
        until       = params.get('until')
        target_host = params.get('target_host')

        if not since or not until or not target_host:
            self._send_json(400, {'error': 'since, until, and target_host are required'})
            return

        if not OKTA_API_TOKEN or not OKTA_TENANT_URL:
            self._send_json(503, {'error': 'Okta credentials not configured'})
            return

        status, data = _okta_api('/api/v1/logs', {
            'filter': 'eventType eq "pam.server.ssh_login"',
            'since':  since,
            'until':  until,
            'sortOrder': 'DESCENDING',
            'limit':  '25',
        })

        if status != 200 or not isinstance(data, list):
            self._send_json(502, {'error': 'Okta API error', 'okta_status': status})
            return

        # Find the event whose target displayName matches the SSH target host
        match = None
        for event in data:
            targets = event.get('target', [])
            for t in targets:
                if t.get('displayName', '').lower() == target_host.lower():
                    match = event
                    break
            if match:
                break

        if not match:
            self._send_json(404, {'found': False})
            return

        actor   = match.get('actor', {})
        outcome = match.get('outcome', {})
        targets = match.get('target', [])
        debug   = match.get('debugContext', {}).get('debugData', {})

        host_name = None
        for t in targets:
            if t.get('displayName', '').lower() == target_host.lower():
                host_name = t.get('displayName')

        result = {
            'found':         True,
            'uuid':          match.get('uuid'),
            'published':     match.get('published'),
            'outcome':       outcome.get('result'),
            'actor_id':      actor.get('id'),
            'actor_type':    actor.get('type'),
            'target_host':   host_name or target_host,
            'ssh_algorithm': debug.get('SshAlgorithm'),
        }
        self._send_json(200, result)

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
            # Pass gh_status so the frontend can distinguish queued vs in_progress
            self._send_json(200, {"status": "in_progress", "gh_status": gh_status, "run_id": run_id})


if __name__ == "__main__":
    host, port = "127.0.0.1", 8765
    print(f"OPA demo API server listening on {host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()
