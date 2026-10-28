import { ArrowUpRight, CheckCircle2, GitPullRequest, Shield } from 'lucide-react';
import { Link } from 'react-router-dom';

const HomePage = () => {
  const githubAppSlug = import.meta.env.VITE_GITHUB_APP_SLUG;
  const installUrl = githubAppSlug
    ? `https://github.com/apps/${githubAppSlug}/installations/new`
    : null;

  return (
    <main className="min-h-screen bg-dark-bg text-dark-text bg-grid-pattern">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-accent-middle" />
          <span className="text-xl font-bold gradient-text">ACI</span>
        </div>
        <Link
          to="/login"
          className="rounded-lg border border-dark-border px-4 py-2 text-sm font-medium text-dark-muted transition hover:bg-dark-hover hover:text-dark-text"
        >
          Optional console
        </Link>
      </header>

      <section className="mx-auto grid max-w-6xl gap-12 px-5 pb-20 pt-14 sm:px-8 sm:pt-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent-middle/30 bg-accent-middle/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-accent-middle">
            <CheckCircle2 className="h-4 w-4" />
            Requirement delivery checks for GitHub
          </p>
          <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
            Know what a pull request <span className="gradient-text">actually delivered.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-dark-muted">
            ACI checks each pull request against its linked requirements and
            acceptance criteria, then posts an evidence-backed decision in
            GitHub. No separate dashboard is needed for review or merge.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
            {installUrl ? (
              <a
                href={installUrl}
                className="inline-flex items-center gap-2 rounded-lg bg-accent-middle px-5 py-3 font-semibold text-white transition hover:bg-accent-end"
              >
                Install the GitHub App
                <ArrowUpRight className="h-4 w-4" />
              </a>
            ) : (
              <span className="rounded-lg border border-dark-border px-5 py-3 text-sm text-dark-muted">
                GitHub App installation link is not configured
              </span>
            )}
          </div>
        </div>

        <div className="card p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-xl bg-accent-middle/15 p-3">
              <GitPullRequest className="h-6 w-6 text-accent-middle" />
            </div>
            <div>
              <p className="font-semibold">Your review stays in GitHub</p>
              <p className="text-sm text-dark-muted">One check. One maintained comment.</p>
            </div>
          </div>
          <ol className="space-y-5">
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-dark-hover text-xs font-semibold">1</span>
              <p className="text-sm leading-6 text-dark-muted">
                Install ACI on the repositories you choose.
              </p>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-dark-hover text-xs font-semibold">2</span>
              <p className="text-sm leading-6 text-dark-muted">
                Open or update a pull request linked to clear requirements.
              </p>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-dark-hover text-xs font-semibold">3</span>
              <p className="text-sm leading-6 text-dark-muted">
                Review ACI&apos;s deterministic Check and evidence-linked comment on the PR.
              </p>
            </li>
          </ol>
          <div className="mt-7 border-t border-dark-border pt-5 text-xs leading-5 text-dark-muted">
            The optional console is for requirement setup and audit history.
            Login is not part of the GitHub PR review workflow.
          </div>
        </div>
      </section>
    </main>
  );
};

export default HomePage;
