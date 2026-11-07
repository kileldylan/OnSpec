import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Layout';
import { aciApi } from './api/aci';
import HomePage from './components/HomePage';
import ProtectedRoute from './components/ProtectedRoute';
import { Login, Register } from './components/AuthPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Analytics as VercelAnalytics } from '@vercel/analytics/react';

const Dashboard = lazy(() => import('./components/Dashboard'));
const VerificationList = lazy(() => import('./components/VerificationList'));
const VerificationDetail = lazy(() => import('./components/VerificationDetail'));
const EvidenceChain = lazy(() => import('./components/EvidenceChain'));
const Analytics = lazy(() => import('./components/Analytics'));
const PullRequests = lazy(() => import('./components/PullRequests'));
const PullRequestDetail = lazy(() => import('./components/PullRequestDetail'));
const Requirements = lazy(() => import('./components/Requirements'));

function EvidencePage() {
  const [evidence, setEvidence] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    aciApi.getEvidence()
      .then((response) => {
        const payload = response.data;
        setEvidence(Array.isArray(payload) ? payload : payload.results || []);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading evidence...</div>;
  }

  return <EvidenceChain evidence={evidence} />;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 60000,
    },
  },
});

function HomeRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-dark-bg text-dark-muted"
        role="status"
      >
        Loading Requora...
      </div>
    );
  }

  return user ? <Navigate to="/console" replace /> : <HomePage />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
        <BrowserRouter>
          <Toaster
            position='top-right'
            toastOptions={{
              duration: 4000,
              className: 'bg-dark-card text-dark-text border border-dark-border',
            }}
          />
          <Suspense
            fallback={
              <div
                className="flex min-h-screen items-center justify-center bg-dark-bg text-dark-muted"
                role="status"
              >
                Loading Requora...
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<HomeRoute />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="console" element={<Dashboard />} />
                  <Route path="overview" element={<Navigate to="/console" replace />} />
                  <Route path="verifications" element={<VerificationList />} />
                  <Route path="verifications/:id" element={<VerificationDetail />} />
                  <Route path="evidence" element={<EvidencePage />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="pull-requests" element={<PullRequests />} />
                  <Route path="pull-requests/:id" element={<PullRequestDetail />} />
                  <Route path="requirements" element={<Requirements />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
          <VercelAnalytics />
        </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
