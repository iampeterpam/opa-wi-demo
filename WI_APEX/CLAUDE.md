# OPA Workload Identity — Comparison Page

## Purpose

Single-file HTML presentation page for Okta sales engineers to demo the value of OPA Workload Identity to non-technical business leaders (CISOs, VPs, managers). Contrasts traditional SSH credential management against OPA's approach using scroll-triggered animated timelines.

**Live at:** Static file, opened locally or hosted on any web server.
**Primary audience:** Non-technical executives (customer-facing sections) + Okta SEs (Apex Framework section).

---

## File Structure

```
Comparison Page/
├── index.html    ← Entire page (HTML + CSS + JS, ~810 lines)
└── CLAUDE.md     ← This file
```

Single self-contained HTML file. No build step, no external images, no dependencies beyond CDNs.

---

## Tech Stack

| Technology | Delivery | Purpose |
|-----------|----------|---------|
| Tailwind CSS | CDN (`cdn.tailwindcss.com`) | Utility-first styling |
| DM Serif Display | Google Fonts | Display/headline font |
| Plus Jakarta Sans | Google Fonts | Body font |
| Vanilla JS | Inline `<script>` | Scroll-triggered animations (IntersectionObserver) |

---

## Page Sections (in order)

| # | Section | Background | Lines (approx) |
|---|---------|-----------|----------------|
| 1 | Hero | slate-950 (dark) | 311–357 |
| 2 | Traditional Timeline | slate-50 (light gray) | 363–458 |
| 3 | Bridge Quote | white | 463–467 |
| 4 | Okta Timeline | slate-50 (light gray) | 472–625 |
| 5 | Paradigm Shift | slate-900 (dark) | 630–644 |
| 6 | APEX Framework (Internal) | white | 649–722 |
| 7 | Executive Value Summary | slate-950 (dark) | 727–775 |
| 8 | Footer | slate-950 (dark) | 777–790 |

---

## Design System

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `okta-600` | `#4f46e5` | Primary brand, secure states, Okta timeline accent |
| `okta-400` | `#818cf8` | Lighter accent, hero highlights |
| `risk-500` | `#ef4444` | Risk/danger, traditional timeline accent |
| `risk-600` | `#dc2626` | Darker risk text |
| `green-500/600` | standard | Positive outcomes, "destroyed" confirmations |
| `slate-950` | `#0a0e1a` | Dark section backgrounds |
| `slate-50` | standard | Light section backgrounds |

### Typography

- **Headlines:** DM Serif Display (serif)
- **Body:** Plus Jakarta Sans (sans-serif)
- **Monospace elements:** Tailwind `font-mono` for technical terms (`wl_`, `pam.user_creds.issue`, etc.)

### Animation Patterns

- **Scroll-triggered fade-up:** `.fade-up` + `.timeline-step` classes, triggered by IntersectionObserver
- **Scene animations:** Per-step micro-animations (traveling dots, dissolving elements) triggered when `.visible` class is added
- **Key pulse:** `.scene-key-persist` — infinite red pulse on the static SSH key (Traditional Step 3/4)
- **Dissolve:** `.scene-dissolve` — items blur/shrink/fade to show destruction (Okta Step 7)
- **Dissolved labels:** `.dissolved-label` — checkmark + "Destroyed" labels appear after dissolve completes

---

## Content Architecture

### Traditional Timeline (6 steps, red accent)
Shows a typical SSH deployment flow with risk callouts at each vulnerable point.

1. Code Pushed (neutral)
2. Pipeline Needs Server Access (use cases: config management, deploys, security scans)
3. Static SSH Key Retrieved — **risk callout**
4. Permanent Service Account — **risk callout**, animated scene
5. Deployment Runs (neutral)
6. Nothing Changes — **risk callout**, strongest warning

### Okta Timeline (7 steps, blue accent)
Same deployment, secured step-by-step with technology badges.

1. Code Pushed (same starting point)
2. Pipeline Requests Identity — `OIDC JWT` badge, animated scene, supported platforms list
3. OPA Validates Identity — `JWT Validation` badge
4. Ephemeral Access Token — `Ephemeral Token` badge
5. x509 SSH Certificate — `x509 Certificate` badge, animated scene
6. JIT Account Created — `JIT Account` badge, dynamic sudo mention
7. Deployment Runs & Cleanup — `Zero Residue` badge, dissolve animation (Token/Certificate/Account)

### APEX Framework Section (Internal Only)
Okta's Apex sales methodology applied to Workload Identity. Visible on the page but marked "INTERNAL ONLY" in red.

Categories:
- Value Drivers (4 items)
- Before Scenario & Negative Consequences (4 items)
- After Scenario & Positive Outcomes (4 items)
- Differentiators — How We Do It Better (5 items including dynamic sudo)
- Trap Setting Questions (3 items)
- Discovery Questions (3 items)

---

## Key Technical Differentiators (for content accuracy)

1. **JIT local accounts:** `wl_` prefixed Unix accounts created per-session, destroyed on disconnect
2. **Dynamic sudo:** Host agent writes session-specific sudoers rules — not group-based, not pre-provisioned
3. **Non-refreshable tokens:** Access tokens cannot be renewed; must re-authenticate from scratch
4. **x509 SSH certificates:** One-time certificates for each session; no persistent private keys
5. **Built-in governance:** Draft → Active promotion requires separate security admin (separation of duties)
6. **Platform-agnostic:** Supports GitHub Actions, GitLab, CircleCI, Azure Managed Identity, GCP, Kubernetes, Generic JWT

---

## Supported Identity Providers

All use JWT-based authentication:
- Generic JWT
- Azure Managed Identity
- CircleCI
- Google Cloud Provider
- GitHub Actions
- GitLab
- Kubernetes

---

## Constraints & Decisions

- **Platform-agnostic language:** Do not reference GitHub Actions as the only platform. Use "your CI/CD platform" or list multiple providers.
- **SSH M2M is the current scope:** OPA WI currently supports SSH only. Roadmap includes secrets retrieval and managed passwords (mentioned subtly in Paradigm Shift section).
- **No external images:** All visuals are inline SVGs or Tailwind CSS components.
- **Single file:** Everything must remain in one HTML file for portability.
- **Non-technical audience:** Customer-facing sections must avoid unexplained jargon. Technical terms (JWT, x509, OIDC) appear only with plain-language explanations alongside.
- **Scroll animations trigger once:** IntersectionObserver fires when elements enter viewport; they don't re-animate on scroll-up.

---

## Competitive Context (for content accuracy)

| Competitor | Sudo Model | OPA Advantage |
|-----------|-----------|---------------|
| Teleport | Static group-based sudo (user dropped into group, sudoers pre-configured) | OPA: per-session, per-user, dynamically-scoped sudoers |
| CyberArk | Similar group-based approach | OPA: true JIT account creation/destruction + dynamic sudo |

---

## Quick Reference — How to Edit

- **Change copy:** Find the relevant section by searching for its heading text
- **Add a timeline step:** Copy an existing `<div class="timeline-step">` block and adjust content
- **Add an Apex item:** Add a `<p>` with the same classes as siblings in that category
- **Test animations:** Scroll the page — each step should fade in as it enters the viewport
- **Verify structure:** Run `grep -c '</section>' index.html` — should match `grep -c '<section' index.html`
