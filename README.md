# ACI — Delivery Verification

**ACI proves whether a pull request actually delivered the requirement, using the evidence already in your code, tests, and CI.**

It posts the result where engineering leads and reviewers already look: a GitHub Check and a single PR comment. No daily login, no new dashboard required for the core workflow.

> From “the PR looks clean” to “we have evidence this criterion was delivered.”

---

## The Problem

Teams have strong signals for code quality:
- CI green
- Linters and type checks pass
- AI code reviewers approve the style and catch bugs
- Tests exist and run

They still lack a reliable signal for **requirement satisfaction**.

A PR can pass every technical gate while missing one or more acceptance criteria. The gap is usually discovered late—in QA, staging, or production—creating rework. For regulated or high-stakes work, reconstructing evidence after the fact is slow and incomplete.

ACI closes that gap with an auditable, evidence-backed answer: **did this PR deliver the requested criteria?**

---

## What ACI Does

ACI builds a short verification chain for every relevant pull request:
Requirement / Acceptance Criteria ↓ Linked Pull Request ↓ Commits + Changed Files + CI/Test Evidence ↓ Grounded Verification ↓ Deterministic Delivery Decision


It surfaces the result as:
1. A **GitHub Check** (can be required before merge).
2. A **single, self-updating PR comment** that shows which criteria are verified, partial, or missing, with links to the supporting evidence.

Everything else (history, audit trail, configuration) is secondary.

---

## How It Works in GitHub (No Daily Login)

ACI is installed as a **GitHub App**. Once installed on a repository (or organization), it works through webhooks and the Checks API. Developers and leads stay inside GitHub.

### Trigger
- `pull_request` events (`opened`, `synchronize`, `reopened`, etc.).
- A same-repository GitHub Issue referenced as `#123` can be linked automatically. Existing manual requirements can also be linked by external ID or title; Jira linking remains optional when configured.

### Evidence collection (automatic)
- Diff and changed files
- Commits and SHAs
- Existing CI check statuses / test results (via GitHub Checks or Statuses API)
- Source snippets, test results, and evidence references associated with each criterion

No manual upload. No screenshot chasing.

### Output (where people already work)
1. **Check Run** (Checks API)
   Name example: `ACI / Delivery Verification`
   - Stays `in_progress` while verification is queued; only a fully verified delivery concludes `success`. Partial, missing, stale, and failed evidence conclude `failure`.
   - Markdown summary with criterion-level status.
   - Can be set as a required status check in branch protection / rulesets.

2. **One PR comment** (created or updated in place)
   - Clear list of criteria: verified / partial / missing.
   - Short evidence pointers (file, test, commit SHA).
   - The same comment is edited in place; unchanged reports are not rewritten.

### What users do
- Open or update a PR as usual.
- Read the Check and the comment.
- Define requirements and required criteria in ACI; repository configuration files are not yet supported.

They do **not** need to visit a separate web app for normal review or merge decisions. A lightweight web interface exists only for audit history, bulk reports, or advanced configuration.

---

## Example Output

**PR comment / Check summary:**
ACI Delivery Verification — PARTIAL

3 / 5 criteria verified

✓ User can request password reset Evidence: handler in auth/reset.py (commit a1b2c3d)

✓ User can set a new password Evidence: endpoint + test coverage

✓ Automated tests cover the flow Evidence: CI check “unit-tests” green on head SHA

⚠ Reset email is sent Partial evidence found (email service called) Confidence: medium

✗ Reset links must expire No sufficient implementation evidence found

Delivery Decision: UNVERIFIED (required criteria incomplete)


The Check can block merge until the missing criteria are addressed or explicitly waived.

---

## Core Principles

- **No evidence, no verification.** Prefer “insufficient evidence” over a confident guess.
- **Deterministic delivery decision.** The LLM may evaluate evidence; the final status follows clear rules (required criteria met, partials, missing).
- **Workflow-native.** Primary interface is the PR and the Check. The dashboard is optional.
- **Auditable chain.** Every conclusion points back to the requirement, criterion, commit, file, or CI result that supported it.
- **AI is constrained.** The model receives only the structured evidence pack and must reference it. Output is validated before acceptance.

---

## Verification Model (Short)

| Concept              | Role                                      |
|----------------------|-------------------------------------------|
| Requirement          | Source ticket / issue                     |
| Criterion            | Independently verifiable acceptance piece |
| Evidence             | Code diff, test result, CI status, etc.   |
| Verification         | Grounded conclusion per criterion         |
| Delivery Decision    | Deterministic overall status              |

Possible criterion states: `satisfied`, `partial`, `missing`, `not_applicable`.
Possible delivery decisions: `verified`, `partial`, `unverified`, `failed`, `stale`.

---

## Architecture (Current Focus)

```text
GitHub App webhook
  -> validate webhook signature and persist installation / PR / commit data
  -> queue evidence collection and criterion verification
  -> assemble a structured evidence report
  -> validate evaluator output and calculate a deterministic delivery decision
  -> publish/update one Check Run and one tracked PR comment
```

The GitHub App is the repository integration and owns the PR-facing workflow. Its installation token is minted for the installation that delivered the webhook; a personal access token is retained only for local-development read access. Check Runs and PR comments are written only with a GitHub App installation token. The web console's optional user login and GitHub-account link control console visibility only; repository authorization is granted to the App installation.

GitHub webhooks are signature-checked and saved to a durable database inbox, then acknowledged immediately. Run the separate persistent worker with `python ACI_backend/manage.py run_aci_worker` from the repository root (or configure that command as a continuously running worker service sharing the backend database and environment). It processes webhook events and verification runs independently of HTTP requests; failed webhook jobs are retried and visible in Django Admin. Check/status webhooks are ingested as evidence, while ACI's own Check Run is excluded to avoid feedback loops. The delivery decision is rule-based and conservative; an LLM can evaluate only the supplied evidence and cannot choose the final decision.

The public web landing page points repositories to GitHub App installation and explains that review happens on the PR. Login and registration are only for the optional console, whose small navigation surface is for pull requests, requirements, and audit history. Analytics and detailed evidence views remain secondary/legacy routes rather than the merge-decision interface.

### GitHub App configuration

Configure `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, and `GITHUB_WEBHOOK_SECRET` in the backend environment. Configure `VITE_GITHUB_APP_SLUG` in the frontend to show the repository-install link. The app needs repository permissions for **Checks (read/write)**, **Contents (read)**, **Pull requests (read)**, and **Issues (read/write)**, and must subscribe to `pull_request`, `check_run`, and `status` events. Installation creation and permission-accepted events synchronize the repositories granted to the App. Installations should grant access only to repositories intended for verification.

The backend accepts PostgreSQL settings either as `DATABASE_URL` or as `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, and `DATABASE_PORT`. For local commands against Render data, use the database's external connection URL from Render and keep it in the ignored `ACI_backend/.env`; do not commit or share it.

---

## Current Status

Early-stage implementation. The backend has GitHub App installation-token support, a durable webhook inbox, a persistent worker command for automatic processing, evidence-backed deterministic decisions, and GitHub Check/comment publishing. Hosting still requires a separate always-on worker process running `python ACI_backend/manage.py run_aci_worker`; webhook requests only enqueue work. PRs can link same-repository GitHub Issues via `#number`, or existing manual requirements via external ID or title. Jira linking is optional; repository config files, Linear, bulk reporting, and managed queue infrastructure are not included yet.

---

## Getting Started (Design Partners)

1. Configure the GitHub App credentials and webhook secret in the backend, then set the frontend app slug.
2. Install the ACI GitHub App on a repository with the permissions listed above.
3. Ensure the PR references a GitHub Issue (`#123`), a Jira key, or the external ID/title of a manual requirement in ACI.
4. Open or update the PR; the webhook queues the event and the persistent worker collects evidence and evaluates criteria.
5. Review the in-progress Check, then the completed decision and single updated comment.

For configuration, audit history, or pilot discussion: [link to contact / docs].

---

**From assumed done to proven delivered.**
