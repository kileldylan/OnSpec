# Requora — Delivery Verification

**Requora proves whether a pull request actually delivered the requirement, using the evidence already in your code, tests, and CI.**

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

Requora closes that gap with an auditable, evidence-backed answer: **did this PR deliver the requested criteria?**

---

## What Requora Does

Requora builds a short verification chain for every relevant pull request:
Requirement / Acceptance Criteria ↓ Linked Pull Request ↓ Commits + Changed Files + CI/Test Evidence ↓ Grounded Verification ↓ Deterministic Delivery Decision


It surfaces the result as:
1. A **GitHub Check** (can be required before merge).
2. A **single, self-updating PR comment** that shows which criteria are verified, partial, or missing, with links to the supporting evidence.

Everything else (history, audit trail, configuration) is secondary.

---

## How It Works in GitHub (No Daily Login)

Requora is installed as a **GitHub App**. Once installed on a repository (or organization), it works through webhooks and the Checks API. Developers and leads stay inside GitHub.

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
   Name example: `Requora / Delivery Verification`
   - Stays `in_progress` while verification is queued; only a fully verified delivery concludes `success`. Partial, missing, stale, and failed evidence conclude `failure`.
   - Markdown summary with criterion-level status and supporting evidence links.
   - Evidence links identify the source file and available line span (for example, `auth/login.py:10-23`) and open the matching lines on GitHub. Long criteria wrap within the table, and every evidence link is listed on its own line in the Evidence column.
   - Can be set as a required status check in branch protection / rulesets.

2. **One PR comment** (created or updated in place)
   - Clear list of criteria: verified / partial / missing.
   - Evidence pointers include source filenames and line ranges where available, linked to the exact GitHub lines.
   - The same comment is edited in place; unchanged reports are not rewritten.

### What users do
- Open or update a PR as usual.
- Read the Check and the comment.
- Define requirements and required criteria in Requora; repository configuration files are not yet supported.

They do **not** need to visit a separate web app for normal review or merge decisions. A lightweight web interface exists only for audit history, bulk reports, or advanced configuration.

---

## Example Output

**GitHub Check / PR comment:**

| Criterion | Status | Evidence |
|---|---|---|
| User can request a password reset. | satisfied | [`auth/reset.py:10-23`](https://github.com/example/app/blob/abc123/auth/reset.py#L10-L23) |
| Automated tests cover the reset flow. | satisfied | [`tests/test_reset.py:40-52`](https://github.com/example/app/blob/abc123/tests/test_reset.py#L40-L52) |
| Reset links expire after the configured lifetime and cannot be reused. | partial | No supporting evidence |

Long criteria wrap onto subsequent lines in the table. Every supporting evidence item is listed on its own line in the Evidence column.


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

GitHub webhooks are signature-checked and saved to a durable database inbox, then acknowledged immediately. Run the separate persistent worker with `python Requora_backend/manage.py run_requora_worker` from the repository root (or configure that command as a continuously running worker service sharing the backend database and environment). It processes webhook events and verification runs independently of HTTP requests; failed webhook jobs are retried and visible in Django Admin. Check/status webhooks are ingested as evidence, while Requora's own Check Run is excluded to avoid feedback loops. The delivery decision is rule-based and conservative; an LLM can evaluate only the supplied evidence and cannot choose the final decision.

The public web landing page points repositories to GitHub App installation and explains that review happens on the PR. Login and registration are only for the optional console, whose small navigation surface is for pull requests, requirements, and audit history. Analytics and detailed evidence views remain secondary/legacy routes rather than the merge-decision interface.

### GitHub App configuration

Configure `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, and `GITHUB_WEBHOOK_SECRET` in the backend environment. Configure `VITE_GITHUB_APP_SLUG` in the frontend to show the repository-install link. The app needs repository permissions for **Checks (read/write)**, **Contents (read)**, **Pull requests (read)**, and **Issues (read/write)**, and must subscribe to `pull_request`, `issue_comment`, `check_run`, and `status` events. Installation creation and permission-accepted events synchronize the repositories granted to the App. Installations should grant access only to repositories intended for verification.

### Generate acceptance criteria

On a GitHub Issue, an issue author or repository collaborator can comment:

- `/requora generate` to generate criteria from the GitHub Issue title and body.
- `/requora generate from jira` to generate improved criteria from a Jira issue key in the GitHub Issue title/body. This requires `JIRA_BASE_URL` and `JIRA_API_TOKEN`.

Requora posts a preview of 4–8 AI-generated checklist items. Reply `accept` or `save` to approve it. To change the list, reply `/requora accept` and include a replacement checklist with 4–8 `- [ ] ...` items. Reply `/requora reject` to discard the preview, or `/requora generate` to create a new version. Acceptance is stored with GitHub Issue and optional Jira identifiers and version history. The existing PR workflow uses accepted generated criteria first when it links that GitHub Issue or Jira key; otherwise it falls back to criteria parsed from the issue/ticket text.

Set `ACCEPTANCE_CRITERIA_LLM_PROVIDER=openai` and `ACCEPTANCE_CRITERIA_LLM_MODEL` to configure the generator. Provide `ACCEPTANCE_CRITERIA_LLM_API_KEY`, or reuse the existing `OPENAI_API_KEY`. `ACCEPTANCE_CRITERIA_LLM_TIMEOUT` optionally controls the provider request timeout in seconds. Generation requires a configured API key; verification's deterministic mode does not generate criteria.

Configure a private Redis service and set `REDIS_URL` on both the Render web service and worker. Redis provides shared API rate-limit state, GitHub App installation-token caching, and short-lived caching of immutable commit-SHA reads. Without it, local development uses process-local memory, which is not suitable for coordinating production service instances. Auth endpoints have tighter limits; API limits are global, and GitHub webhooks instead rely on HMAC signature validation, delivery-ID deduplication, and a payload size cap to tolerate GitHub event bursts.

Set `DEBUG=False` and keep `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` restricted to the deployed domains. Production enables HTTPS redirects and HSTS by default; `SECURE_HSTS_INCLUDE_SUBDOMAINS` remains off unless every subdomain is HTTPS-only. Run `python Requora_backend/manage.py check --deploy` before deployment. The pytest suite uses an isolated in-memory SQLite database; run it with `pytest Requora_backend/RequoraApp/tests`. Test settings prevent test runs from using the configured production database.

The backend accepts PostgreSQL settings either as `DATABASE_URL` or as `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, and `DATABASE_PORT`. For local commands against Render data, use the database's external connection URL from Render and keep it in the ignored `Requora_backend/.env`; do not commit or share it.

---

## Current Status

Early-stage implementation. The backend has GitHub App installation-token support, a durable webhook inbox, a persistent worker command for automatic processing, AI-generated acceptance-criteria previews and approval, evidence-backed deterministic decisions, and GitHub Check/comment publishing. Hosting still requires a separate always-on worker process running `python Requora_backend/manage.py run_requora_worker`; webhook requests only enqueue work. PRs can link same-repository GitHub Issues via `#number`, Jira issues by key, or existing manual requirements via external ID or title. Repository config files, Linear, bulk reporting, and managed queue infrastructure are not included yet.

---

## Getting Started (Design Partners)

1. Configure the GitHub App credentials, webhook secret, and acceptance-criteria LLM key in the backend, then set the frontend app slug.
2. Install the Requora GitHub App on a repository with the permissions listed above.
3. Optionally generate and approve criteria on a GitHub Issue using `/requora generate`; link Jira criteria with `/requora generate from jira`.
4. Ensure the PR references a GitHub Issue (`#123`), a Jira key, or the external ID/title of a manual requirement in Requora.
5. Open or update the PR; the webhook queues the event and the persistent worker collects evidence and evaluates criteria.
6. Review the in-progress Check, then the completed decision and single updated comment.

For configuration, audit history, or pilot discussion: [link to contact / docs].

---

**From assumed done to proven delivered.**
