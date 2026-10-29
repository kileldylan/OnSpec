import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Layout';
import { aciApi } from './api/aci';
import Dashboard from './components/Dashboard';
import VerificationList from './components/VerificationList';
import VerificationDetail from './components/VerificationDetail';
import EvidenceChain from './components/EvidenceChain';
import Analytics from './components/Analytics';
import PullRequests from './components/PullRequests';
import PullRequestDetail from './components/PullRequestDetail';
import Requirements from './components/Requirements';
import HomePage from './components/HomePage';
import ProtectedRoute from './components/ProtectedRoute';
import { Login, Register } from './components/AuthPage';
import { AuthProvider } from './context/AuthContext';
import { Analytics as VercelAnalytics } from '@vercel/analytics/react';

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
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
              <Route path="console" element={<Navigate to="/pull-requests" replace />} />
              <Route path="overview" element={<Dashboard />} />
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
          <VercelAnalytics />
        </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
