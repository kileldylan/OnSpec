import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, Circle, FileSearch, FileText, Sparkles } from 'lucide-react';
import { aciApi } from '../api/aci';
import StatusBadge from './StatusBadge';

const formatEvidenceLabel = (evidence) => {
  if (!evidence) return 'Evidence';

  const role = evidence.metadata?.evidence_role;
  const kind = role === 'documentation'
    ? 'Documentation'
    : role === 'test'
      ? 'Test'
      : evidence.evidence_type?.toUpperCase() || 'Evidence';
  const filename = evidence.metadata?.filename || evidence.changed_file?.filename;
  const context = evidence.metadata?.context || evidence.metadata?.name || evidence.description;

  if (filename) return `${kind}: ${filename}`;
  if (context) return `${kind}: ${context}`;
  return `${kind} evidence`;
};

export const VerificationDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [requestState, setRequestState] = useState({
    id: null,
    verification: null,
    loading: true,
    error: null,
  });
  const isCurrentRequest = requestState.id === id;
  const verification = isCurrentRequest ? requestState.verification : null;
  const loading = !isCurrentRequest || requestState.loading;
  const error = isCurrentRequest ? requestState.error : null;

  useEffect(() => {
    let active = true;
    aciApi.getVerification(id)
      .then((response) => {
        if (active) {
          setRequestState({
            id,
            verification: response.data,
            loading: false,
            error: null,
          });
        }
      })
      .catch((requestError) => {
        console.error('Unable to load verification:', requestError);
        if (active) {
          setRequestState({
            id,
            verification: null,
            loading: false,
            error: requestError.message,
          });
        }
      });

    return () => {
      active = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-accent-middle border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-dark-muted">Loading verification...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-unverified/10 border border-unverified/20 text-unverified px-4 py-3 rounded-xl">
        Error: {error}
      </div>
    );
  }

  if (!verification) {
    return (
      <div className="text-center py-12 text-dark-muted">
        <p className="text-lg">Verification not found</p>
      </div>
    );
  }

  const criteria = verification.criteria_evaluations || [];
  const satisfiedCount = criteria.filter((criterion) => criterion.status === 'satisfied').length;

  return (
    <div className="min-w-0 space-y-6 animate-slide-up">
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center sm:gap-4">
        <div>
          <h1 className="text-xl font-bold sm:text-2xl">Verification #{verification.id}</h1>
          <p className="text-dark-muted mt-1">
            {verification.requirement?.title || 'No title'}
          </p>
        </div>
        <StatusBadge status={verification.status} size="lg" />
      </div>

      <div className="card min-w-0 p-4 sm:p-6">
        <h2 className="text-lg font-semibold mb-4">Decision</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm text-dark-muted">Requirement</p>
            <p className="font-medium">{verification.requirement?.external_id || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-dark-muted">Pull Request</p>
            <p className="font-medium">#{verification.pull_request?.number || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-dark-muted">Confidence</p>
            <p className="font-medium">{verification.confidence != null ? `${Math.round(verification.confidence * 100)}%` : 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-dark-muted">Progress</p>
            <p className="font-medium">{criteria.length > 0 ? `${satisfiedCount}/${criteria.length} satisfied` : 'N/A'}</p>
          </div>
        </div>

        {verification.summary && (
          <div className="mt-4 p-4 bg-dark-hover rounded-xl border border-dark-border/60">
            <div className="flex items-center gap-2 text-sm text-dark-muted mb-2">
              <Sparkles className="w-4 h-4 text-accent-middle" />
              Summary
            </div>
            <p>{verification.summary}</p>
          </div>
        )}
      </div>

      <div className="card min-w-0 p-4 sm:p-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold">Acceptance Criteria</h2>
          {criteria.length > 0 && (
            <span className="text-sm text-dark-muted">{satisfiedCount}/{criteria.length} complete</span>
          )}
        </div>

        {criteria.length === 0 ? (
          <div className="text-sm text-dark-muted">No acceptance criteria were found for this ticket.</div>
        ) : (
          <div className="space-y-3">
            {criteria.map((criterion, index) => {
              const status = (criterion.status || 'missing').toLowerCase();
              const evidenceItems = Array.isArray(criterion.evidence) ? criterion.evidence : [];
              const evidenceCount = criterion.evidence_count ?? evidenceItems.length;
              const primaryEvidence = evidenceItems[0];
              const isComplete = status === 'satisfied';

              return (
                <div
                  key={criterion.id || index}
                  className="rounded-xl border border-dark-border/60 bg-dark-hover/80 p-4"
                >
                  <div className="flex flex-col xl:flex-row xl:items-start gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="mt-0.5">
                        {isComplete ? (
                          <CheckCircle2 className="w-5 h-5 text-verified" />
                        ) : (
                          <Circle className="w-5 h-5 text-dark-muted" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-sm text-dark-muted">Criterion {index + 1}</span>
                          <StatusBadge status={status} size="sm" />
                        </div>

                        <p className="font-medium break-words">{criterion.criterion_text || 'Untitled criterion'}</p>

                        {criterion.summary && (
                          <p className="text-sm text-dark-muted mt-2">{criterion.summary}</p>
                        )}
                      </div>
                    </div>

                    {evidenceCount > 0 && (
                      <div className="w-full rounded-lg border border-dark-border/60 bg-dark-bg/60 p-3 xl:w-[42%]">
                        <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wide text-dark-muted">
                          <FileText className="w-3.5 h-3.5" />
                          Primary evidence
                        </div>
                        {primaryEvidence ? (
                          <>
                            <div className="break-all text-sm text-dark-text">
                              {primaryEvidence.metadata?.source_url ? (
                                <a
                                  href={primaryEvidence.metadata.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-accent-middle hover:underline"
                                >
                                  {formatEvidenceLabel(primaryEvidence)}
                                  {primaryEvidence.metadata.line_start && (
                                    <span className="text-dark-muted">
                                      {' '}(L{primaryEvidence.metadata.line_start}
                                      {primaryEvidence.metadata.line_end &&
                                        primaryEvidence.metadata.line_end !== primaryEvidence.metadata.line_start &&
                                        `-L${primaryEvidence.metadata.line_end}`}
                                      )
                                    </span>
                                  )}
                                </a>
                              ) : (
                                formatEvidenceLabel(primaryEvidence)
                              )}
                            </div>
                            {primaryEvidence.metadata?.snippet && (
                              <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded bg-dark-bg p-2 text-xs font-mono text-dark-muted">
                                {primaryEvidence.metadata.snippet}
                              </pre>
                            )}
                          </>
                        ) : (
                          <p className="text-sm text-dark-muted">
                            {evidenceCount} supporting evidence {evidenceCount === 1 ? 'item' : 'items'} recorded.
                          </p>
                        )}
                        <button
                          className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent-middle hover:text-accent-end"
                          onClick={() => navigate(
                            `/verifications/${id}/criteria/${criterion.criterion}/evidence`
                          )}
                          type="button"
                        >
                          <FileSearch className="h-4 w-4" />
                          View all {evidenceCount} evidence {evidenceCount === 1 ? 'item' : 'items'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default VerificationDetail;
