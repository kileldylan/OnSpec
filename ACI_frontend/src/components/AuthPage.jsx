import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { aciApi } from '../api/aci';

const inputClass = 'w-full rounded-lg border border-dark-border bg-dark-bg px-4 py-3 text-sm text-dark-text outline-none transition focus:border-accent-middle focus:ring-1 focus:ring-accent-middle';

export const Login = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: '', password: '' });
  const [submitting, setSubmitting] = useState(false);
  const [githubSubmitting, setGithubSubmitting] = useState(false);

  useEffect(() => {
    const result = new URLSearchParams(location.search).get('github');
    if (!result) return;

    const messages = {
      cancelled: 'GitHub sign-in was cancelled.',
      failed: 'GitHub sign-in failed. Please try again.',
      invalid_state: 'GitHub sign-in expired. Please try again.',
      already_linked: 'This GitHub account is linked to another ACI user.',
    };
    toast.error(messages[result] || 'Unable to sign in with GitHub.');
    navigate('/login', { replace: true });
  }, [location.search, navigate]);

  const signInWithGitHub = async () => {
    setGithubSubmitting(true);
    try {
      const response = await aciApi.getGitHubLoginUrl();
      window.location.assign(response.data.authorization_url);
    } catch (error) {
      toast.error(
        error.response?.data?.detail || 'Unable to start GitHub sign-in.'
      );
      setGithubSubmitting(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login(form);
      navigate(location.state?.from?.pathname || '/', { replace: true });
    } catch {
      toast.error('Unable to sign in with those details.');
    } finally {
      setSubmitting(false);
    }
  };

  return <AuthForm title="Optional ACI console" subtitle="Set up requirements or review audit history. Pull request decisions are posted in GitHub." submitLabel="Sign in" form={form} setForm={setForm} submit={submit} submitting={submitting} login onGitHubSignIn={signInWithGitHub} githubSubmitting={githubSubmitting} />;
};

export const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', email: '', password: '', password_confirm: '' });
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await register(form);
      navigate('/', { replace: true });
    } catch (error) {
      const detail = error.response?.data;
      const message = detail?.detail || Object.values(detail || {})[0]?.[0] || 'Unable to create your account.';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return <AuthForm title="Create a console account" subtitle="The optional ACI console is for requirement setup and audit history. GitHub App installation handles repository access." submitLabel="Create account" form={form} setForm={setForm} submit={submit} submitting={submitting} />;
};

const AuthForm = ({ title, subtitle, submitLabel, form, setForm, submit, submitting, login, onGitHubSignIn, githubSubmitting }) => {
  const fields = login
    ? [['username', 'Username or email', 'text'], ['password', 'Password', 'password']]
    : [['username', 'Username', 'text'], ['email', 'Work email', 'email'], ['password', 'Password', 'password'], ['password_confirm', 'Confirm password', 'password']];

  return (
    <main className="min-h-[100svh] bg-dark-bg text-dark-text flex items-center justify-center px-4 py-8 sm:px-5 sm:py-12 bg-grid-pattern">
      <section className="w-full max-w-md animate-slide-up">
        <div className="mb-8 flex items-center gap-3">
          <div className="rounded-xl bg-accent-middle/15 p-3"><Shield className="h-7 w-7 text-accent-middle" /></div>
          <div><p className="text-lg font-bold tracking-wide">ACI</p><p className="text-xs uppercase tracking-[0.2em] text-dark-muted">Assurance control</p></div>
        </div>
        <div className="card p-5 sm:p-8">
          <div className="mb-7"><p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent-middle">Secure workspace</p><h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1><p className="mt-2 text-sm text-dark-muted">{subtitle}</p></div>
          <form onSubmit={submit} className="space-y-4">
            {fields.map(([name, label, type]) => (
              <label key={name} className="block"><span className="mb-2 block text-sm font-medium">{label}</span><input required className={inputClass} type={type} value={form[name]} onChange={(event) => setForm({ ...form, [name]: event.target.value })} autoComplete={name === 'password_confirm' ? 'new-password' : name === 'password' && !login ? 'new-password' : name === 'password' ? 'current-password' : name} /></label>
            ))}
            <button disabled={submitting} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-accent-middle px-4 py-3 text-sm font-semibold text-white transition hover:bg-accent-end disabled:cursor-not-allowed disabled:opacity-60" type="submit">{submitting ? 'Please wait...' : submitLabel}<ArrowRight className="h-4 w-4" /></button>
          </form>
          {login && (
            <>
              <div className="my-5 flex items-center gap-3 text-xs text-dark-muted">
                <span className="h-px flex-1 bg-dark-border" />
                <span>or</span>
                <span className="h-px flex-1 bg-dark-border" />
              </div>
              <button
                type="button"
                onClick={onGitHubSignIn}
                disabled={githubSubmitting}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dark-border px-4 py-3 text-sm font-semibold transition hover:bg-dark-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                {githubSubmitting ? 'Connecting to GitHub...' : 'Sign in to console with GitHub'}
              </button>
            </>
          )}
          <p className="mt-6 text-center text-sm text-dark-muted">{login ? 'New to ACI?' : 'Already have an account?'}{' '}<Link className="font-semibold text-accent-middle hover:text-accent-end" to={login ? '/register' : '/login'}>{login ? 'Create an account' : 'Sign in'}</Link></p>
        </div>
        <p className="mt-6 flex items-center justify-center gap-2 text-xs text-dark-muted"><CheckCircle2 className="h-3.5 w-3.5 text-verified" /> Evidence-backed delivery decisions</p>
      </section>
    </main>
  );
};