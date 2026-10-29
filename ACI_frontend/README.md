# ACI Console

The console is a secondary interface for requirement setup and verification history. The primary review and merge workflow is in GitHub: ACI publishes a Checks API result and maintains one evidence-linked comment on each pull request. Linking a GitHub user account only controls optional console visibility; repository access for verification is granted to the GitHub App installation.

## Product interface

The public home page explains and links to the GitHub App. Developers install the App and read delivery checks and the maintained evidence comment on their pull requests; they do not need to sign in to ACI for that workflow. Login and registration are only for the optional console used for requirement setup and audit history.

## Local development

1. Install frontend dependencies with `npm install`.
2. Set `VITE_GITHUB_APP_SLUG` to the GitHub App's URL slug to enable the repository installation link.
3. Configure `VITE_API_URL` when the backend URL differs from the deployed default; local development uses the Vite proxy.
4. Start the frontend with `npm run dev`.

The optional console is available at `/pull-requests` after sign-in. Audit history and requirements are available in its navigation; analytics and detailed evidence views are secondary routes.

## Validation

- `npm run lint`
- `npm run build`
