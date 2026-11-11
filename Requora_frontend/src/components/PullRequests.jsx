// src/components/PullRequests.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  GitPullRequest,
  GitBranch,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Loader2,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Calendar,
  User,
  Zap,
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

export const PullRequests = () => {
  const navigate = useNavigate();
  const [selectedRepo, setSelectedRepo] = useState('all');
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const { user } = useAuth();

  const query = useQuery({
    queryKey: ['pull-requests', user?.id, selectedRepo, page],
    enabled: Boolean(user),
    queryFn: async () => {
      const [repoResponse, prResponse] = await Promise.all([
        requoraApi.getRepositories({ limit: 100 }),
        selectedRepo === 'all'
          ? requoraApi.getAllPullRequests({ page, page_size: 50 })
          : requoraApi.getRepositoryPullRequests(selectedRepo, { page, page_size: 50 }),
      ]);
      const repos = responseItems(repoResponse);
      const repoById = new Map(repos.map((repo) => [String(repo.id), repo]));
      const prs = responseItems(prResponse).map((pr) => ({
        ...pr,
        repo: repoById.get(String(pr.repository))?.full_name || 'Unknown',
      }));
      prs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      const verificationResponse = prs.length
        ? await requoraApi.getVerifications({
          pull_requests: prs.map((pr) => pr.id).join(','),
          latest_per: 'pull_request',
        })
        : { data: [] };
      const verifications = {};
      responseItems(verificationResponse).forEach((verification) => {
        const pullRequestId = verification.pull_request?.id;
        if (pullRequestId && !verifications[pullRequestId]) {
          verifications[pullRequestId] = verification;
        }
      });

      return {
        repositories: repos,
        pullRequests: prs,
        verifications,
        totalCount: prResponse.data?.count ?? prs.length,
        totalPages: prResponse.data?.count
          ? Math.ceil(prResponse.data.count / 50)
          : 1,
      };
    },
    staleTime: 60_000,
  });
  const repositories = query.data?.repositories || [];
  const pullRequests = query.data?.pullRequests || [];
  const verifications = query.data?.verifications || {};
  const loading = query.isLoading;
  const refreshing = query.isFetching && !query.isLoading;
  const lastUpdated = query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : new Date();

  useEffect(() => {
    if (query.error) {
      console.error('Error fetching PR data:', query.error);
      toast.error('Failed to load pull requests');
    }
  }, [query.error]);

  const handleRefresh = async () => {
    await query.refetch();
    toast.success('Pull requests refreshed');
  };

  const handleStartVerification = async (repoId, prNumber) => {
    try {
      await requoraApi.startVerification(repoId, {
        pull_request_number: prNumber,
        // Requora will auto-detect Jira key from PR title
      });
      toast.success(`Verification started for PR #${prNumber}`);
      setTimeout(() => query.refetch(), 2000);
    } catch {
      toast.error('Failed to start verification');
    }
  };

  const getVerificationStatus = (prId) => {
    const ver = verifications[prId];
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

  const filteredPRs = pullRequests.filter(pr => {
    const matchesSearch = pr.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          pr.author?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          `#${pr.number}`.includes(searchTerm);
    const matchesStatus = statusFilter === 'all' || getVerificationStatus(pr.id) === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const formatTime = (date) => {
    if (!date) return 'N/A';
    return new Date(date).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center space-y-4">
          <Loader2 className="w-16 h-16 text-accent-middle animate-spin mx-auto" />
          <p className="text-dark-muted animate-pulse">Loading pull requests...</p>
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
            <GitPullRequest className="w-6 h-6 text-accent-middle" />
            Pull Requests
          </h1>
          <p className="text-dark-muted text-sm mt-1">
            {pullRequests.length} pull requests across {repositories.length} repositories
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
        <div className="flex flex-col md:flex-row gap-4">
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
          <div className="min-w-0 flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by title, author, or PR number..."
              className="w-full pl-10 pr-4 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm md:w-auto"
          >
            <option value="all">All Statuses</option>
            <option value="verified">Verified</option>
            <option value="partial">Partial</option>
            <option value="unverified">Unverified</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      {/* PR Cards */}
      {filteredPRs.length === 0 ? (
        <div className="card p-6 text-center sm:p-12">
          <GitPullRequest className="w-16 h-16 text-dark-muted/30 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Pull Requests Found</h3>
          <p className="text-dark-muted text-sm">
            {searchTerm || statusFilter !== 'all' 
              ? 'Try adjusting your filters or search terms'
              : 'Pull requests will appear here once they are created'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredPRs.map((pr) => {
            const status = getVerificationStatus(pr.id);
            const StatusIcon = getStatusIcon(status);
            const isJiraLinked = pr.title?.match(/[A-Z]+-\d+/);

            return (
              <div
                key={pr.id}
                className="card min-w-0 p-4 hover:border-accent-middle/30 hover:shadow-lg hover:shadow-accent-start/5 transition-all duration-300 cursor-pointer group sm:p-5"
                onClick={() => navigate(`/pull-requests/${pr.id}?repo=${pr.repository}`)}
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  {/* Left: PR Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-3">
                      <div className="mt-1">
                        <StatusBadge status={status} size="sm" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-mono text-dark-muted">
                            #{pr.number}
                          </span>
                          <span className="text-sm text-dark-muted">•</span>
                          <span className="min-w-0 break-words text-sm font-medium sm:truncate">
                            {pr.title}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-dark-muted">
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {pr.author}
                          </span>
                          <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3" />
                            {pr.source_branch} → {pr.target_branch}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatTime(pr.created_at)}
                          </span>
                          <span className="text-xs bg-dark-bg px-2 py-0.5 rounded-full">
                            {pr.repo}
                          </span>
                          {isJiraLinked && (
                            <span className="flex items-center gap-1 text-accent-middle">
                              <Zap className="w-3 h-3" />
                              {pr.title.match(/[A-Z]+-\d+/)?.[0]}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right: Status Info */}
                  <div className="flex flex-wrap items-center justify-between gap-3 sm:flex-shrink-0 sm:justify-end sm:gap-4">
                    {verifications[pr.id] && (
                      <div className="text-right">
                        <div className="flex items-center gap-2">
                          <StatusIcon className={clsx(
                            'w-4 h-4',
                            status === 'verified' ? 'text-verified' :
                            status === 'partial' ? 'text-partial' :
                            status === 'unverified' ? 'text-unverified' :
                            'text-pending'
                          )} />
                          <span className="text-sm capitalize">{status}</span>
                        </div>
                        {verifications[pr.id].confidence && (
                          <div className="text-xs text-dark-muted">
                            {parseFloat(verifications[pr.id].confidence) * 100}% confidence
                          </div>
                        )}
                        {verifications[pr.id].evidence_ids?.length > 0 && (
                          <div className="text-xs text-dark-muted">
                            📎 {verifications[pr.id].evidence_ids.length} evidence items
                          </div>
                        )}
                      </div>
                    )}

                    {!verifications[pr.id] && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const repo = repositories.find(r => r.full_name === pr.repo);
                          if (repo) {
                            handleStartVerification(repo.id, pr.number);
                          }
                        }}
                        className="px-3 py-1.5 rounded-lg bg-accent-start/20 text-accent-middle hover:bg-accent-start/30 transition-colors text-sm"
                      >
                        Verify
                      </button>
                    )}
                  </div>
                </div>

                {/* Verification Summary */}
                {verifications[pr.id]?.summary && (
                  <div className="mt-3 pt-3 border-t border-dark-border text-sm text-dark-muted">
                    {verifications[pr.id].summary}
                  </div>
                )}

                {/* Evidence tags */}
                {verifications[pr.id]?.evidence_ids?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {verifications[pr.id].evidence_ids.slice(0, 5).map((id) => (
                      <span key={id} className="text-xs bg-dark-bg px-2 py-0.5 rounded-full text-dark-muted">
                        📎 Evidence #{id}
                      </span>
                    ))}
                    {verifications[pr.id].evidence_ids.length > 5 && (
                      <span className="text-xs text-dark-muted">
                        +{verifications[pr.id].evidence_ids.length - 5} more
                      </span>
                    )}
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
          Showing {filteredPRs.length} of {pullRequests.length} loaded pull requests
          {query.data?.totalCount > pullRequests.length
            ? ` (${query.data.totalCount} total)`
            : ''}
        </span>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          <span>Last updated: {formatTime(lastUpdated)}</span>
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous pull-request page"
              className="rounded border border-dark-border p-1.5 disabled:opacity-40"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => current - 1)}
              type="button"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>{page} / {query.data?.totalPages || 1}</span>
            <button
              aria-label="Next pull-request page"
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

export default PullRequests;
