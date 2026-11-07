import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Clock3,
  Download,
  FileText,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { aciApi } from '../api/aci';

const STATUS_CONFIG = {
  verified: { label: 'Verified', color: '#22c55e' },
  partial: { label: 'Partial', color: '#f59e0b' },
  unverified: { label: 'Unverified', color: '#ef4444' },
  failed: { label: 'Failed', color: '#dc2626' },
  stale: { label: 'Stale', color: '#a855f7' },
  pending: { label: 'Pending', color: '#3b82f6' },
};
const RANGE_DAYS = { '7d': 7, '30d': 30, '90d': 90 };
const chartTooltipStyle = {
  backgroundColor: '#14141e',
  borderColor: '#2a2a3a',
  color: '#e2e2f0',
};

const responseItems = (response) => {
  const payload = response?.data;
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
};

const verificationStatus = (verification) => {
  const status = (verification?.status || 'pending').toLowerCase();
  return STATUS_CONFIG[status] ? status : 'pending';
};

const verificationDate = (verification) =>
  verification.created_at || verification.verified_at || null;

const formatDate = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

const escapeCsv = (value) => {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
};

const downloadReport = (verifications, repositories, rangeLabel) => {
  const headers = [
    'Verification ID',
    'Created at',
    'Verified at',
    'Repository',
    'Requirement ID',
    'Requirement title',
    'Pull request',
    'Status',
    'Confidence',
    'Evidence count',
    'Summary',
  ];
  const repositoryById = new Map(repositories.map((repository) => [
    String(repository.id),
    repository.full_name || repository.name,
  ]));
  const rows = verifications.map((verification) => [
    verification.id,
    verificationDate(verification),
    verification.verified_at,
    repositoryById.get(String(verification.requirement?.repository)) || '',
    verification.requirement?.external_id || verification.requirement?.id,
    verification.requirement?.title,
    verification.pull_request?.number
      ? `#${verification.pull_request.number}`
      : '',
    verification.status,
    verification.confidence,
    verification.evidence_count ?? verification.evidence_ids?.length ?? 0,
    verification.summary,
  ]);
  const csv = [headers, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `requora-verification-report-${rangeLabel}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

const Analytics = () => {
  const [timeRange, setTimeRange] = useState('30d');
  const [repositoryFilter, setRepositoryFilter] = useState('all');
  const [repositories, setRepositories] = useState([]);
  const [verifications, setVerifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(async () => {
    const [repositoryResponse, verificationResponse] = await Promise.all([
      aciApi.getRepositories(),
      aciApi.getVerifications({ ordering: '-created_at' }),
    ]);
    return { repositoryResponse, verificationResponse };
  }, []);

  const applyData = useCallback((data) => {
    setRepositories(data.repositories);
    setVerifications(data.verifications);
    setLastUpdated(new Date());
  }, []);

  const getLoadError = (error) => {
    console.error('Unable to load analytics data:', error);
    return error.response?.data?.detail || 'Analytics could not be loaded. Check your connection and try again.';
  };

  useEffect(() => {
    let active = true;
    fetchData()
      .then(({ repositoryResponse, verificationResponse }) => {
        if (active) {
          applyData({
            repositories: responseItems(repositoryResponse),
            verifications: responseItems(verificationResponse),
          });
        }
      })
      .catch((error) => {
        if (active) setLoadError(getLoadError(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [applyData, fetchData]);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);

    try {
      const { repositoryResponse, verificationResponse } = await fetchData();
      applyData({
        repositories: responseItems(repositoryResponse),
        verifications: responseItems(verificationResponse),
      });
      return true;
    } catch (error) {
      setLoadError(getLoadError(error));
      return false;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [applyData, fetchData]);

  const selectedRepository = repositories.find(
    (repository) => String(repository.id) === repositoryFilter
  );
  const rangeDays = RANGE_DAYS[timeRange];
  const { currentVerifications, previousVerifications, trendData, statusData, repositoryData } = useMemo(() => {
    const now = new Date();
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - rangeDays + 1);
    const previousStart = new Date(start);
    previousStart.setDate(previousStart.getDate() - rangeDays);

    const repositoryById = new Map(repositories.map((repository) => [
      String(repository.id),
      repository,
    ]));
    const matchesRepository = (verification) =>
      repositoryFilter === 'all' ||
      String(verification.requirement?.repository) === repositoryFilter ||
      String(verification.pull_request?.repository) === repositoryFilter;
    const current = [];
    const previous = [];

    verifications.forEach((verification) => {
      if (!matchesRepository(verification)) return;
      const createdAt = new Date(verificationDate(verification));
      if (Number.isNaN(createdAt.getTime())) return;
      if (createdAt >= start && createdAt <= now) current.push(verification);
      else if (createdAt >= previousStart && createdAt < start) previous.push(verification);
    });

    const bucketDates = [];
    const byBucket = new Map();
    for (let offset = 0; offset < rangeDays; offset += 1) {
      const date = new Date(start);
      date.setDate(start.getDate() + offset);
      const key = date.toLocaleDateString();
      if (!byBucket.has(key)) {
        const bucket = {
          date: date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
          verified: 0,
          partial: 0,
          unverified: 0,
          failed: 0,
          stale: 0,
          pending: 0,
        };
        byBucket.set(key, bucket);
        bucketDates.push(bucket);
      }
    }

    const statusCounts = Object.keys(STATUS_CONFIG).reduce((counts, status) => {
      counts[status] = 0;
      return counts;
    }, {});
    current.forEach((verification) => {
      const status = verificationStatus(verification);
      statusCounts[status] += 1;
      const date = new Date(verificationDate(verification)).toLocaleDateString();
      const bucket = byBucket.get(date);
      if (bucket) bucket[status] += 1;
    });

    const perRepository = new Map();
    current.forEach((verification) => {
      const id = String(
        verification.requirement?.repository ??
        verification.pull_request?.repository ??
        ''
      );
      if (!id) return;
      const repository = repositoryById.get(id);
      const item = perRepository.get(id) || {
        name: repository?.full_name || repository?.name || `Repository ${id}`,
        total: 0,
        verified: 0,
      };
      item.total += 1;
      if (verificationStatus(verification) === 'verified') item.verified += 1;
      perRepository.set(id, item);
    });

    return {
      currentVerifications: current,
      previousVerifications: previous,
      trendData: bucketDates,
      statusData: Object.entries(statusCounts).map(([status, value]) => ({
        name: STATUS_CONFIG[status].label,
        status,
        value,
        color: STATUS_CONFIG[status].color,
      })).filter((item) => item.value > 0),
      repositoryData: [...perRepository.values()]
        .map((item) => ({
          ...item,
          passRate: item.total ? Math.round((item.verified / item.total) * 100) : 0,
        }))
        .sort((a, b) => b.total - a.total)
        .slice(0, 8),
    };
  }, [rangeDays, repositories, repositoryFilter, verifications]);

  const metrics = useMemo(() => {
    const total = currentVerifications.length;
    const verified = currentVerifications.filter(
      (verification) => verificationStatus(verification) === 'verified'
    ).length;
    const attention = currentVerifications.filter((verification) =>
      ['partial', 'unverified', 'failed', 'stale'].includes(verificationStatus(verification))
    ).length;
    const evidence = currentVerifications.reduce(
      (count, verification) =>
        count + Number(verification.evidence_count ?? verification.evidence_ids?.length ?? 0),
      0
    );
    const previousTotal = previousVerifications.length;
    const change = previousTotal
      ? Math.round(((total - previousTotal) / previousTotal) * 100)
      : null;
    return {
      total,
      verified,
      attention,
      evidence,
      verifiedRate: total ? Math.round((verified / total) * 100) : 0,
      change,
    };
  }, [currentVerifications, previousVerifications]);

  const handleRefresh = async () => {
    setLoadError('');
    if (await loadData(true)) toast.success('Analytics refreshed');
  };

  const handleRetry = () => {
    setLoadError('');
    setLoading(true);
    loadData();
  };

  const handleExport = () => {
    downloadReport(
      currentVerifications,
      repositories,
      timeRange,
    );
    toast.success(`Exported ${currentVerifications.length} verification records.`);
  };

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center" role="status">
        <RefreshCw className="h-8 w-8 animate-spin text-accent-middle" />
        <span className="sr-only">Loading analytics...</span>
      </div>
    );
  }

  if (loadError) {
    return (
      <section className="card mx-auto max-w-xl p-8 text-center" role="alert">
        <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-partial" />
        <h1 className="text-xl font-semibold">Analytics unavailable</h1>
        <p className="mt-2 text-sm text-dark-muted">{loadError}</p>
        <button
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-accent-middle px-4 py-2 text-sm font-semibold text-white"
          onClick={handleRetry}
          type="button"
        >
          <RefreshCw className="h-4 w-4" /> Try again
        </button>
      </section>
    );
  }

  return (
    <div className="min-w-0 space-y-6 animate-slide-up">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-accent-middle" />
            <h1 className="text-2xl font-bold sm:text-3xl">Analytics &amp; reports</h1>
          </div>
          <p className="mt-1 text-sm text-dark-muted">
            Delivery outcomes and evidence-backed verification activity.
            {lastUpdated && ` Updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            aria-label="Filter by date range"
            className="rounded-xl border border-dark-border bg-dark-card px-3 py-2 text-sm"
            onChange={(event) => setTimeRange(event.target.value)}
            value={timeRange}
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
          <select
            aria-label="Filter by repository"
            className="max-w-56 rounded-xl border border-dark-border bg-dark-card px-3 py-2 text-sm"
            onChange={(event) => setRepositoryFilter(event.target.value)}
            value={repositoryFilter}
          >
            <option value="all">All repositories</option>
            {repositories.map((repository) => (
              <option key={repository.id} value={repository.id}>
                {repository.full_name}
              </option>
            ))}
          </select>
          <button
            className="inline-flex items-center gap-2 rounded-xl border border-dark-border bg-dark-card px-3 py-2 text-sm transition hover:border-accent-middle/40 disabled:opacity-60"
            disabled={refreshing}
            onClick={handleRefresh}
            type="button"
          >
            <RefreshCw className={`h-4 w-4${refreshing ? ' animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-xl bg-accent-middle px-3 py-2 text-sm font-semibold text-white transition hover:bg-accent-end"
            onClick={handleExport}
            type="button"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>
      </header>

      <section aria-label="Verification metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={FileText} label="Verifications" value={metrics.total} detail={metrics.change === null ? 'In selected period' : `${metrics.change >= 0 ? '+' : ''}${metrics.change}% vs previous period`} />
        <MetricCard icon={ShieldCheck} label="Verified delivery" value={`${metrics.verifiedRate}%`} detail={`${metrics.verified} verified in selected period`} />
        <MetricCard icon={AlertTriangle} label="Needs attention" value={metrics.attention} detail="Partial, stale, failed or unverified" />
        <MetricCard icon={CheckCircle} label="Evidence linked" value={metrics.evidence} detail="Across selected verifications" />
      </section>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <section className="card min-w-0 p-4 sm:p-6">
          <h2 className="mb-1 text-lg font-semibold">Verification activity</h2>
          <p className="mb-4 text-sm text-dark-muted">Daily verification outcomes in the selected period</p>
          <div className="h-72">
            {currentVerifications.length === 0 ? (
              <EmptyChartMessage />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 8, right: 12, left: -18, bottom: 4 }}>
                  <CartesianGrid stroke="#2a2a3a" strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke="#8888aa" tick={{ fontSize: 11 }} minTickGap={20} />
                  <YAxis allowDecimals={false} stroke="#8888aa" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Legend />
                  {Object.entries(STATUS_CONFIG).map(([status, config]) => (
                    <Line
                      connectNulls
                      dataKey={status}
                      dot={false}
                      key={status}
                      name={config.label}
                      stroke={config.color}
                      strokeWidth={2}
                      type="monotone"
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="card min-w-0 p-4 sm:p-6">
          <h2 className="mb-1 text-lg font-semibold">Outcome distribution</h2>
          <p className="mb-4 text-sm text-dark-muted">Current status of verifications in this report</p>
          <div className="h-72">
            {statusData.length === 0 ? (
              <EmptyChartMessage />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    innerRadius={55}
                    nameKey="name"
                    outerRadius={95}
                    paddingAngle={2}
                  >
                    {statusData.map((item) => (
                      <Cell fill={item.color} key={item.status} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>

      <section className="card min-w-0 p-4 sm:p-6">
        <h2 className="mb-1 text-lg font-semibold">Repository performance</h2>
        <p className="mb-4 text-sm text-dark-muted">Verification volume and verified delivery rate</p>
        {repositoryData.length === 0 ? (
          <EmptyChartMessage />
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={repositoryData} layout="vertical" margin={{ top: 4, right: 20, left: 16, bottom: 4 }}>
                <CartesianGrid stroke="#2a2a3a" strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} stroke="#8888aa" />
                <YAxis type="category" dataKey="name" width={130} stroke="#8888aa" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Legend />
                <Bar dataKey="total" fill="#6366f1" name="Verifications" radius={[0, 4, 4, 0]} />
                <Bar dataKey="verified" fill="#22c55e" name="Verified" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-2 border-b border-dark-border p-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <h2 className="text-lg font-semibold">Verification report</h2>
            <p className="text-sm text-dark-muted">
              {currentVerifications.length} records
              {selectedRepository ? ` · ${selectedRepository.full_name}` : ' · all repositories'}
              {' · '}{timeRange.replace('d', ' days')}
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 self-start rounded-lg border border-dark-border px-3 py-2 text-sm hover:border-accent-middle/40 sm:self-auto"
            onClick={handleExport}
            type="button"
          >
            <Download className="h-4 w-4" /> Download report
          </button>
        </div>
        {currentVerifications.length === 0 ? (
          <p className="p-8 text-center text-sm text-dark-muted">No verification records match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-dark-hover/50 text-xs uppercase text-dark-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">Requirement</th>
                  <th className="px-5 py-3 font-medium">Repository</th>
                  <th className="px-5 py-3 font-medium">Pull request</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Evidence</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border">
                {[...currentVerifications]
                  .sort((a, b) => new Date(verificationDate(b)) - new Date(verificationDate(a)))
                  .slice(0, 12)
                  .map((verification) => {
                    const status = verificationStatus(verification);
                    const repository = repositories.find(
                      (item) => String(item.id) === String(verification.requirement?.repository)
                    );
                    return (
                      <tr className="transition hover:bg-dark-hover/40" key={verification.id}>
                        <td className="max-w-xs px-5 py-3">
                          <Link className="font-medium text-accent-middle hover:underline" to={`/verifications/${verification.id}`}>
                            {verification.requirement?.external_id || `Verification #${verification.id}`}
                          </Link>
                          <p className="truncate text-xs text-dark-muted">{verification.requirement?.title || 'Untitled requirement'}</p>
                        </td>
                        <td className="px-5 py-3 text-dark-muted">{repository?.full_name || '—'}</td>
                        <td className="px-5 py-3">
                          {verification.pull_request?.number
                            ? <Link className="text-accent-middle hover:underline" to={`/pull-requests/${verification.pull_request.id}`}>#{verification.pull_request.number}</Link>
                            : '—'}
                        </td>
                        <td className="px-5 py-3">
                          <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: STATUS_CONFIG[status].color }} />
                            {STATUS_CONFIG[status].label}
                          </span>
                        </td>
                        <td className="px-5 py-3">{verification.evidence_count ?? verification.evidence_ids?.length ?? 0}</td>
                        <td className="whitespace-nowrap px-5 py-3 text-dark-muted">{formatDate(verificationDate(verification))}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
        {currentVerifications.length > 12 && (
          <div className="border-t border-dark-border px-5 py-3 text-right">
            <Link className="text-sm font-medium text-accent-middle hover:underline" to="/verifications">View all verification history</Link>
          </div>
        )}
      </section>
    </div>
  );
};

const MetricCard = ({ icon: Icon, label, value, detail }) => (
  <article className="card flex min-w-0 items-start gap-4 p-4 sm:p-5">
    <div className="rounded-xl bg-accent-middle/10 p-3 text-accent-middle">
      <Icon className="h-5 w-5" />
    </div>
    <div className="min-w-0">
      <p className="text-sm text-dark-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      <p className="mt-1 truncate text-xs text-dark-muted">{detail}</p>
    </div>
  </article>
);

const EmptyChartMessage = () => (
  <div className="flex h-full flex-col items-center justify-center text-center text-sm text-dark-muted">
    <Clock3 className="mb-2 h-6 w-6 opacity-60" />
    No verification activity for this selection.
  </div>
);

export default Analytics;
