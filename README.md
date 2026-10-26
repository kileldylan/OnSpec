# ACI — AI-Assisted Requirement Verification

**ACI (Automated Compliance Intelligence)** is a developer-focused verification platform that answers a question existing code-review tools often don't answer:

> **Did the team actually deliver what the requirement asked for?**

ACI connects the **requirement**, **Pull Request**, **code changes**, **tests**, **CI results**, and other available evidence into one verification chain.

Instead of treating a PR as "good" simply because the code looks clean, ACI evaluates whether the requested work has actually been delivered and whether there is evidence supporting that conclusion.

---

## The Problem

Modern development teams have excellent tools for writing and reviewing code.

GitHub, GitLab, Jira, Linear, AI code reviewers, CI systems, and testing frameworks can each answer different questions:

* Does the code build?
* Are there obvious bugs?
* Does the PR follow coding standards?
* Did the tests pass?
* What task is this PR associated with?

But there is still a critical gap:

> **Does the submitted implementation satisfy the actual requirements of the task?**

Consider a ticket:

**PROJ-123 — Add authentication**

Requirements:

1. Users can log in with email and password.
2. Invalid credentials are rejected.
3. Successful authentication creates a session.
4. Authentication failures are logged.
5. Automated tests cover the authentication flow.

A developer opens a PR.

The PR may:

* compile successfully,
* pass linting,
* contain clean code,
* pass some tests,
* receive a positive AI code review,

while still missing requirement #4 or #5.

ACI is designed to detect that gap.

---

# What ACI Does

ACI creates a chain:

```text
Requirement
     ↓
Acceptance Criteria
     ↓
Pull Request
     ↓
Commits
     ↓
Changed Files
     ↓
Evidence
     ↓
Verification
     ↓
Delivery Decision
```

The goal is to make software delivery **verifiable rather than assumed**.

---

# Core Concept

ACI does not simply ask:

> "Does this code look correct?"

It asks:

> "What was requested, what changed, what evidence exists, and how much of the requirement can we actually verify?"

That distinction is the foundation of ACI.

---

# Example

A Jira ticket says:

> Add password reset functionality.

Acceptance criteria:

* User can request a password reset.
* User receives a reset email.
* Reset links expire.
* User can set a new password.
* The flow is covered by automated tests.

A developer creates:

```text
PR #42
Add password reset functionality
```

ACI discovers the linked Jira requirement and analyzes the PR.

It may produce:

```text
DELIVERY STATUS: PARTIAL

3 / 5 requirements verified

✓ Password reset request implemented
✓ User can set a new password
✓ Automated tests detected

⚠ Reset email delivery
   Evidence found: email service implementation
   Verification: Partial

✗ Reset link expiration
   No sufficient implementation evidence found
```

Instead of saying:

> "The PR looks good."

ACI says:

> **"The PR does not yet provide sufficient evidence that the entire requirement has been delivered."**

---

# The ACI Verification Model

ACI separates several concepts that are normally mixed together.

## 1. Requirement

The original piece of work.

Requirements can originate from:

* Jira
* Linear
* GitHub
* Manual entry

A requirement contains information such as:

* external ID
* title
* description
* source
* status
* URL

---

## 2. Criterion

A requirement can be broken into explicit, independently verifiable pieces.

For example:

```text
Requirement:
Password Reset

Criteria:

1. User can request password reset.
2. Reset email is sent.
3. Reset token expires.
4. User can choose a new password.
5. Automated tests cover the flow.
```

Each criterion can be independently evaluated.

This is important because:

> A requirement should not be considered complete merely because most of it was implemented.

---

## 3. Pull Request

ACI connects requirements to GitHub Pull Requests.

A PR contains:

* repository
* title
* author
* source branch
* target branch
* base SHA
* head SHA
* state
* merge state

The PR becomes the delivery unit that ACI evaluates.

---

## 4. Commits

ACI records commits associated with the repository and PR.

Commits provide a more precise view of what was delivered.

They allow ACI to connect:

```text
Requirement
    ↓
PR
    ↓
Commit
    ↓
Changed File
```

---

## 5. Changed Files

ACI records files modified by commits.

For each changed file, ACI can retain:

* filename
* status
* additions
* deletions
* total changes
* patch

This gives the verification system concrete implementation evidence.

---

# Evidence

Evidence is one of the most important parts of ACI.

ACI does not want an AI model simply saying:

> "I think this requirement is implemented."

Instead, the system records **why** the conclusion was reached.

Evidence can currently represent:

* `code`
* `test`
* `ci`
* `runtime`

Each evidence item can have:

* status
* description
* metadata
* associated requirement
* associated PR
* associated commit
* associated changed file

This creates an auditable evidence chain.

---

# Verification

A verification represents ACI's conclusion about a requirement.

Possible verification states include:

```text
pending
verified
partial
unverified
stale
failed
```

A verification can contain:

* summary
* confidence
* verification timestamp
* invalidation timestamp
* supporting evidence

The important principle is:

> **Verification conclusions must be grounded in supplied evidence.**

The AI evaluator is therefore not treated as an unquestionable authority.

---

# AI Evaluation

ACI includes an LLM evaluation layer, but the architecture deliberately keeps the AI behind a provider-neutral interface.

The evaluator receives structured information such as:

```text
Requirement
    +
Evidence
```

and is expected to return structured JSON containing:

```text
status
summary
confidence
evidence_ids
```

The evaluator is explicitly instructed to:

* evaluate only supplied evidence,
* avoid inventing evidence,
* reference only supplied evidence,
* conform to the expected response structure.

ACI then validates the evaluator's conclusion before accepting it.

This creates an important architectural boundary:

```text
Evidence
   ↓
LLM
   ↓
Structured conclusion
   ↓
Contract validation
   ↓
Verification
```

The AI can reason.

The system still controls what is accepted.

---

# Criterion Verification

Requirements can be evaluated at criterion level.

Each criterion evaluation can produce states such as:

```text
pending
satisfied
partial
missing
not_applicable
failed
```

This allows ACI to distinguish between:

```text
Requirement = partially implemented
```

and:

```text
Criterion #3 = missing
```

That distinction is critical for developers.

Instead of receiving a vague:

> "Something might be missing."

they can receive:

> **Criterion #3 — Reset links must expire**
>
> Status: Missing
>
> No sufficient implementation evidence was found.

---

# Delivery Decision

ACI separates **verification** from the final delivery decision.

The delivery decision is deterministic.

It considers:

* verification status,
* required criteria,
* criterion results,
* missing criteria,
* partial criteria,
* verification evidence.

Possible decisions include:

```text
verified
partial
unverified
failed
stale
```

For example:

```text
Verification:
PARTIAL

Required criteria:
5

Satisfied:
3

Partial:
1

Missing:
1

Delivery Decision:
UNVERIFIED
```

This prevents an AI evaluator from simply overriding the actual requirement state.

---

# Evidence-First Architecture

One of ACI's central design principles is:

> **No evidence, no verification.**

The system should prefer:

```text
Unknown
```

over:

```text
Probably implemented
```

when evidence is insufficient.

This is particularly important when AI is involved.

ACI is therefore designed around **evidence-backed conclusions rather than AI-generated confidence alone**.

---

# Auditability

ACI retains relationships between:

```text
Requirement
    ↓
Criterion
    ↓
Verification
    ↓
Evidence
    ↓
Commit
    ↓
Changed File
```

This makes it possible to answer questions such as:

* Which requirement was being verified?
* Which criterion failed?
* Which PR delivered the work?
* Which commit contained the implementation?
* Which files provided evidence?
* What evidence supported the conclusion?
* When was the verification performed?
* Has that evidence become stale?
* Why did ACI mark the delivery as partial?

This is intended to make ACI useful not only for automation but also for engineering accountability.

---

# Current Architecture

ACI is currently built around Django and a service-oriented integration layer.

Conceptually:

```text
                    ┌───────────────┐
                    │     Jira      │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Requirements │
                    └───────┬───────┘
                            │
                            ▼
┌──────────────┐     ┌───────────────┐
│    GitHub    │────▶│      ACI      │
│   Webhooks   │     │               │
└──────────────┘     │ Verification  │
                     │ Engine        │
                     └───────┬───────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           Commits      Changed Files     Evidence
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                       ┌───────────┐
                       │    LLM    │
                       │ Evaluator │
                       └─────┬─────┘
                             ▼
                       ┌───────────┐
                       │Verification│
                       └─────┬─────┘
                             ▼
                       ┌───────────┐
                       │ Delivery  │
                       │ Decision  │
                       └───────────┘
```

---

# Current Integrations

### GitHub

ACI currently works with GitHub webhook events and GitHub repository data.

The GitHub integration is responsible for obtaining information such as:

* repositories
* pull requests
* commits
* changed files

### Running a verification

Configure the GitHub webhook in each repository that ACI should monitor. Use
the ACI endpoint `/api/webhooks/github/` and subscribe to pull request, check
run, and commit status events.

When a pull request contains a Jira key in its title or description, such as
`PROJ-123`, ACI imports the Jira requirement and links it to the pull request.
The webhook then queues the initial verification automatically when changed
files are available.

Existing imported data can be started through the authenticated API:

```text
GET  /api/repositories/{repository_id}/pull-requests/
GET  /api/repositories/{repository_id}/requirements/
POST /api/repositories/{repository_id}/start-verification/
```

The start request accepts `pull_request_id` or `pull_request_number`, plus
`requirement_id` or `jira_key`. For example:

```json
{
    "pull_request_number": 12,
    "jira_key": "PROJ-123"
}
```

Run the worker after a verification is queued:

```bash
python ACI_backend/manage.py process_reverification_runs
```

Results are available from `/api/verifications/`,
`/api/verification-runs/`, and `/api/delivery-decisions/`.

### Jira

ACI currently supports Jira requirement ingestion.

Jira issue keys can be detected from text such as:

```text
Implements PROJ-123
Fixes PROJ-456
```

ACI can then retrieve the corresponding issue and associate it with the Pull Request.

---

# Design Principles

## 1. Evidence Before Conclusions

ACI should never claim something is delivered without supporting evidence.

## 2. Requirements Are First-Class Objects

The requirement is not merely metadata attached to a PR.

It is the thing being verified.

## 3. Criteria Must Be Independently Verifiable

Large requirements should be decomposed into smaller acceptance criteria.

## 4. AI Assists; The System Decides

LLMs provide semantic reasoning.

Deterministic services enforce system rules and consistency.

## 5. Preserve History

Verification results and delivery decisions should remain auditable rather than simply being overwritten.

## 6. Prefer Conservative Conclusions

If evidence is insufficient:

```text
unverified
```

is preferable to a false:

```text
verified
```

## 7. Evidence Can Become Stale

A verification should not remain permanently trustworthy if the underlying implementation changes.

---

# What Makes ACI Different

ACI is not intended to be another generic AI code reviewer.

The core distinction is the **delivery verification layer**.

Traditional code review asks:

```text
Is this code good?
```

ACI asks:

```text
Did we deliver what was requested?
```

And more importantly:

```text
What evidence proves it?
```

This creates a different relationship between:

```text
Product requirement
        ↓
Engineering implementation
        ↓
Verification
        ↓
Delivery confidence
```

---

# The Long-Term Vision

The long-term goal is for ACI to become a **delivery verification layer for software teams**.

A future ACI workflow could look like:

```text
Jira / Linear
      │
      │ Requirements
      ▼
     ACI
      │
      │ PR opened
      ▼
   GitHub
      │
      │ Code / commits / tests
      ▼
     ACI
      │
      ├── Requirement analysis
      ├── Criterion verification
      ├── Evidence collection
      ├── AI reasoning
      └── Deterministic validation
      │
      ▼
Delivery Decision
      │
      ├── VERIFIED
      ├── PARTIAL
      ├── UNVERIFIED
      └── FAILED
```

The ultimate objective is simple:

> **Give engineering teams confidence that completed work actually satisfies the work that was requested.**

---

# Development Status

ACI is currently in active development.

The foundational system already includes:

* GitHub repository ingestion
* Pull Request ingestion
* Commit ingestion
* Changed-file ingestion
* Jira requirement ingestion
* Requirement ↔ Pull Request relationships
* Requirement criteria
* Criterion verification
* Evidence relationships
* Verification services
* LLM evaluator abstraction
* OpenAI evaluator integration
* Deterministic delivery decisions
* Historical delivery decision snapshots
* Evidence-backed verification validation
* Automated test coverage for the core services

The project is currently moving toward the next stage:

**turning the verification model into a complete end-to-end delivery verification workflow.**

---

# Testing

Run the complete test suite with:

```bash
pytest ACI_backend
```

The project is designed so that external services such as GitHub, Jira, and LLM providers can be mocked during tests.

This keeps the core verification logic deterministic and testable.

---

# Project Philosophy

ACI is built around one fundamental question:

> **"Can we prove this requirement was delivered?"**

Not:

> "Did the PR look good?"

Not:

> "Did an AI reviewer approve the code?"

Not:

> "Did the developer say it was finished?"

But:

> **"What was requested, what was implemented, what evidence exists, and what can we confidently verify?"**

That is the problem ACI exists to solve.

---

## ACI

**From code review to delivery verification.**

**From assumptions to evidence.**

**From "looks done" to "proven delivered."**
/ /   t e s t i n g   v e r i f i c a t i o n  
 