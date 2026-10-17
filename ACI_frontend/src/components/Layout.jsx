import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  GitPullRequest, 
  CheckCircle, 
  Sun,
  Moon,
  Sparkles,
  Shield,
  FileCode,
  FileText,
  LogOut,
  Menu,
  X,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { clsx } from 'clsx';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: CheckCircle, label: 'Verifications', path: '/verifications' },
  { icon: GitPullRequest, label: 'Pull Requests', path: '/pull-requests' },
  { icon: FileCode, label: 'Evidence', path: '/evidence' },
  { icon: FileText, label: 'Requirements', path: '/requirements' },
  { icon: TrendingUp, label: 'Analytics', path: '/analytics' },
];

const Navigation = ({ mobile = false, onNavigate }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  return (
    <nav
      aria-label={mobile ? 'Mobile navigation' : 'Main navigation'}
      className={clsx(
        'bg-dark-card p-4 flex flex-col',
        mobile
          ? 'h-full w-[min(18rem,85vw)]'
          : 'fixed left-0 top-0 hidden h-full w-64 border-r border-dark-border md:flex'
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between gap-2 mb-8 px-2">
        <div className="flex items-center gap-2">
          <Shield className="w-8 h-8 text-accent-middle" />
          <span className="text-xl font-bold gradient-text">ACI</span>
        </div>
        {mobile && (
          <button
            type="button"
            onClick={onNavigate}
            aria-label="Close navigation"
            className="rounded-lg p-2 text-dark-muted hover:bg-dark-hover hover:text-dark-text md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <div className="flex-1 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => {
              navigate(item.path);
              onNavigate?.();
            }}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              'hover:bg-dark-hover text-dark-muted hover:text-dark-text',
              (item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)) &&
                'bg-accent-start/10 text-accent-middle'
            )}
          >
            <item.icon className="w-5 h-5" />
            <span className="text-sm font-medium">{item.label}</span>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-dark-border pt-4 space-y-3">
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-dark-hover transition-colors text-dark-muted hover:text-dark-text"
        >
          {theme === 'dark' ? (
            <Sun className="w-5 h-5" />
          ) : (
            <Moon className="w-5 h-5" />
          )}
          <span className="text-sm font-medium">
            {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </span>
        </button>
        
        <button
          onClick={async () => {
            await logout();
            onNavigate?.();
            navigate('/login', { replace: true });
          }}
          className="w-full min-w-0 flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-dark-hover transition-colors text-dark-muted hover:text-dark-text"
        >
          <LogOut className="w-5 h-5" />
          <span className="min-w-0 truncate text-left text-sm font-medium">
            Sign out {user?.username ? `(${user.username})` : ''}
          </span>
        </button>
        
        <div className="px-3 pt-2">
          <div className="flex items-center gap-2 text-xs text-dark-muted/60">
            <Sparkles className="w-3 h-3" />
            <span>v1.0 · Online</span>
            <span className="w-1.5 h-1.5 rounded-full bg-verified animate-pulse"></span>
          </div>
        </div>
      </div>
    </nav>
  );
};

export const Layout = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen min-w-0 overflow-x-hidden bg-dark-bg">
      <Navigation />
      <header className="fixed inset-x-0 top-0 z-30 flex h-16 items-center gap-3 border-b border-dark-border bg-dark-card/95 px-4 backdrop-blur md:hidden">
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          aria-label="Open navigation"
          aria-expanded={menuOpen}
          className="rounded-lg p-2 text-dark-muted hover:bg-dark-hover hover:text-dark-text"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-accent-middle" />
          <span className="font-bold gradient-text">ACI</span>
        </div>
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            onClick={() => setMenuOpen(false)}
            aria-label="Close navigation menu"
            className="absolute inset-0 h-full w-full bg-black/60"
          />
          <div className="relative z-10 h-full shadow-2xl">
            <Navigation mobile onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      )}

      <main className="min-h-screen min-w-0 overflow-x-hidden bg-grid-pattern px-4 pb-6 pt-20 sm:px-6 sm:pb-8 sm:pt-24 md:ml-64 md:px-6 md:pt-8 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;