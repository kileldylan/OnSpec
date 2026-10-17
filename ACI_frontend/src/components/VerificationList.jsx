import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, 
  Filter, 
  RefreshCw,
  ChevronDown,
  Calendar,
  GitPullRequest,
  FileCode,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Loader2,
} from 'lucide-react';
import { aciApi } from '../api/aci';
import StatusBadge from './StatusBadge';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

const statusOptions = [
  { value: 'all', label: 'All Statuses' },
  { value: 'verified', label: 'Verified' },
  { value: 'partial', label: 'Partial' },
  { value: 'unverified', label: 'Unverified' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' },
];

const sortOptions = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'confidence', label: 'Highest Confidence' },
];

export const VerificationList = () => {
  const navigate = useNavigate();
  const [verifications, setVerifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [showFilters, setShowFilters] = useState(false);
  const [processingQueued, setProcessingQueued] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 10,
    total: 0,
  });

  useEffect(() => {
    fetchVerifications();
  }, [statusFilter, sortBy, pagination.page]);

  const fetchVerifications = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page,
        page_size: pagination.pageSize,
        ordering: sortBy === 'newest' ? '-created_at' : 'created_at',
        ...(statusFilter !== 'all' && { status: statusFilter }),
        ...(searchTerm && { search: searchTerm }),
      };
      
      const response = await aciApi.getVerifications(params);
      const data = response.data.results || response.data || [];
      setVerifications(Array.isArray(data) ? data : []);
      if (response.data.count) {
        setPagination(prev => ({ ...prev, total: response.data.count }));
      }
    } catch (error) {
      console.error('Error fetching verifications:', error);
      toast.error('Failed to load verifications');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchVerifications();
  };

  const handleProcessQueued = async () => {
    try {
      setProcessingQueued(true);
      const response = await aciApi.processQueuedVerifications({ limit: 1 });
      const processed = response.data?.processed || 0;

      if (processed > 0) {
        toast.success(`Processed ${processed} queued verification run${processed === 1 ? '' : 's'}.`);
      } else {
        toast('No queued verification runs waiting to be processed.');
      }

      await fetchVerifications();
    } catch (error) {
      console.error('Error processing queued verification runs:', error);
      toast.error('Failed to run queued verification worker');
    } finally {
      setProcessingQueued(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'verified': return CheckCircle;
      case 'partial': return AlertTriangle;
      case 'unverified': return XCircle;
      case 'pending': return Clock;
      default: return Clock;
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'verified': return 'text-verified border-verified/20';
      case 'partial': return 'text-partial border-partial/20';
      case 'unverified': return 'text-unverified border-unverified/20';
      case 'pending': return 'text-pending border-pending/20';
      default: return 'text-dark-muted border-dark-border';
    }
  };

  if (loading && pagination.page === 1) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-4">
          <Loader2 className="w-12 h-12 text-accent-middle animate-spin mx-auto" />
          <p className="text-dark-muted">Loading verifications...</p>
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
            <FileCode className="w-6 h-6 text-accent-middle" />
            Verifications
          </h1>
          <p className="text-dark-muted text-sm mt-1">
            {pagination.total} verifications across all requirements
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            onClick={handleProcessQueued}
            disabled={processingQueued}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-middle text-dark-bg hover:opacity-90 transition-opacity text-sm disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {processingQueued ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {processingQueued ? 'Running worker...' : 'Run worker'}
          </button>
          <button
            onClick={() => { setPagination({ ...pagination, page: 1 }); fetchVerifications(); }}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-dark-card border border-dark-border hover:border-accent-middle/30 transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by requirement ID or title..."
                className="w-full pl-10 pr-4 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle transition-colors"
              />
            </div>
          </form>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle transition-colors text-sm sm:w-auto sm:px-4"
            >
              {statusOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full min-w-0 px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle transition-colors text-sm sm:w-auto sm:px-4"
            >
              {sortOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Verification Cards */}
      {verifications.length === 0 ? (
        <div className="card p-6 text-center sm:p-12">
          <div className="max-w-md mx-auto">
            <FileCode className="w-16 h-16 text-dark-muted/30 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Verifications Found</h3>
            <p className="text-dark-muted text-sm">
              {searchTerm || statusFilter !== 'all' 
                ? 'Try adjusting your filters or search terms'
                : 'Create a PR with a Jira key to get started'}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {verifications.map((ver) => {
            const StatusIcon = getStatusIcon(ver.status);
            return (
              <div
                key={ver.id}
                onClick={() => navigate(`/verifications/${ver.id}`)}
                className={clsx(
                  'card min-w-0 p-4 cursor-pointer transition-all duration-300 sm:p-6',
                  'hover:border-accent-middle/30 hover:shadow-lg hover:shadow-accent-start/5',
                  'group'
                )}
              >
                <div className="flex flex-col md:flex-row md:items-center gap-4">
                  {/* Main Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <StatusBadge status={ver.status} size="sm" />
                      <span className="text-xs text-dark-muted">
                        #{ver.id}
                      </span>
                    </div>
                    <h3 className="font-semibold text-lg truncate">
                      {ver.requirement?.title || 'Untitled Requirement'}
                    </h3>
                    <div className="flex flex-wrap items-center gap-4 mt-1 text-sm text-dark-muted">
                      {ver.requirement?.external_id && (
                        <span className="flex items-center gap-1">
                          <FileCode className="w-3.5 h-3.5" />
                          {ver.requirement.external_id}
                        </span>
                      )}
                      {ver.pull_request?.number && (
                        <span className="flex items-center gap-1">
                          <GitPullRequest className="w-3.5 h-3.5" />
                          PR #{ver.pull_request.number}
                        </span>
                      )}
                      {ver.verification_timestamp && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {new Date(ver.verification_timestamp).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="flex items-center justify-between gap-4 sm:justify-start sm:gap-6">
                    {ver.confidence && (
                      <div className="text-center">
                        <div className="text-sm font-medium text-dark-text">
                          {Math.round(ver.confidence * 100)}%
                        </div>
                        <div className="text-xs text-dark-muted">Confidence</div>
                      </div>
                    )}
                    {ver.criteria_evaluations && (
                      <div className="text-center">
                        <div className="text-sm font-medium text-dark-text">
                          {ver.criteria_evaluations.filter(c => c.status === 'satisfied').length}
                          /{ver.criteria_evaluations.length}
                        </div>
                        <div className="text-xs text-dark-muted">Criteria</div>
                      </div>
                    )}
                    <div className={clsx(
                      'p-2 rounded-lg border transition-colors',
                      getStatusColor(ver.status),
                      'group-hover:border-opacity-100'
                    )}>
                      <StatusIcon className="w-5 h-5" />
                    </div>
                  </div>
                </div>

                {/* Evidence summary */}
                {ver.evidence_count > 0 && (
                  <div className="mt-3 pt-3 border-t border-dark-border flex items-center gap-4 text-xs text-dark-muted">
                    <span className="flex items-center gap-1">
                      📄 {ver.evidence_count} evidence items
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {pagination.total > pagination.pageSize && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-dark-muted">
            Showing {((pagination.page - 1) * pagination.pageSize) + 1} - 
            {Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
              disabled={pagination.page === 1}
              className={clsx(
                'px-3 py-1 rounded-lg border border-dark-border transition-colors',
                pagination.page === 1 ? 'opacity-50 cursor-not-allowed' : 'hover:border-accent-middle'
              )}
            >
              Previous
            </button>
            <span className="text-sm text-dark-muted">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.pageSize)}
            </span>
            <button
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
              disabled={pagination.page >= Math.ceil(pagination.total / pagination.pageSize)}
              className={clsx(
                'px-3 py-1 rounded-lg border border-dark-border transition-colors',
                pagination.page >= Math.ceil(pagination.total / pagination.pageSize) 
                  ? 'opacity-50 cursor-not-allowed' 
                  : 'hover:border-accent-middle'
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default VerificationList;