# OPA Workload Identity Demo — Validation Prompt

> **For the SE:** Hand this file to Claude and say: "Execute this prompt." Claude will read the demo prompt, fetch the official Okta and GitHub docs, and produce a structured validation report covering accuracy, ordering, CLI syntax, and known fragility points.

---

## SECTION 1 — CLAUDE INSTRUCTIONS

You are validating `OPA_WI_DEMO_PROMPT.md` — a demo prompt used by Solutions Engineers to build and deliver a live Okta Privileged Access (OPA) Workload Identity demo. Your job is to verify every meaningful claim in that file against official documentation, then output a structured validation report.

**Execute these steps in order:**

1. Read the file at `OPA_WI_DEMO_PROMPT.md` in the current working directory. Read the entire file before proceeding.

2. Fetch each URL listed in Section 3 of this prompt. Use WebFetch on each URL.

3. Cross-reference the demo prompt section by section against what you found in the live docs. Use the checklist in Section 2 as your guide.

4. Output the validation report using the format defined in Section 4. Do not output anything else — no preamble, no commentary outside the report structure.

**Rules:**
- Do not skip any checklist item in Section 2, even if you cannot verify it from the docs. Mark those as `UNVERIFIABLE` with a reason.
- If a doc URL returns an error or redirect, note it in the report and attempt the redirect URL.
- Quote specific doc language when flagging an issue. Include the source URL.
- Reference specific line numbers from `OPA_WI_DEMO_PROMPT.md` when flagging items.

---

## SECTION 2 — VALIDATION CHECKLIST

Cross-reference each item below against the live docs. For each item, determine: **Confirmed**, **Flagged**, or **Unverifiable**.

---

### 2.1 — Phase Ordering and Admin Role Assignment

Verify:
- The 4-phase model (Connect → Governance → Logic → Deploy) matches the sequence described in official OPA Workload Identity configuration documentation.
- Phase 1 (Workload Connection creation) is correctly assigned to the DevOps Admin role.
- Phase 2 (promoting Connection from Draft to Active) is correctly assigned to the Security Admin role.
- Phase 3 (Workload Role creation + policy attachment) is correctly assigned to the Security Admin role.
- Phase 4 (pipeline injection) is correctly assigned to the DevOps Admin role.
- The draft → active promotion flow is accurately described (i.e., DevOps cannot self-approve).

---

### 2.2 — CLI Syntax: `sft workload authenticate`

Verify against the official CLI authentication command documentation:
- All flags used in the demo prompt are valid: `--team`, `--connection`, `--jwt-env`
- The `--role-hint` flag is described as optional and its purpose is accurate
- No undocumented or deprecated flags are used
- The command structure matches the documented syntax (flag order, argument format)
- The `sft wl` alias note in Section 7 of the demo prompt is accurate (pre-GA alias vs. GA command)
- The `SFT_FEATURE_NHI=1` feature flag note in Section 7 is accurate and appropriately scoped

---

### 2.3 — JWKS URL Accuracy

Verify:
- The GitHub Actions JWKS URL used in the demo prompt is correct: `https://token.actions.githubusercontent.com/.well-known/jwks`
- This URL is the correct endpoint for GitHub OIDC token verification (not a discovery URL that redirects)
- Confirm against the GitHub OIDC documentation whether a direct JWKS URL or the OpenID configuration discovery URL should be used

---

### 2.4 — Required Claims: `iss` and `repository`

Verify against GitHub OIDC token documentation:
- The `iss` claim value `https://token.actions.githubusercontent.com` is what GitHub actually includes in OIDC tokens
- The `repository` claim is a real claim in GitHub OIDC tokens and contains the format `<org>/<repo>`
- The claims used in the demo prompt for required claims in the Workload Connection are sufficient (not missing required ones, not using non-existent ones)
- Cross-check: are there any other claims the OPA docs recommend requiring for GitHub Actions connections?

---

### 2.5 — Workload Role Claim Conditions

Verify:
- The condition `ref = refs/heads/main` uses the correct claim name and value format for GitHub OIDC tokens
- The condition `repository = <GITHUB_ORG>/<GITHUB_REPO>` uses the correct claim name
- The OPA docs describe `equals` as a valid operator for claim conditions
- No other condition syntax (e.g., `contains`, `startsWith`) would be more appropriate for the `ref` field
- The negative test logic (non-main branch triggers rejection) is consistent with how OPA evaluates these conditions

---

### 2.6 — Token Constraint Accuracy

Verify:
- The "tokens cannot be refreshed" constraint is accurately described in the demo prompt
- The behavior on token expiration (full re-authentication required) matches the docs
- Individual token revocation unavailability is accurately described
- The mechanism for revoking access (deactivating the Workload Connection) is accurate
- The demo prompt's description of what happens when a Workload Role is removed from a security policy (active SSH sessions terminated) matches the docs

---

### 2.7 — JIT Account Prefix (`wl_`)

Verify:
- The `wl_` prefix for workload JIT usernames is accurately described
- The example username `wl_github_actions` or similar is a plausible/accurate representation
- The JIT account lifecycle (created at job start, torn down after session closes) matches the docs
- Any constraints on workload username format are accurately described

---

### 2.8 — Split-Duty Admin Model

Verify:
- The distinction between DevOps Admin and Security Admin capabilities matches what OPA docs describe
- The claim that DevOps cannot self-approve Connections into production is accurate
- No capabilities are incorrectly attributed to the wrong admin role

---

### 2.9 — Two-Session Token Fragility

Examine the `opa-workflow.yml` in Section 4d of the demo prompt carefully:
- The workflow uses `$OPA_TOKEN` for **two separate** `sft ssh` calls (Step 5: "Update dashboard via brokered SSH" and Step 6: "Update session duration")
- The Workload Connection TTL is set to `120` seconds in Phase 1
- Verify: does the OPA token TTL apply to the total time between issuance and the last use, or only to individual session duration?
- Assess whether using a 120s TTL token across two sequential SSH sessions (where the second re-opens after the first closes) creates a realistic risk of token expiration mid-workflow, especially on slow CI runners
- Confirm whether Step 6 in the workflow correctly handles this with `|| echo "Duration patch skipped (token may have expired — that's fine)"` — is this a reasonable mitigation or a fragile workaround?

---

### 2.10 — Section 2 Narrative vs. Workflow Implementation: `ACTIONS_ID_TOKEN_REQUEST_TOKEN` Inconsistency

Examine Section 2 of the demo prompt (Feature Context → Authentication Flow):

```
2. Pipeline runs: sft workload authenticate \
     --team <TEAM> \
     --connection <CONNECTION_NAME> \
     --jwt-env ACTIONS_ID_TOKEN_REQUEST_TOKEN \
     [--role-hint <ROLE_NAME>]
```

Then examine the actual `opa-workflow.yml` in Section 4d:
- Step 3 fetches a token using `$ACTIONS_ID_TOKEN_REQUEST_TOKEN` and stores it in `${{ steps.oidc.outputs.token }}`
- Step 4 sets `GITHUB_OIDC_TOKEN: ${{ steps.oidc.outputs.token }}` and passes `--jwt-env GITHUB_OIDC_TOKEN`

Verify:
- `ACTIONS_ID_TOKEN_REQUEST_TOKEN` is the raw GitHub Actions token used to *request* an OIDC token, not the OIDC token itself — it cannot be passed directly to `--jwt-env`
- The actual OIDC JWT is the derived value fetched via `curl ... $ACTIONS_ID_TOKEN_REQUEST_TOKEN`
- The Section 2 narrative is therefore inaccurate (it implies `ACTIONS_ID_TOKEN_REQUEST_TOKEN` can be passed directly to `sft`)
- The actual workflow implementation (Step 3 → Step 4 via `GITHUB_OIDC_TOKEN`) is the correct pattern
- Flag this as a narrative/implementation inconsistency and suggest a corrected description for Section 2

---

### 2.11 — OPA Enrollment as a Hard Prerequisite

Review the pre-flight checklist (Section 4e) and all other prerequisite references in the demo prompt:
- OPA server enrollment (`sftd` running on the target VM) is currently listed only as item 4 within the Phase 4 OPA configuration steps and as a checklist item under "INFRASTRUCTURE"
- Assess: should OPA enrollment be flagged earlier and more prominently — specifically as a **hard prerequisite** that must be confirmed before any OPA configuration phases begin?
- The current structure buries enrollment verification within configuration steps rather than surfacing it as a blocking dependency
- Evaluate whether this ordering could cause an SE to complete all OPA configuration (Phases 1–3) before discovering the target VM is not enrolled

---

### 2.12 — `sft` CLI Install Command

Verify:
- `curl -fsSL https://dist.scaleft.com/install.sh | sh` is the current recommended installation method
- The install path `$HOME/.local/bin` is consistent with what the install script produces
- `echo "$HOME/.local/bin" >> $GITHUB_PATH` is the correct mechanism for adding to PATH in GitHub Actions

---

### 2.13 — `sft ssh` Token Flag

Verify:
- The `--token "$OPA_TOKEN"` flag for `sft ssh` is documented and correct
- No additional flags are required for brokered SSH using a workload token (e.g., is `--via` or a bastion flag required for some configurations?)

---

## SECTION 3 — REFERENCE URLS TO FETCH

Fetch all of the following URLs. Use the fetched content for validation.

**Official Okta OPA Documentation:**
1. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-workloads.htm`
   — Workloads Overview
2. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-requirements-workloads.htm`
   — Requirements & Limitations
3. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workloads.htm`
   — Get Started / Configuration Guide
4. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-connection.htm`
   — Configure Workload Connection
5. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-cli.htm`
   — CLI Authentication Command
6. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-configure-workload-role.htm`
   — Configure Workload Roles
7. `https://help.okta.com/oie/en-us/content/topics/privileged-access/pam-ssh-access-workloads.htm`
   — SSH Access for Workloads

**GitHub Documentation:**
8. `https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect`
   — GitHub OIDC token claims and format

---

## SECTION 4 — REPORT FORMAT

Output the validation report using exactly this structure. Do not add sections or change section names.

---

```
╔══════════════════════════════════════════════════════════════════╗
║         OPA WI DEMO PROMPT — VALIDATION REPORT                  ║
╚══════════════════════════════════════════════════════════════════╝

DOCS FETCHED
─────────────────────────────────────────────────────────────────
List each URL attempted, with status (fetched / redirected / error).
Note: if a URL redirected, list the resolved URL.

CONFIRMED ITEMS
─────────────────────────────────────────────────────────────────
List each checklist item that verified correctly. For each:
  ✅ [Item reference, e.g. "2.1 Phase ordering"]
     Brief statement of what was verified and the source doc.

FLAGGED ITEMS
─────────────────────────────────────────────────────────────────
List each item with an inaccuracy, inconsistency, or fragility concern. For each:
  ⚠️  [Item reference]
     ISSUE: Clear description of what is wrong or inconsistent.
     LOCATION: Section/line reference in OPA_WI_DEMO_PROMPT.md.
     SOURCE: Quote from official doc (with URL) that contradicts or clarifies.
     FIX: Exact suggested replacement text or action.

UNVERIFIABLE ITEMS
─────────────────────────────────────────────────────────────────
List checklist items that could not be verified from the fetched docs. For each:
  ❓ [Item reference]
     REASON: Why this could not be verified (e.g., doc requires auth, page not found).
     RECOMMENDATION: Suggested alternative verification method.

SUMMARY
─────────────────────────────────────────────────────────────────
Confirmed: N  |  Flagged: N  |  Unverifiable: N

Priority fixes (if any flagged items exist, list in order of demo risk):
1. [Highest-risk issue — could break the live demo]
2. [Accuracy issue — wrong information shown to customer]
3. [Lower-priority polish / narrative inconsistency]
```

---

*This validation prompt is part of the OPA Workload Identity Demo project. Re-execute against the demo prompt whenever `OPA_WI_DEMO_PROMPT.md` is updated or Okta releases new documentation.*
