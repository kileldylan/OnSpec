import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ExternalLink, FileSearch, Loader2 } from 'lucide-react';
import { aciApi } from '../api/aci';
import StatusBadge from './StatusBadge';

const evidenceLabel = (evidence) => {
  const filename = evidence.metadata?.filename || evidence.changed_file?.filename;
  const role = evidence.metadata?.evidence_role;
  const kind = role === 'implementation'
    ? 'Implementation'
    : role === 'test'
      ? 'Test'
      : role === 'documentation'
        ? 'Documentation'
        : evidence.evidence_type || 'Evidence';
  return filename ? `${kind} · ${filename}` : evidence.description || `${kind} evidence`;
};

const lineRange = (evidence) => {
  const start = evidence.metadata?.line_start;
  const end = evidence.metadata?.line_end;
  if (!start) return '';
  return end && end !== start ? `L${start}-L${end}` : `L${start}`;
};

const CriterionEvidenceDetail = () => {
  const { id, criterionId } = useParams();
  const navigate = useNavigate();
  const [requestState, setRequestState] = useState({
    key: '',
    detail: null,
    loading: true,
    error: '',
  });
  const requestKey = `${id}/${criterionId}`;
  const isCurrentRequest = requestState.key === requestKey;
  const detail = isCurrentRequest ? requestState.detail : null;
  const loading = !isCurrentRequest || requestState.loading;
  const error = isCurrentRequest ? requestState.error : '';

  useEffect(() => {
    let active = true;
    aciApi.getCriterionEvidence(id, criterionId)
      .then((response) => {
        if (active) {
          setRequestState({
            key: requestKey,
            detail: response.data,
            loading: false,
            error: '',
          });
        }
      })
      .catch((requestError) => {
        console.error('Unable to load criterion evidence:', requestError);
        if (active) {
          setRequestState({
            key: requestKey,
            detail: null,
            loading: false,
            error: requestError.response?.data?.detail ||
              'Unable to load the evidence for this criterion.',
          });
        }
      })

    return () => {
      active = false;
    };
  }, [criterionId, id, requestKey]);

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center gap-3 text-dark-muted" role="status">
        <Loader2 className="h-6 w-6 animate-spin text-accent-middle" />
        Loading criterion evidence...
      </div>
    );
  }

  if (error) {
    return (
      <section className="card mx-auto max-w-2xl p-6" role="alert">
        <p className="text-sm text-unverified">{error}</p>
        <button
          className="mt-4 inline-flex items-center gap-2 text-sm text-accent-middle hover:text-accent-end"
          onClick={() => navigate(`/verifications/${id}`)}
          type="button"
        >
          <ArrowLeft className="h-4 w-4" /> Back to verification
        </button>
      </section>
    );
  }

  const evidence = detail?.evidence || [];

  return (
    <main className="min-w-0 space-y-6 animate-slide-up">
      <button
        className="inline-flex items-center gap-2 text-sm text-dark-muted transition hover:text-accent-middle"
        onClick={() => navigate(`/verifications/${id}`)}
        type="button"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to verification
      </button>

      <header className="min-w-0">
        <div className="flex items-center gap-2 text-accent-middle">
          <FileSearch className="h-5 w-5" />
          <span className="text-xs font-semibold uppercase tracking-wide">
            Criterion evidence
          </span>
        </div>
        <h1 className="mt-2 break-words text-xl font-bold sm:text-2xl">
          {detail?.criterion?.text || 'Criterion'}
        </h1>
        <p className="mt-2 text-sm text-dark-muted">
          {detail?.evidence_count || 0} evidence {detail?.evidence_count === 1 ? 'item' : 'items'}.
          {' '}The strongest match is shown first; remaining entries are related line-level proof.
        </p>
      </header>

      {evidence.length === 0 ? (
        <section className="card p-8 text-center text-sm text-dark-muted">
          No evidence is linked to this criterion yet.
        </section>
      ) : (
        <section aria-label="All criterion evidence" className="space-y-3">
          {evidence.map((item, index) => (
            <article className="card min-w-0 p-4 sm:p-5" key={item.id}>
              <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-dark-border px-2.5 py-1 text-xs text-dark-muted">
                      {index === 0 ? 'Primary evidence' : 'Related line evidence'}
                    </span>
                    <StatusBadge status={item.status} size="sm" />
                    <span className="text-xs uppercase text-dark-muted">
                      {item.evidence_type}
                    </span>
                  </div>
                  <h2 className="break-all font-medium">{evidenceLabel(item)}</h2>
                  {item.description && (
                    <p className="mt-1 text-sm text-dark-muted">{item.description}</p>
                  )}
                  {item.metadata?.source_url && (
                    <a
                      className="mt-2 inline-flex items-center gap-1 text-sm text-accent-middle hover:underline"
                      href={item.metadata.source_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Open source {lineRange(item) && `(${lineRange(item)})`}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
                {item.commit_sha && (
                  <span className="shrink-0 font-mono text-xs text-dark-muted">
                    {item.commit_sha.slice(0, 8)}
                  </span>
                )}
              </div>
              {item.metadata?.snippet && (
                <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-dark-border bg-dark-bg p-3 text-xs leading-relaxed text-dark-muted">
                  {item.metadata.snippet}
                </pre>
              )}
            </article>
          ))}
        </section>
      )}
    </main>
  );
};

export default CriterionEvidenceDetail;
