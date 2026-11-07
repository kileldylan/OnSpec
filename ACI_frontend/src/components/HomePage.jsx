import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  ChevronRight,
  CircleCheck,
  Clock3,
  Code2,
  FileCheck2,
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  Layers3,
  Menu,
  ShieldCheck,
  TestTube2,
  Workflow,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import BrandMark from './BrandMark';
import '../App.css';
import { githubAppInstallUrl } from '../config/githubApp';

const workflowSteps = [
  {
    number: '01',
    icon: GitBranch,
    title: 'Connect your repository',
    description: 'Install Requora on the GitHub repositories you choose.',
  },
  {
    number: '02',
    icon: Layers3,
    title: 'Link your requirements',
    description: 'Connect Jira requirements and acceptance criteria to pull requests.',
  },
  {
    number: '03',
    icon: Code2,
    title: 'Collect delivery evidence',
    description: 'Requora examines implementation changes and available test and CI evidence.',
  },
  {
    number: '04',
    icon: FileCheck2,
    title: 'Review the verification report',
    description: 'See a structured delivery decision and criterion-level evidence directly in GitHub.',
  },
];

const featureCards = [
  {
    icon: GitPullRequest,
    title: 'Requirement-to-PR traceability',
    description: 'Link a requirement to the pull request that aims to deliver it.',
  },
  {
    icon: CheckCheck,
    title: 'Acceptance criteria verification',
    description: 'Review a delivery status for each criterion instead of one vague summary.',
  },
  {
    icon: Code2,
    title: 'Implementation evidence',
    description: 'Ground findings in changed files and source references, with line links where available.',
  },
  {
    icon: TestTube2,
    title: 'Test and CI evidence',
    description: 'Use available test results and GitHub check or status signals as supporting evidence.',
  },
  {
    icon: ShieldCheck,
    title: 'Deterministic delivery decisions',
    description: 'A consistent rules-based outcome follows required-criterion and evidence rules.',
  },
  {
    icon: Clock3,
    title: 'Historical verification records',
    description: 'Return to verification history in the console when you need more context.',
  },
];

const criteria = [
  {
    title: 'Track consecutive failed login attempts',
    file: 'auth_app/views.py:42–56',
  },
  {
    title: 'Temporarily lock the account after repeated failures',
    file: 'auth_app/views.py:58–71',
  },
  {
    title: 'Reset the failed-attempt count after successful login',
    file: 'auth_app/views.py:73–79',
  },
  {
    title: 'Cover the lockout behavior with tests',
    file: 'auth_app/tests.py:110–148',
  },
];

const HomePage = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  return (
    <main className="requora-landing">
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a
            aria-label="Requora home"
            className="landing-brand"
            href="#top"
            onClick={closeMenu}
          >
            <BrandMark className="landing-brand-mark" />
            <span>requora</span>
          </a>

          <button
            aria-expanded={menuOpen}
            aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            className="landing-menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            {menuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>

          <nav
            aria-label="Main navigation"
            className={`landing-nav${menuOpen ? ' is-open' : ''}`}
          >
            <a href="#how-it-works" onClick={closeMenu}>How it works</a>
            <a href="#features" onClick={closeMenu}>Features</a>
            <a href="#integrations" onClick={closeMenu}>Integrations</a>
            <Link to="/login" onClick={closeMenu}>Console</Link>
            {githubAppInstallUrl ? (
              <a
                className="landing-nav-cta"
                href={githubAppInstallUrl}
                onClick={closeMenu}
                rel="noreferrer"
                target="_blank"
              >
                Install on GitHub <ArrowUpRight size={15} />
              </a>
            ) : (
              <span className="landing-nav-cta is-disabled">
                GitHub App not configured
              </span>
            )}
          </nav>
        </div>
      </header>

      <section className="landing-hero landing-container" id="top">
        <div className="landing-hero-copy">
          <div className="landing-eyebrow">
            <span className="landing-eyebrow-dot" />
            Requirement-driven delivery verification
          </div>
          <h1>
            Know what your code <span>actually delivers.</span>
          </h1>
          <p className="landing-hero-description">
            Requora connects software requirements to pull requests,
            implementation changes and test evidence, showing exactly what
            your team has delivered.
          </p>
          <div className="landing-hero-actions">
            {githubAppInstallUrl ? (
              <a
                className="landing-button landing-button-primary"
                href={githubAppInstallUrl}
                rel="noreferrer"
                target="_blank"
              >
                Install Requora on GitHub <ArrowUpRight size={17} />
              </a>
            ) : (
              <span className="landing-button landing-button-disabled">
                GitHub App installation unavailable
              </span>
            )}
            <a className="landing-button landing-button-secondary" href="#how-it-works">
              See how it works <ArrowDown size={16} />
            </a>
          </div>
          <div className="landing-hero-proof">
            <span><Check size={14} /> Evidence-linked</span>
            <span><Check size={14} /> GitHub-native</span>
            <span><Check size={14} /> Criterion by criterion</span>
          </div>
        </div>

        <div
          aria-label="Illustrative GitHub pull request delivery verification report"
          className="landing-report-wrap"
        >
          <div className="landing-report-glow" />
          <article className="landing-report">
            <div className="landing-report-topbar">
              <div className="landing-window-dots" aria-hidden="true">
                <i /><i /><i />
              </div>
              <span>GITHUB CHECK</span>
              <span className="landing-report-menu" aria-hidden="true">•••</span>
            </div>
            <div className="landing-report-content">
              <div className="landing-report-label">
                <GitPullRequest size={15} />
                <span>DELIVERY VERIFICATION</span>
                <span className="landing-sample-label">ILLUSTRATIVE</span>
              </div>
              <div className="landing-pr-title">
                <h2>Protect email-based login</h2>
                <span>#26</span>
              </div>
              <div className="landing-repo-line">
                <span className="landing-repo-dot" />
                kileldylan / aci_test
                <span className="landing-branch"><GitBranch size={13} /> feature/login-lockout</span>
              </div>

              <div className="landing-verdict">
                <div className="landing-verdict-icon"><CircleCheck size={19} /></div>
                <div>
                  <strong>Delivery verified</strong>
                  <span>All required criteria have evidence</span>
                </div>
                <span className="landing-verified-pill">VERIFIED</span>
              </div>

              <div className="landing-criteria-heading">
                <span>ACCEPTANCE CRITERIA</span>
                <span>4 / 4</span>
              </div>
              <ul className="landing-criteria-list">
                {criteria.map((criterion) => (
                  <li key={criterion.title}>
                    <CircleCheck size={16} />
                    <div className="landing-criterion-copy">
                      <span>{criterion.title}</span>
                      <code><GitCommitHorizontal size={12} /> {criterion.file}</code>
                    </div>
                    <span className="landing-satisfied">SATISFIED</span>
                  </li>
                ))}
              </ul>

              <div className="landing-report-footer">
                <span><TestTube2 size={14} /> Tests passing</span>
                <span><GitCommitHorizontal size={14} /> 8f2c1a7</span>
                <span><CheckCheck size={14} /> Evidence attached</span>
              </div>
            </div>
          </article>
          <div className="landing-report-caption">
            <span className="landing-caption-dot" />
            An illustrative report · Your team reviews in GitHub
          </div>
        </div>
      </section>

      <div className="landing-container">
        <div className="landing-value-strip">
          <span>Requirements in.</span>
          <span className="landing-strip-arrow"><ArrowRight size={17} /></span>
          <span>Evidence out.</span>
          <span className="landing-strip-note">A traceable path from the ticket to the code.</span>
        </div>
      </div>

      <section className="landing-section landing-section-muted" id="how-it-works">
        <div className="landing-container">
          <div className="landing-section-heading">
            <p className="landing-section-kicker">FROM REQUIREMENT TO PROOF</p>
            <h2>A clearer path from request to delivery.</h2>
            <p>Keep the review where your team already works: in the pull request.</p>
          </div>
          <div className="landing-steps">
            {workflowSteps.map(({ number, icon: Icon, title, description }) => (
              <article className="landing-step" key={number}>
                <div className="landing-step-top">
                  <span className="landing-step-icon"><Icon size={20} /></span>
                  <span className="landing-step-number">{number}</span>
                </div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section" id="why-requora">
        <div className="landing-container landing-problem-layout">
          <div className="landing-problem-intro">
            <p className="landing-section-kicker">THE DELIVERY GAP</p>
            <h2>Passing tests doesn’t always mean delivering the requirement.</h2>
            <p>
              Tests and code review matter. But on their own, they don’t show
              whether every acceptance criterion made it into the change.
            </p>
          </div>
          <div className="landing-problem-list">
            <article>
              <span className="landing-problem-index">01</span>
              <div>
                <h3>Requirements drift away from implementation</h3>
                <p>Ticket context gets lost as work moves through branches and reviews.</p>
              </div>
            </article>
            <article>
              <span className="landing-problem-index">02</span>
              <div>
                <h3>Green CI is not criterion-level proof</h3>
                <p>A passing pipeline doesn’t guarantee that each requested behavior was delivered.</p>
              </div>
            </article>
            <article>
              <span className="landing-problem-index">03</span>
              <div>
                <h3>Code review alone leaves a gap</h3>
                <p>Reviewers need to connect the change back to the original requirement.</p>
              </div>
            </article>
            <div className="landing-problem-answer">
              <ShieldCheck size={19} />
              <p>Requora connects requirements, changes and available test evidence in one traceable report.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section landing-section-muted" id="features">
        <div className="landing-container">
          <div className="landing-section-heading">
            <p className="landing-section-kicker">BUILT FOR DELIVERY CONFIDENCE</p>
            <h2>Evidence for the work that matters.</h2>
            <p>Focused on what changed, what was requested and what can be verified.</p>
          </div>
          <div className="landing-feature-grid">
            {featureCards.map(({ icon: Icon, title, description }) => (
              <article className="landing-feature-card" key={title}>
                <span className="landing-feature-icon"><Icon size={19} /></span>
                <h3>{title}</h3>
                <p>{description}</p>
                <ChevronRight className="landing-feature-arrow" size={16} aria-hidden="true" />
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section" id="integrations">
        <div className="landing-container landing-integrations">
          <div>
            <p className="landing-section-kicker">WORKS WITH YOUR WORKFLOW</p>
            <h2>Connected to the tools already in the loop.</h2>
            <p>
              Requora links Jira requirements to GitHub pull requests and
              publishes verification where engineering teams review changes.
            </p>
          </div>
          <div className="landing-integration-list">
            <div className="landing-integration-card">
              <span className="landing-integration-icon landing-github-icon"><GitBranch size={24} /></span>
              <div><strong>GitHub</strong><span>Pull requests, code and checks</span></div>
              <span className="landing-integration-status">AVAILABLE</span>
            </div>
            <div className="landing-integration-card">
              <span className="landing-integration-icon landing-jira-icon"><Workflow size={23} /></span>
              <div><strong>Jira</strong><span>Requirement linking and retrieval</span></div>
              <span className="landing-integration-status">AVAILABLE</span>
            </div>
            <p className="landing-integration-note">Integrations reflect current product capabilities.</p>
          </div>
        </div>
      </section>

      <section className="landing-container">
        <div className="landing-final-cta">
          <div className="landing-final-mark"><BrandMark className="landing-brand-mark" /></div>
          <p className="landing-section-kicker">REQUIREMENTS IN. EVIDENCE OUT.</p>
          <h2>Ship with evidence, not assumptions.</h2>
          <p>Connect your GitHub repositories and start verifying delivery against real requirements.</p>
          {githubAppInstallUrl ? (
            <a
              className="landing-button landing-button-primary"
              href={githubAppInstallUrl}
              rel="noreferrer"
              target="_blank"
            >
              Get started with Requora <ArrowUpRight size={17} />
            </a>
          ) : (
            <span className="landing-button landing-button-disabled">
              GitHub App installation unavailable
            </span>
          )}
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="landing-footer-brand">
            <a aria-label="Requora home" className="landing-brand" href="#top">
              <BrandMark className="landing-brand-mark" />
              <span>requora</span>
            </a>
            <p>Know what you actually delivered.</p>
          </div>
          <a
            className="landing-repository-link"
            href="https://github.com/kileldylan/OnSpec"
            rel="noreferrer"
            target="_blank"
          >
            <GitBranch size={16} /> GitHub repository <ArrowUpRight size={14} />
          </a>
          <span className="landing-copyright">© {new Date().getFullYear()} Requora</span>
        </div>
      </footer>
    </main>
  );
};

export default HomePage;
