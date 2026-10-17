
// src/components/Dashboard.jsx

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle,
  Clock,
  Database,
  FileCheck2,
  FileCode,
  GitBranch,
  GitPullRequest,
  Loader2,
  RefreshCw,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

import { aciApi } from '../api/aci';
import StatusBadge from './StatusBadge';
import StatsCard from './StatsCard';
BarChart3
/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

const responseItems = (response) => {
  const payload = response?.data;

  if (Array.isArray(payload)) {
    return payload;
  }

  if (Array.isArray(payload?.results)) {
    return payload.results;
  }

  return [];
};


const safeNumber = (value) => {
  const number = Number(value);

  return Number.isFinite(number) ? number : 0;
};


const truncate = (value, length = 70) => {
  if (!value) {
    return '';
  }

  if (value.length <= length) {
    return value;
  }

  return `${value.substring(0, length)}...`;
};


const formatDate = (value) => {
  if (!value) {
    return 'N/A';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return 'N/A';
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};


const formatTime = (value) => {
  if (!value) {
    return 'N/A';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return 'N/A';
  }

  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
};


const getVerificationStatus = (verification) => {
  return (
    verification?.status ||
    verification?.delivery_decision?.status ||
    verification?.decision?.status ||
    'pending'
  ).toLowerCase();
};


const getStatusIcon = (status) => {
  switch (status?.toLowerCase()) {
    case 'verified':
    case 'satisfied':
      return CheckCircle;

    case 'partial':
      return AlertTriangle;

    case 'unverified':
    case 'failed':
    case 'missing':
      return XCircle;

    default:
      return Clock;
  }
};


const getStatusClasses = (status) => {
  switch (status?.toLowerCase()) {
    case 'verified':
    case 'satisfied':
      return 'text-verified';

    case 'partial':
      return 'text-partial';

    case 'unverified':
    case 'failed':
    case 'missing':
      return 'text-unverified';

    default:
      return 'text-pending';
  }
};


/* -------------------------------------------------------------------------- */
/* Dashboard                                                                  */
/* -------------------------------------------------------------------------- */

export const Dashboard = () => {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [lastUpdated, setLastUpdated] = useState(new Date());

  const [repositories, setRepositories] = useState([]);
  const [verifications, setVerifications] = useState([]);
  const [recentPRs, setRecentPRs] = useState([]);
  const [recentEvidence, setRecentEvidence] = useState([]);

  /* ------------------------------------------------------------------------ */
  /* Data fetching                                                            */
  /* ------------------------------------------------------------------------ */

  const fetchData = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const [
        repositoriesResponse,
        verificationsResponse,
        evidenceResponse,
      ] = await Promise.all([
        aciApi.getRepositories(),
        aciApi.getVerifications({ limit: 50 }),
        aciApi.getEvidence({ limit: 10 }),
      ]);

      const repos = responseItems(repositoriesResponse);
      const verificationItems = responseItems(verificationsResponse);
      const evidenceItems = responseItems(evidenceResponse);

      setRepositories(repos);
      setVerifications(verificationItems);
      setRecentEvidence(evidenceItems);

      /*
       * Fetch PRs from repositories independently.

       * This avoids the old behaviour where only the first repository was
       * represented on the dashboard.
       */
      if (repos.length > 0) {
        const prResponses = await Promise.all(
          repos.slice(0, 10).map((repo) =>
            aciApi
              .getRepositoryPullRequests(repo.id, { limit: 5 })
              .then(responseItems)
              .catch((error) => {
                console.warn(
                  `Unable to load PRs for repository ${repo.id}`,
                  error
                );

                return [];
              })
          )
        );

        const prs = prResponses
          .flat()
          .sort((a, b) => {
            const dateA = new Date(
              a.updated_at || a.created_at || 0
            ).getTime();

            const dateB = new Date(
              b.updated_at || b.created_at || 0
            ).getTime();

            return dateB - dateA;
          });

        setRecentPRs(prs.slice(0, 8));
      } else {
        setRecentPRs([]);
      }

      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error fetching ACI dashboard data:', error);

      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);


  useEffect(() => {
    fetchData();

    /*
     * ACI is event-driven, but polling gives the dashboard a useful
     * development-time refresh while webhook processing is being built out.
     */
    const interval = setInterval(() => {
      fetchData(true);
    }, 60000);

    return () => clearInterval(interval);
  }, [fetchData]);


  const handleRefresh = async () => {
    await fetchData(true);
    toast.success('Dashboard refreshed');
  };


  /* ------------------------------------------------------------------------ */
  /* Derived statistics                                                       */
  /* ------------------------------------------------------------------------ */

  const stats = useMemo(() => {
    const total = verifications.length;

    const verified = verifications.filter(
      (verification) =>
        getVerificationStatus(verification) === 'verified'
    ).length;

    const partial = verifications.filter(
      (verification) =>
        getVerificationStatus(verification) === 'partial'
    ).length;

    const unverified = verifications.filter((verification) =>
      ['unverified', 'failed'].includes(
        getVerificationStatus(verification)
      )
    ).length;

    const pending = verifications.filter(
      (verification) =>
        getVerificationStatus(verification) === 'pending'
    ).length;

    const passRate =
      total > 0
        ? Math.round((verified / total) * 100)
        : 0;

    const requirements = new Set(
      verifications
        .map((verification) => {
          return (
            verification.requirement?.id ||
            verification.requirement_id ||
            verification.requirement?.external_id
          );
        })
        .filter(Boolean)
    ).size;

    const pullRequests = new Set(
      verifications
        .map((verification) => {
          return (
            verification.pull_request?.id ||
            verification.pull_request_id
          );
        })
        .filter(Boolean)
    ).size;

    return {
      total,
      verified,
      partial,
      unverified,
      pending,
      requirements,
      pullRequests,
      passRate,
      repositories: repositories.length,
    };
  }, [repositories, verifications]);


  /* ------------------------------------------------------------------------ */
  /* Attention items                                                          */
  /* ------------------------------------------------------------------------ */

  const attentionItems = useMemo(() => {
    return verifications
      .filter((verification) => {
        const status = getVerificationStatus(verification);

        return ['partial', 'unverified', 'failed'].includes(status);
      })
      .slice(0, 5);
  }, [verifications]);


  const recentVerifications = useMemo(() => {
    return [...verifications]
      .sort((a, b) => {
        const dateA = new Date(
          a.verified_at ||
          a.updated_at ||
          a.created_at ||
          0
        ).getTime();

        const dateB = new Date(
          b.verified_at ||
          b.updated_at ||
          b.created_at ||
          0
        ).getTime();

        return dateB - dateA;
      })
      .slice(0, 6);
  }, [verifications]);


  /* ------------------------------------------------------------------------ */
  /* Loading                                                                  */
  /* ------------------------------------------------------------------------ */

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center space-y-4">
          <div className="relative w-16 h-16 mx-auto">
            <div className="absolute inset-0 border-4 border-accent-middle/20 rounded-full" />

            <div className="absolute inset-0 border-4 border-accent-middle border-t-transparent rounded-full animate-spin" />

            <Shield className="absolute inset-0 m-auto w-6 h-6 text-accent-middle" />
          </div>

          <div>
            <p className="font-medium">
              Loading ACI
            </p>

            <p className="text-sm text-dark-muted mt-1">
              Loading verification and evidence data...
            </p>
          </div>
        </div>
      </div>
    );
  }


  /* ------------------------------------------------------------------------ */
  /* Render                                                                   */
  /* ------------------------------------------------------------------------ */

  return (
    <div className="min-w-0 space-y-6 animate-slide-up sm:space-y-8">

      {/* ------------------------------------------------------------------ */}
      {/* Header                                                             */}
      {/* ------------------------------------------------------------------ */}

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">

        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-accent-start/10 border border-accent-middle/10">
              <Shield className="w-7 h-7 text-accent-middle" />
            </div>

            <div>
              <h1 className="text-2xl font-bold gradient-text sm:text-3xl">
                ACI Dashboard
              </h1>

              <p className="text-dark-muted text-sm mt-1">
                Did the PR actually deliver the requirement?
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3 text-xs text-dark-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-verified animate-pulse" />

            Monitoring

            <span>•</span>

            Updated {formatTime(lastUpdated)}
          </div>
        </div>


        <div className="flex flex-wrap items-center gap-2 sm:gap-3">

          {repositories.length > 0 && (
            <div className="hidden md:flex items-center gap-2 px-3 py-2 rounded-xl bg-dark-card border border-dark-border">
              <Database className="w-4 h-4 text-dark-muted" />

              <span className="text-sm">
                {repositories.length}{' '}
                {repositories.length === 1
                  ? 'repository'
                  : 'repositories'}
              </span>
            </div>
          )}

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-dark-card border border-dark-border hover:border-accent-middle/40 hover:bg-dark-hover transition-colors disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}

            <span className="text-sm">
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </span>
          </button>
        </div>
      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Main decision banner                                               */}
      {/* ------------------------------------------------------------------ */}

      <div className="relative min-w-0 overflow-hidden rounded-2xl border border-accent-middle/20 bg-accent-start/5 p-4 sm:p-6">

        <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-accent-middle/5 blur-3xl" />

        <div className="relative flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">

          <div className="flex min-w-0 items-start gap-3 sm:gap-4">

            <div className="p-3 rounded-xl bg-accent-middle/10">
              <Target className="w-6 h-6 text-accent-middle" />
            </div>

            <div>
              <p className="text-xs uppercase tracking-wider text-accent-middle font-semibold">
                Delivery Verification
              </p>

              <h2 className="mt-1 text-lg font-semibold sm:text-xl">
                ACI checks what was requested against what was delivered.
              </h2>

              <p className="text-sm text-dark-muted mt-2 max-w-2xl">
                Requirements are connected to pull requests, criteria,
                verification results, and evidence so your team can see
                whether work is actually complete — not simply whether
                the code passed review.
              </p>
            </div>
          </div>

          <button
            onClick={() => navigate('/verifications')}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-middle/10 px-4 py-2.5 text-accent-middle transition-colors hover:bg-accent-middle/20 sm:w-auto sm:whitespace-nowrap"
          >
            Review deliveries

            <ArrowRight className="w-4 h-4" />
          </button>

        </div>
      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Verification overview                                               */}
      {/* ------------------------------------------------------------------ */}

      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">
              Verification Overview
            </h2>

            <p className="text-sm text-dark-muted mt-1">
              Current delivery health across your repositories.
            </p>
          </div>
        </div>


        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">

          <StatsCard
            title="Total Verifications"
            value={stats.total}
            icon={Activity}
            color="text-accent-middle"
            onClick={() => navigate('/verifications')}
          />

          <StatsCard
            title="Verified"
            value={stats.verified}
            icon={CheckCircle}
            color="text-verified"
            onClick={() =>
              navigate('/verifications?status=verified')
            }
          />

          <StatsCard
            title="Needs Attention"
            value={stats.partial + stats.unverified}
            icon={AlertTriangle}
            color="text-partial"
            onClick={() =>
              navigate('/verifications?status=partial')
            }
          />

          <StatsCard
            title="Pending"
            value={stats.pending}
            icon={Clock}
            color="text-pending"
            onClick={() =>
              navigate('/verifications?status=pending')
            }
          />

        </div>
      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Delivery health                                                     */}
      {/* ------------------------------------------------------------------ */}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        <div className="card min-w-0 p-4 sm:p-5 lg:col-span-2">

          <div className="flex items-center justify-between mb-5">

            <div>
              <h2 className="font-semibold">
                Delivery Health
              </h2>

              <p className="text-xs text-dark-muted mt-1">
                Verification outcomes from the current dataset.
              </p>
            </div>

            <div className="p-2 rounded-lg bg-accent-start/10">
              <BarChart3 className="w-4 h-4 text-accent-middle" />
            </div>

          </div>


          <div className="space-y-5">

            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-dark-muted">
                  Verified delivery
                </span>

                <span className="font-semibold">
                  {stats.passRate}%
                </span>
              </div>

              <div className="h-2 rounded-full bg-dark-border overflow-hidden">
                <div
                  className="h-full bg-verified rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(stats.passRate, 100)}%`,
                  }}
                />
              </div>
            </div>


            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

              <div className="rounded-xl bg-dark-hover/50 border border-dark-border p-3">
                <p className="text-xs text-dark-muted">
                  Verified
                </p>

                <p className="text-xl font-bold mt-1">
                  {stats.verified}
                </p>
              </div>

              <div className="rounded-xl bg-dark-hover/50 border border-dark-border p-3">
                <p className="text-xs text-dark-muted">
                  Partial
                </p>

                <p className="text-xl font-bold mt-1">
                  {stats.partial}
                </p>
              </div>

              <div className="rounded-xl bg-dark-hover/50 border border-dark-border p-3">
                <p className="text-xs text-dark-muted">
                  Unverified
                </p>

                <p className="text-xl font-bold mt-1">
                  {stats.unverified}
                </p>
              </div>

              <div className="rounded-xl bg-dark-hover/50 border border-dark-border p-3">
                <p className="text-xs text-dark-muted">
                  Pending
                </p>

                <p className="text-xl font-bold mt-1">
                  {stats.pending}
                </p>
              </div>

            </div>

          </div>
        </div>


        {/* Workspace stats */}

        <div className="card min-w-0 p-4 sm:p-5">

          <div className="flex items-center gap-2 mb-5">
            <Zap className="w-4 h-4 text-accent-middle" />

            <h2 className="font-semibold">
              Workspace
            </h2>
          </div>


          <div className="space-y-4">

            <button
              onClick={() => navigate('/repositories')}
              className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-dark-hover transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <Database className="w-4 h-4 text-accent-middle" />

                <span className="text-sm">
                  Repositories
                </span>
              </div>

              <span className="font-semibold">
                {stats.repositories}
              </span>
            </button>


            <button
              onClick={() => navigate('/pull-requests')}
              className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-dark-hover transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <GitPullRequest className="w-4 h-4 text-accent-middle" />

                <span className="text-sm">
                  Pull Requests
                </span>
              </div>

              <span className="font-semibold">
                {stats.pullRequests}
              </span>
            </button>


            <button
              onClick={() => navigate('/requirements')}
              className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-dark-hover transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <FileCode className="w-4 h-4 text-accent-middle" />

                <span className="text-sm">
                  Requirements
                </span>
              </div>

              <span className="font-semibold">
                {stats.requirements}
              </span>
            </button>


            <button
              onClick={() => navigate('/evidence')}
              className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-dark-hover transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <FileCheck2 className="w-4 h-4 text-accent-middle" />

                <span className="text-sm">
                  Evidence
                </span>
              </div>

              <span className="font-semibold">
                {recentEvidence.length}
              </span>
            </button>

          </div>
        </div>

      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Needs attention                                                     */}
      {/* ------------------------------------------------------------------ */}

      <div className="card overflow-hidden">

        <div className="p-5 border-b border-dark-border">

          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">

              <div className="p-2 rounded-lg bg-partial/10">
                <AlertTriangle className="w-4 h-4 text-partial" />
              </div>

              <div>
                <h2 className="font-semibold">
                  Needs Attention
                </h2>

                <p className="text-xs text-dark-muted mt-1">
                  Deliveries that should be reviewed before approval.
                </p>
              </div>

            </div>

            <button
              onClick={() => navigate('/verifications')}
              className="text-xs text-accent-middle hover:text-accent-end"
            >
              View all →
            </button>

          </div>

        </div>


        {attentionItems.length === 0 ? (

          <div className="p-8 text-center">

            <div className="w-12 h-12 mx-auto rounded-full bg-verified/10 flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-verified" />
            </div>

            <p className="font-medium mt-3">
              Nothing needs attention
            </p>

            <p className="text-sm text-dark-muted mt-1">
              No partial or unverified deliveries were found.
            </p>

          </div>

        ) : (

          <div className="divide-y divide-dark-border">

            {attentionItems.map((verification) => {

              const status = getVerificationStatus(
                verification
              );

              const StatusIcon = getStatusIcon(status);

              const requirement =
                verification.requirement || {};

              return (
                <button
                  key={verification.id}
                  onClick={() =>
                    navigate(
                      `/verifications/${verification.id}`
                    )
                  }
                  className="w-full text-left p-4 hover:bg-dark-hover transition-colors"
                >

                  <div className="flex items-start gap-3">

                    <StatusIcon
                      className={clsx(
                        'w-5 h-5 mt-0.5 shrink-0',
                        getStatusClasses(status)
                      )}
                    />

                    <div className="min-w-0 flex-1">

                      <div className="flex flex-wrap items-center gap-2">

                        <span className="text-sm font-semibold">
                          {requirement.external_id ||
                            'Requirement'}
                        </span>

                        <StatusBadge
                          status={status}
                          size="sm"
                        />

                      </div>

                      <p className="text-sm mt-1">
                        {truncate(
                          requirement.title ||
                            verification.summary ||
                            'Verification requires review.',
                          100
                        )}
                      </p>

                      <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-dark-muted">

                        {verification.pull_request && (
                          <span className="flex items-center gap-1">
                            <GitPullRequest className="w-3 h-3" />

                            PR #
                            {verification.pull_request.number}
                          </span>
                        )}

                        {verification.confidence !== null &&
                          verification.confidence !==
                            undefined && (
                            <span>
                              Confidence:{' '}
                              {Math.round(
                                safeNumber(
                                  verification.confidence
                                ) * 100
                              )}
                              %
                            </span>
                          )}

                      </div>

                    </div>

                    <ArrowRight className="w-4 h-4 text-dark-muted shrink-0 mt-1" />

                  </div>

                </button>
              );
            })}

          </div>

        )}

      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Recent verifications                                                */}
      {/* ------------------------------------------------------------------ */}

      <div className="card overflow-hidden">

        <div className="p-5 border-b border-dark-border">

          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">

              <Activity className="w-5 h-5 text-accent-middle" />

              <div>
                <h2 className="font-semibold">
                  Recent Delivery Checks
                </h2>

                <p className="text-xs text-dark-muted mt-1">
                  Latest requirement-to-PR verification results.
                </p>
              </div>

            </div>

            <button
              onClick={() => navigate('/verifications')}
              className="text-sm text-accent-middle hover:text-accent-end"
            >
              View all →
            </button>

          </div>

        </div>


        {recentVerifications.length === 0 ? (

          <div className="p-10 text-center">

            <div className="w-14 h-14 mx-auto rounded-2xl bg-accent-start/10 flex items-center justify-center">
              <Target className="w-7 h-7 text-accent-middle" />
            </div>

            <p className="font-medium mt-4">
              No delivery checks yet
            </p>

            <p className="text-sm text-dark-muted mt-1 max-w-md mx-auto">
              Open a GitHub pull request containing a Jira
              requirement key and ACI will begin building the
              requirement-to-evidence chain.
            </p>

          </div>

        ) : (

          <div className="divide-y divide-dark-border">

            {recentVerifications.map((verification) => {

              const status =
                getVerificationStatus(verification);

              const StatusIcon =
                getStatusIcon(status);

              const requirement =
                verification.requirement || {};

              const pullRequest =
                verification.pull_request || {};

              return (
                <button
                  key={verification.id}
                  onClick={() =>
                    navigate(
                      `/verifications/${verification.id}`
                    )
                  }
                  className="w-full text-left p-4 hover:bg-dark-hover transition-colors group"
                >

                  <div className="flex items-center gap-4">

                    <div className="shrink-0">
                      <StatusIcon
                        className={clsx(
                          'w-5 h-5',
                          getStatusClasses(status)
                        )}
                      />
                    </div>


                    <div className="min-w-0 flex-1">

                      <div className="flex items-center gap-2 flex-wrap">

                        <span className="font-semibold text-sm group-hover:text-accent-middle transition-colors">
                          {requirement.external_id ||
                            'Requirement'}
                        </span>

                        <StatusBadge
                          status={status}
                          size="sm"
                        />

                      </div>

                      <p className="text-sm text-dark-muted mt-1 truncate">
                        {requirement.title ||
                          verification.summary ||
                          'No summary available'}
                      </p>

                      {pullRequest.number && (
                        <div className="flex items-center gap-1 mt-1 text-xs text-dark-muted">
                          <GitBranch className="w-3 h-3" />

                          PR #{pullRequest.number}

                          {pullRequest.repository && (
                            <>
                              <span>·</span>

                              <span>
                                {pullRequest.repository}
                              </span>
                            </>
                          )}
                        </div>
                      )}

                    </div>


                    <div className="hidden md:flex items-center gap-5 text-xs text-dark-muted">

                      {verification.confidence !==
                        null &&
                        verification.confidence !==
                          undefined && (
                          <div className="text-right">
                            <p className="text-dark-muted">
                              Confidence
                            </p>

                            <p className="font-semibold text-dark-text mt-1">
                              {Math.round(
                                safeNumber(
                                  verification.confidence
                                ) * 100
                              )}
                              %
                            </p>
                          </div>
                        )}


                      {verification.verified_at && (
                        <div className="text-right">
                          <p className="text-dark-muted">
                            Checked
                          </p>

                          <p className="font-semibold text-dark-text mt-1">
                            {formatDate(
                              verification.verified_at
                            )}
                          </p>
                        </div>
                      )}

                      <ArrowRight className="w-4 h-4 group-hover:text-accent-middle transition-colors" />

                    </div>

                  </div>

                </button>
              );
            })}

          </div>

        )}

      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Pull requests + evidence                                            */}
      {/* ------------------------------------------------------------------ */}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        {/* Pull requests */}

        <div className="card overflow-hidden">

          <div className="p-5 border-b border-dark-border">

            <div className="flex items-center justify-between">

              <div className="flex items-center gap-3">

                <GitPullRequest className="w-5 h-5 text-accent-middle" />

                <div>
                  <h2 className="font-semibold">
                    Recent Pull Requests
                  </h2>

                  <p className="text-xs text-dark-muted mt-1">
                    Code changes entering the verification pipeline.
                  </p>
                </div>

              </div>

              <button
                onClick={() => navigate('/pull-requests')}
                className="text-xs text-accent-middle hover:text-accent-end"
              >
                View all →
              </button>

            </div>

          </div>


          {recentPRs.length === 0 ? (

            <div className="p-8 text-center text-sm text-dark-muted">
              No pull requests found.
            </div>

          ) : (

            <div className="divide-y divide-dark-border">

              {recentPRs.slice(0, 6).map((pr) => (

                <button
                  key={pr.id}
                  onClick={() =>
                    navigate(
                      `/pull-requests/${pr.id}`
                    )
                  }
                  className="w-full text-left p-4 hover:bg-dark-hover transition-colors"
                >

                  <div className="flex items-start gap-3">

                    <div className="p-2 rounded-lg bg-accent-start/10 shrink-0">
                      <GitBranch className="w-4 h-4 text-accent-middle" />
                    </div>

                    <div className="min-w-0 flex-1">

                      <p className="text-sm font-medium truncate">
                        #{pr.number}{' '}
                        {pr.title ||
                          'Untitled pull request'}
                      </p>

                      <p className="text-xs text-dark-muted mt-1">
                        {pr.author || 'Unknown author'}
                      </p>

                      <div className="flex items-center gap-2 mt-2">

                        <StatusBadge
                          status={
                            pr.state === 'open'
                              ? 'pending'
                              : pr.state || 'verified'
                          }
                          size="sm"
                        />

                        <span className="text-xs text-dark-muted">
                          {formatDate(
                            pr.updated_at ||
                              pr.created_at
                          )}
                        </span>

                      </div>

                    </div>

                  </div>

                </button>

              ))}

            </div>

          )}

        </div>


        {/* Evidence */}

        <div className="card overflow-hidden">

          <div className="p-5 border-b border-dark-border">

            <div className="flex items-center justify-between">

              <div className="flex items-center gap-3">

                <FileCheck2 className="w-5 h-5 text-accent-middle" />

                <div>
                  <h2 className="font-semibold">
                    Recent Evidence
                  </h2>

                  <p className="text-xs text-dark-muted mt-1">
                    The proof behind ACI's decisions.
                  </p>
                </div>

              </div>

              <button
                onClick={() => navigate('/evidence')}
                className="text-xs text-accent-middle hover:text-accent-end"
              >
                View all →
              </button>

            </div>

          </div>


          {recentEvidence.length === 0 ? (

            <div className="p-8 text-center">

              <Sparkles className="w-7 h-7 mx-auto text-dark-muted/50" />

              <p className="text-sm text-dark-muted mt-3">
                No evidence collected yet.
              </p>

            </div>

          ) : (

            <div className="divide-y divide-dark-border">

              {recentEvidence.slice(0, 6).map(
                (evidence, index) => (

                  <div
                    key={
                      evidence.id ||
                      `${evidence.commit_sha}-${index}`
                    }
                    className="p-4 hover:bg-dark-hover transition-colors"
                  >

                    <div className="flex items-start gap-3">

                      <div className="p-2 rounded-lg bg-accent-start/10 shrink-0">
                        <FileCheck2 className="w-4 h-4 text-accent-middle" />
                      </div>

                      <div className="min-w-0 flex-1">

                        <p className="text-sm font-medium truncate">
                          {evidence.description ||
                            'Evidence item'}
                        </p>

                        <div className="flex flex-wrap items-center gap-2 mt-2">

                          <StatusBadge
                            status={
                              evidence.status ||
                              'valid'
                            }
                            size="sm"
                          />

                          {evidence.evidence_type && (
                            <span className="text-xs uppercase text-dark-muted">
                              {evidence.evidence_type}
                            </span>
                          )}

                          {evidence.commit_sha && (
                            <span className="text-xs font-mono text-dark-muted">
                              {evidence.commit_sha.substring(
                                0,
                                7
                              )}
                            </span>
                          )}

                          {evidence.changed_file && (
                            <span className="text-xs text-dark-muted truncate max-w-[180px]">
                              {evidence.changed_file}
                            </span>
                          )}

                        </div>

                      </div>

                    </div>

                  </div>

                )
              )}

            </div>

          )}

        </div>

      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Product explanation                                                 */}
      {/* ------------------------------------------------------------------ */}

      <div className="min-w-0 rounded-2xl border border-dark-border bg-dark-card/60 p-4 sm:p-6">

        <div className="flex flex-col md:flex-row md:items-center gap-5">

          <div className="p-3 rounded-xl bg-accent-start/10 shrink-0">
            <Sparkles className="w-6 h-6 text-accent-middle" />
          </div>

          <div className="flex-1">

            <p className="text-xs uppercase tracking-wider text-accent-middle font-semibold">
              ACI Principle
            </p>

            <h3 className="text-lg font-semibold mt-1">
              Don't just review the code. Verify the delivery.
            </h3>

            <p className="text-sm text-dark-muted mt-2 max-w-3xl">
              ACI connects the requirement, pull request,
              criteria, verification result, and supporting
              evidence into one traceable delivery record.
            </p>

          </div>

          <button
            onClick={() => navigate('/requirements')}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-dark-border px-4 py-2.5 transition-colors hover:border-accent-middle/40 sm:w-auto sm:whitespace-nowrap"
          >
            Explore requirements

            <ArrowRight className="w-4 h-4" />
          </button>

        </div>

      </div>


      {/* ------------------------------------------------------------------ */}
      {/* Footer                                                              */}
      {/* ------------------------------------------------------------------ */}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-dark-muted/60 border-t border-dark-border pt-6">

        <div className="flex items-center gap-2">

          <Shield className="w-3.5 h-3.5" />

          <span>
            ACI v1.0 · Automated Compliance Intelligence
          </span>

        </div>


        <div className="flex items-center gap-4">

          <span>
            Last updated {formatTime(lastUpdated)}
          </span>

          <span className="flex items-center gap-1.5">

            <span className="w-1.5 h-1.5 rounded-full bg-verified animate-pulse" />

            Online

          </span>

        </div>

      </div>

    </div>
  );
};


export default Dashboard;