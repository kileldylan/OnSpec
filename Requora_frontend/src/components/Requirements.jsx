// src/components/Requirements.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FileText,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  Loader2,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Calendar,
  ExternalLink,
  GitPullRequest,
  Zap,
  Shield,
} from 'lucide-react';
import { requoraApi } from '../api/requora';
import StatusBadge from './StatusBadge';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const responseItems = (response) => {
  const payload = response?.data;
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
};

export const Requirements = () => {
  const navigate = useNavigate();
  const [selectedRepo, setSelectedRepo] = useState('all');
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const { user } = useAuth();

  const query = useQuery({
    queryKey: ['requirements', user?.id, selectedRepo, page],
    enabled: Boolean(user),
    queryFn: async () => {
      const [repoResponse, requirementResponse] = await Promise.all([
        requoraApi.getRepositories({ limit: 100 }),
        selectedRepo === 'all'
          ? requoraApi.getAllRequirements({ page, page_size: 50 })
          : requoraApi.getRepositoryRequirements(selectedRepo, { page, page_size: 50 }),
      ]);
      const repos = responseItems(repoResponse);
      const repoById = new Map(repos.map((repo) => [String(repo.id), repo]));
      const items = responseItems(requirementResponse).map((requirement) => ({
        ...requirement,
        repo: repoById.get(String(requirement.repository))?.full_name || 'Unknown',
      }));
      items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      const verificationResponse = items.length
        ? await requoraApi.getVerifications({
          requirements: items.map((item) => item.id).join(','),
          latest_per: 'requirement',
        })
        : { data: [] };
      const verifications = {};
      responseItems(verificationResponse).forEach((verification) => {
        if (verification.requirement?.id && !verifications[verification.requirement.id]) {
          verifications[verification.requirement.id] = verification;
        }
      });

      return {
        repositories: repos,
        requirements: items,
        verifications,
        totalCount: requirementResponse.data?.count ?? items.length,
        totalPages: requirementResponse.data?.count
          ? Math.ceil(requirementResponse.data.count / 50)
          : 1,
      };
    },
    staleTime: 60_000,
  });
  const repositories = query.data?.repositories || [];
  const requirements = query.data?.requirements || [];
  const verifications = query.data?.verifications || {};
  const loading = query.isLoading;
  const refreshing = query.isFetching && !query.isLoading;
  const lastUpdated = query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : new Date();

  useEffect(() => {
    if (query.error) {
      console.error('Error fetching requirements:', query.error);
      toast.error('Failed to load requirements');
    }
  }, [query.error]);

  const handleRefresh = async () => {
    await query.refetch();
    toast.success('Requirements refreshed');
  };

  const getVerificationStatus = (reqId) => {
    const ver = verifications[reqId];
    if (!ver) return 'pending';
    return ver.status;
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'verified': return CheckCircle;
      case 'partial': return AlertTriangle;
      case 'unverified': return XCircle;
      default: return Clock;
    }
  };

  const getSourceIcon = (source) => {
    switch (source?.toLowerCase()) {
      case 'jira': return <Zap className="w-4 h-4 text-blue-400" />;
      case 'linear': return <Shield className="w-4 h-4 text-purple-400" />;
      case 'github': return <GitPullRequest className="w-4 h-4 text-green-400" />;
      default: return <FileText className="w-4 h-4 text-gray-400" />;
    }
  };

  const filteredRequirements = requirements.filter(req => {
    const matchesSearch = req.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          req.external_id?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || getVerificationStatus(req.id) === statusFilter;
    const matchesSource = sourceFilter === 'all' || req.source === sourceFilter;
    return matchesSearch && matchesStatus && matchesSource;
  });

  const formatTime = (date) => {
    if (!date) return 'N/A';
    return new Date(date).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center space-y-4">
          <Loader2 className="w-16 h-16 text-accent-middle animate-spin mx-auto" />
          <p className="text-dark-muted animate-pulse">Loading requirements...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="w-6 h-6 text-accent-middle" />
            Requirements
          </h1>
          <p className="text-dark-muted text-sm mt-1">
            {requirements.length} requirements across {repositories.length} repositories
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-dark-card border border-dark-border hover:border-accent-middle/30 transition-colors disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            <span className="text-sm">Refresh</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col md:flex-row gap-4 flex-wrap">
          {/* Repository Filter */}
          <div className="min-w-0 flex items-center gap-2">
            <Filter className="w-4 h-4 text-dark-muted" />
            <select
              value={selectedRepo}
              onChange={(e) => {
                setSelectedRepo(e.target.value);
                setPage(1);
              }}
              className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm"
            >
              <option value="all">All Repositories</option>
              {repositories.map(repo => (
                <option key={repo.id} value={repo.id}>
                  {repo.full_name}
                </option>
              ))}
            </select>
          </div>

          {/* Search */}
          <div className="relative min-w-0 flex-1 sm:min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by title or external ID..."
              className="w-full pl-10 pr-4 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm sm:w-auto"
          >
            <option value="all">All Statuses</option>
            <option value="verified">Verified</option>
            <option value="partial">Partial</option>
            <option value="unverified">Unverified</option>
            <option value="pending">Pending</option>
          </select>

          {/* Source Filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm sm:w-auto"
          >
            <option value="all">All Sources</option>
            <option value="jira">Jira</option>
            <option value="linear">Linear</option>
            <option value="github">GitHub</option>
            <option value="manual">Manual</option>
          </select>
        </div>
      </div>

      {/* Requirement Cards */}
      {filteredRequirements.length === 0 ? (
        <div className="card p-6 text-center sm:p-12">
          <FileText className="w-16 h-16 text-dark-muted/30 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Requirements Found</h3>
          <p className="text-dark-muted text-sm">
            {searchTerm || statusFilter !== 'all' || sourceFilter !== 'all'
              ? 'Try adjusting your filters or search terms'
              : 'Requirements will appear here once they are imported from Jira or created'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredRequirements.map((req) => {
            const status = getVerificationStatus(req.id);
            const StatusIcon = getStatusIcon(status);
            const ver = verifications[req.id];

            return (
              <div
                key={req.id}
                className="card min-w-0 p-4 hover:border-accent-middle/30 hover:shadow-lg hover:shadow-accent-start/5 transition-all duration-300 cursor-pointer group sm:p-5"
                onClick={() => navigate(`/requirements/${req.id}`)}
              >
                <div className="flex min-w-0 items-start justify-between gap-2 sm:gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {getSourceIcon(req.source)}
                      <span className="text-sm font-mono text-accent-middle">
                        {req.external_id}
                      </span>
                      <span className="text-xs text-dark-muted">•</span>
                      <span className="text-xs text-dark-muted uppercase">
                        {req.source}
                      </span>
                    </div>
                    <h3 className="font-semibold text-base mt-1 group-hover:text-accent-middle transition-colors line-clamp-2">
                      {req.title}
                    </h3>
                    {req.description && (
                      <p className="text-sm text-dark-muted mt-1 line-clamp-2">
                        {req.description}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-dark-muted">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatTime(req.created_at)}
                      </span>
                      <span className="text-xs bg-dark-bg px-2 py-0.5 rounded-full">
                        {req.repo}
                      </span>
                      {req.url && (
                        <a
                          href={req.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-accent-middle hover:text-accent-end transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ExternalLink className="w-3 h-3" />
                          View
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <StatusBadge status={status} size="sm" />
                    {ver && (
                      <div className="text-right">
                        {ver.confidence && (
                          <div className="text-xs text-dark-muted">
                            {parseFloat(ver.confidence) * 100}% confidence
                          </div>
                        )}
                        {ver.evidence_ids?.length > 0 && (
                          <div className="text-xs text-dark-muted flex items-center gap-1 justify-end">
                            📎 {ver.evidence_ids.length} evidence items
                          </div>
                        )}
                      </div>
                    )}
                    <StatusIcon className={clsx(
                      'w-5 h-5',
                      status === 'verified' ? 'text-verified' :
                      status === 'partial' ? 'text-partial' :
                      status === 'unverified' ? 'text-unverified' :
                      'text-pending'
                    )} />
                  </div>
                </div>

                {/* Criterion summary */}
                {ver?.criterion_results && ver.criterion_results.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-dark-border">
                    <div className="flex items-center gap-3">
                      {ver.criterion_results.map((criterion, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <StatusBadge status={criterion.status} size="sm" />
                          <span className="text-xs text-dark-muted">
                            {criterion.criterion?.text?.substring(0, 20)}...
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Verification summary */}
                {ver?.summary && (
                  <div className="mt-2 text-xs text-dark-muted">
                    {ver.summary}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="flex flex-col gap-3 border-t border-dark-border pt-4 text-xs text-dark-muted/60 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Showing {filteredRequirements.length} of {requirements.length} loaded requirements
          {query.data?.totalCount > requirements.length
            ? ` (${query.data.totalCount} total)`
            : ''}
        </span>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          <span>Last updated: {formatTime(lastUpdated)}</span>
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous requirements page"
              className="rounded border border-dark-border p-1.5 disabled:opacity-40"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => current - 1)}
              type="button"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>{page} / {query.data?.totalPages || 1}</span>
            <button
              aria-label="Next requirements page"
              className="rounded border border-dark-border p-1.5 disabled:opacity-40"
              disabled={page >= (query.data?.totalPages || 1) || loading}
              onClick={() => setPage((current) => current + 1)}
              type="button"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Requirements;