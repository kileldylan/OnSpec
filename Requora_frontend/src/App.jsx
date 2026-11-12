import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Layout';
import HomePage from './components/HomePage';
import ProtectedRoute from './components/ProtectedRoute';
import { Login, Register } from './components/AuthPage';
import { AuthProvider } from './context/AuthContext';
import { Analytics as VercelAnalytics } from '@vercel/analytics/react';

const Dashboard = lazy(() => import('./components/Dashboard'));
const VerificationList = lazy(() => import('./components/VerificationList'));
const VerificationDetail = lazy(() => import('./components/VerificationDetail'));
const CriterionEvidenceDetail = lazy(() => import('./components/CriterionEvidenceDetail'));
const Analytics = lazy(() => import('./components/Analytics'));
const Requirements = lazy(() => import('./components/Requirements'));

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
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="console" element={<Dashboard />} />
                  <Route path="overview" element={<Navigate to="/console" replace />} />
                  <Route path="verifications" element={<VerificationList />} />
                  <Route path="verifications/:id" element={<VerificationDetail />} />
                  <Route
                    path="verifications/:id/criteria/:criterionId/evidence"
                    element={<CriterionEvidenceDetail />}
                  />
                  <Route path="analytics" element={<Analytics />} />
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
