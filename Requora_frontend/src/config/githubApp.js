const githubAppSlug = import.meta.env.VITE_GITHUB_APP_SLUG?.trim();

export const githubAppInstallUrl = githubAppSlug
  ? `https://github.com/apps/${githubAppSlug}/installations/new`
  : null;
