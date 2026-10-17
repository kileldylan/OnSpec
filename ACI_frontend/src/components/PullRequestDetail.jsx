import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  GitPullRequest,
  GitBranch,
  ArrowLeft,
  User,
  Calendar,
  FileText,
  Plus,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { aciApi } from '../api/aci';
import StatusBadge from './StatusBadge';
import { clsx } from 'clsx';

export default function PullRequestDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [pr, setPr] = useState(null);
  const [commits, setCommits] = useState([]);
  const [verifications, setVerifications] = useState([]);
  const [error, setError] = useState(null);

  const repoId = searchParams.get('repo');

  useEffect(() => {
    if (!id) return;

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);

      try {
        // If we have repoId from query param, use the nested endpoint
        if (repoId) {
          const res = await aciApi.getPullRequestDetail(repoId, id);
          setPr(res.data.pull_request);
          setCommits(res.data.commits || []);
          setVerifications(res.data.verifications || []);
        } else {
          // Fallback: try to find the repo by fetching PRs from all repos
          const reposRes = await aciApi.getRepositories();
          const repos = Array.isArray(reposRes.data) ? reposRes.data : reposRes.data.results || [];

          let found = false;
          for (const repo of repos) {
            try {
              const res = await aciApi.getPullRequestDetail(repo.id, id);
              setPr(res.data.pull_request);
              setCommits(res.data.commits || []);
              setVerifications(res.data.verifications || []);
              found = true;
              break;
            } catch (e) {
              // not in this repo, continue
            }
          }

          if (!found) {
            setError('Pull request not found or you do not have access.');
          }
        }
      } catch (err) {
        console.error(err);
        setError('Failed to load pull request details.');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [id, repoId]);

  const handleStartVerification = () => {
    if (!pr) return;
    // Navigate to start verification flow or open modal
    // For now, go to requirements page with context
    navigate('/requirements', { 
      state: { 
        pullRequestId: pr.id,
        pullRequestNumber: pr.number 
      } 
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-3 text-gray-400">Loading pull request...</span>
      </div>
    );
  }

  if (error || !pr) {
    return (
      <div className="p-4 sm:p-6">
        <button
          onClick={() => navigate('/pull-requests')}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Pull Requests
        </button>
        <div className="bg-dark-card border border-dark-border rounded-lg p-8 text-center">
          <p className="text-red-400">{error || 'Pull request not found.'}</p>
        </div>
      </div>
    );
  }

  const totalAdditions = commits.reduce((sum, c) => 
    sum + (c.changed_files?.reduce((s, f) => s + (f.additions || 0), 0) || 0), 0);
  const totalDeletions = commits.reduce((sum, c) => 
    sum + (c.changed_files?.reduce((s, f) => s + (f.deletions || 0), 0) || 0), 0);

  const latestVerification = verifications.length > 0 ? verifications[0] : null;

  return (
    <div className="mx-auto min-w-0 max-w-6xl p-0 sm:p-2">
      {/* Header */}
      <div className="mb-6 flex flex-col items-stretch justify-between gap-3 sm:flex-row sm:items-center">
        <button
          onClick={() => navigate('/pull-requests')}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Pull Requests
        </button>

        <button
          onClick={handleStartVerification}
          className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Start Verification
        </button>
      </div>

      {/* PR Header */}
      <div className="mb-6 min-w-0 rounded-xl border border-dark-border bg-dark-card p-4 sm:p-6">
        <div className="flex items-start gap-4">
          <div className="mt-1">
            <GitPullRequest className="w-8 h-8 text-purple-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2 sm:gap-3">
              <span className="break-words text-lg font-semibold text-white sm:text-xl">
                #{pr.number} {pr.title}
              </span>
              <StatusBadge status={pr.state} />
              {pr.is_merged && (
                <span className="px-2 py-0.5 text-xs rounded bg-purple-900 text-purple-200">Merged</span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm text-gray-400">
              <div className="flex items-center gap-1.5">
                <User className="w-4 h-4" />
                {pr.author}
              </div>
              <div className="flex items-center gap-1.5">
                <GitBranch className="w-4 h-4 shrink-0" />
                <span className="break-all">{pr.source_branch} → {pr.target_branch}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4" />
                {new Date(pr.created_at).toLocaleDateString()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Verification Summary */}
      <div className="mb-6 min-w-0 rounded-xl border border-dark-border bg-dark-card p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Verification Status</h2>
          {latestVerification && (
            <StatusBadge status={latestVerification.status} />
          )}
        </div>

        {latestVerification ? (
          <div>
            <p className="text-gray-300 mb-3">{latestVerification.summary || 'No summary available.'}</p>
            <div className="text-sm text-gray-400">
              Confidence: {latestVerification.confidence ?? '—'}%
            </div>
            <button
              onClick={() => navigate(`/verifications/${latestVerification.id}`)}
              className="mt-4 text-sm text-blue-400 hover:text-blue-300 underline"
            >
              View full verification →
            </button>
          </div>
        ) : (
          <div className="text-gray-400">
            No verification has been run for this pull request yet.
            <button
              onClick={handleStartVerification}
              className="ml-2 text-blue-400 hover:text-blue-300 underline"
            >
              Start one now
            </button>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <div className="text-sm text-gray-400">Commits</div>
          <div className="text-2xl font-semibold mt-1">{commits.length}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <div className="text-sm text-gray-400">Changes</div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-green-400">+{totalAdditions}</span>
            <span className="text-red-400">-{totalDeletions}</span>
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4">
          <div className="text-sm text-gray-400">Verifications</div>
          <div className="text-2xl font-semibold mt-1">{verifications.length}</div>
        </div>
      </div>

      {/* Commits */}
      <div className="mb-6 min-w-0 rounded-xl border border-dark-border bg-dark-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5" /> Commits ({commits.length})
        </h2>

        {commits.length === 0 ? (
          <p className="text-gray-400">No commit data available.</p>
        ) : (
          <div className="space-y-3">
            {commits.map((commit, index) => (
              <div key={index} className="border border-dark-border rounded-lg p-4">
                <div className="font-mono text-sm text-gray-400 mb-1">
                  {commit.sha?.substring(0, 8)}
                </div>
                <div className="mb-2 break-words text-white">{commit.message}</div>
                <div className="text-xs text-gray-500">
                  {commit.author} • {commit.committed_at ? new Date(commit.committed_at).toLocaleString() : ''}
                </div>

                {commit.changed_files && commit.changed_files.length > 0 && (
                  <div className="mt-3 pl-2 border-l border-dark-border">
                    {commit.changed_files.map((file, fIdx) => (
                      <div key={fIdx} className="flex min-w-0 justify-between gap-3 py-0.5 text-sm">
                        <span className="min-w-0 break-all text-gray-300">{file.filename}</span>
                        <span className="text-xs text-gray-500 ml-2 whitespace-nowrap">
                          {file.status} {file.additions > 0 && `+${file.additions}`} {file.deletions > 0 && `-${file.deletions}`}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Verifications List */}
      {verifications.length > 0 && (
        <div className="min-w-0 rounded-xl border border-dark-border bg-dark-card p-4 sm:p-6">
          <h2 className="text-lg font-semibold mb-4">Verifications</h2>
          <div className="space-y-3">
            {verifications.map((v) => (
              <div
                key={v.id}
                onClick={() => navigate(`/verifications/${v.id}`)}
                className="border border-dark-border rounded-lg p-4 hover:border-blue-500/50 cursor-pointer transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-white">Verification #{v.id}</div>
                    <div className="text-sm text-gray-400 line-clamp-2">{v.summary}</div>
                  </div>
                  <StatusBadge status={v.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
