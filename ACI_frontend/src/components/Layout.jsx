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
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { clsx } from 'clsx';

const Navigation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  
const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: CheckCircle, label: 'Verifications', path: '/verifications' },
  { icon: GitPullRequest, label: 'Pull Requests', path: '/pull-requests' },
  { icon: FileCode, label: 'Evidence', path: '/evidence' },
  { icon: FileText, label: 'Requirements', path: '/requirements' },
];

  return (
    <nav className="fixed left-0 top-0 h-full w-64 bg-dark-card border-r border-dark-border p-4 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8 px-2">
        <Shield className="w-8 h-8 text-accent-middle" />
        <span className="text-xl font-bold gradient-text">ACI</span>
      </div>

      {/* Navigation */}
      <div className="flex-1 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
              'hover:bg-dark-hover text-dark-muted hover:text-dark-text',
              location.pathname === item.path && 'bg-accent-start/10 text-accent-middle'
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
            navigate('/login', { replace: true });
          }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-dark-hover transition-colors text-dark-muted hover:text-dark-text"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm font-medium">Sign out {user?.username ? `(${user.username})` : ''}</span>
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
  return (
    <div className="min-h-screen bg-dark-bg">
      <Navigation />
      <main className="ml-64 p-8 min-h-screen bg-grid-pattern">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;