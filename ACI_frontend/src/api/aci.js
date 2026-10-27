import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE = import.meta.env.DEV
  ? '/api'
  : (import.meta.env.VITE_API_URL || '/api');

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for Django session auth
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      if (error.response.status === 401) {
        toast.error('Please log in again');
      } else {
        toast.error(error.response.data?.detail || 'An error occurred');
      }
    } else if (error.request) {
      toast.error('No response from server');
    } else {
      toast.error('Request failed');
    }
    return Promise.reject(error);
  }
);

export const aciApi = {
  getCsrfToken: () => api.get('/auth/csrf/'),
  register: (data, csrfToken) =>
    api.post('/auth/register/', data, {
      headers: { 'X-CSRFToken': csrfToken },
    }),
  login: (data, csrfToken) =>
    api.post('/auth/login/', data, {
      headers: { 'X-CSRFToken': csrfToken },
    }),
  logout: (csrfToken) =>
    api.post('/auth/logout/', null, {
      headers: { 'X-CSRFToken': csrfToken },
    }),
  getCurrentUser: () => api.get('/auth/me/'),
  getGitHubAuthorizationUrl: () => api.get('/auth/github/connect/'),

  // ============ REPOSITORIES ============
  getRepositories: (params = {}) => 
    api.get('/repositories/', { params }),
  
  getRepository: (id) => 
    api.get(`/repositories/${id}/`),
  
  getRepositoryPullRequests: (repoId, params = {}) => 
    api.get(`/repositories/${repoId}/pull-requests/`, { params }),
  
  getRepositoryRequirements: (repoId, params = {}) => 
    api.get(`/repositories/${repoId}/requirements/`, { params }),

  // New: Pull Request Detail
  getPullRequestDetail: (repoId, prId) => 
    api.get(`/repositories/${repoId}/pull-requests/${prId}/`),

  startVerification: (repoId, data) => 
    api.post(`/repositories/${repoId}/start-verification/`, data),

  // ============ REQUIREMENTS ============
  getRequirements: (params = {}) => 
    api.get('/requirements/', { params }),
  
  getRequirement: (id) => 
    api.get(`/requirements/${id}/`),

  // ============ VERIFICATIONS ============
  getVerifications: (params = {}) => 
    api.get('/verifications/', { params }),
  
  getVerification: (id) => 
    api.get(`/verifications/${id}/`),

  processQueuedVerifications: (data = {}) =>
    api.post('/verifications/process-queued/', data),
  
  // ============ VERIFICATION RUNS ============
  getVerificationRuns: (params = {}) => 
    api.get('/verification-runs/', { params }),
  
  getVerificationRun: (id) => 
    api.get(`/verification-runs/${id}/`),

  // ============ DELIVERY DECISIONS ============
  getDeliveryDecisions: (params = {}) => 
    api.get('/delivery-decisions/', { params }),
  
  getDeliveryDecision: (id) => 
    api.get(`/delivery-decisions/${id}/`),

  // ============ EVIDENCE ============
  getEvidence: (params = {}) => 
    api.get('/evidence/', { params }),
  
  getEvidenceByRequirement: (requirementId) =>
    api.get('/evidence/', { params: { requirement: requirementId } }),

  // ============ TEST EXECUTIONS ============
  getTestExecutions: (params = {}) => 
    api.get('/test-executions/', { params }),
};

export default aciApi;
