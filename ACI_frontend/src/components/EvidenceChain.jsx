import React, { useState } from 'react';
import { 
  Code, 
  Beaker, 
  Cpu, 
  Rocket,
  ChevronDown,
  ChevronRight,
  GitCommit,
  File,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import { clsx } from 'clsx';
import StatusBadge from './StatusBadge';

const evidenceIcons = {
  code: Code,
  test: Beaker,
  ci: Cpu,
  runtime: Rocket,
};

const evidenceColors = {
  code: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  test: 'text-green-400 bg-green-400/10 border-green-400/20',
  ci: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  runtime: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
};

export const EvidenceChain = ({ evidence, onEvidenceClick }) => {
  const [expandedItems, setExpandedItems] = useState({});

  const toggleExpand = (id) => {
    setExpandedItems(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  if (!evidence || evidence.length === 0) {
    return (
      <div className="text-center py-8 text-dark-muted">
        <File className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No evidence found for this verification</p>
      </div>
    );
  }

  // Group evidence by type
  const grouped = evidence.reduce((acc, item) => {
    const type = item.evidence_type || 'code';
    if (!acc[type]) acc[type] = [];
    acc[type].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {/* Timeline */}
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-px bg-dark-border sm:left-6"></div>
        
        {evidence.map((item, index) => {
          const Icon = evidenceIcons[item.evidence_type] || File;
          const isExpanded = expandedItems[item.id];
          const isLast = index === evidence.length - 1;

          return (
            <div key={item.id || index} className="relative pb-6 pl-10 sm:pl-16">
              {/* Timeline dot */}
              <div className={clsx(
                'absolute left-4 mt-1.5 h-4 w-4 -translate-x-1/2 transform rounded-full border-2 sm:left-6',
                item.status === 'verified' || item.status === 'satisfied' 
                  ? 'bg-verified border-verified' 
                  : item.status === 'pending'
                  ? 'bg-pending border-pending animate-pulse'
                  : 'bg-unverified border-unverified'
              )}></div>

              {/* Evidence card */}
              <div 
                className={clsx(
                  'card min-w-0 p-3 cursor-pointer transition-all duration-300 sm:p-4',
                  'hover:border-accent-middle/20',
                  'group'
                )}
                onClick={() => toggleExpand(item.id)}
              >
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className={clsx(
                      'p-2 rounded-lg border flex-shrink-0',
                      evidenceColors[item.evidence_type] || 'text-dark-muted border-dark-border'
                    )}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex min-w-0 flex-wrap items-center gap-2 sm:gap-3">
                        <span className="min-w-0 break-words text-sm font-medium sm:truncate">
                          {item.description || 'Evidence item'}
                        </span>
                        <StatusBadge status={item.status} size="sm" />
                      </div>
                      {(item.metadata?.filename || item.filename) && (
                        <p className="text-xs text-dark-muted mt-0.5 font-mono truncate">
                          📁 {item.metadata?.filename || item.filename}
                        </p>
                      )}
                      {item.commit_sha && (
                        <p className="text-xs text-dark-muted mt-0.5 font-mono">
                          🔗 {item.commit_sha.substring(0, 8)}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-1 text-xs text-dark-muted">
                        {item.created_at && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(item.created_at).toLocaleString()}
                          </span>
                        )}
                        {item.evidence_type && (
                          <span className="capitalize">
                            {item.evidence_type}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button className="flex-shrink-0 p-1 text-dark-muted hover:text-dark-text transition-colors">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>
                </div>

                {/* Expanded content */}
                {isExpanded && item.metadata && Object.keys(item.metadata).length > 0 && (
                  <div className="mt-3 pt-3 border-t border-dark-border">
                    {item.metadata.snippet ? (
                      <>
                        <div className="mb-2 text-xs text-dark-muted">
                          {item.metadata.source_url ? (
                            <a
                              href={item.metadata.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-accent-middle hover:underline"
                            >
                              View {item.metadata.filename}
                              {item.metadata.line_start &&
                                ` (lines ${item.metadata.line_start}-${item.metadata.line_end})`}
                            </a>
                          ) : (
                            `${item.metadata.filename || 'Source'}${item.metadata.line_start ? ` (lines ${item.metadata.line_start}-${item.metadata.line_end})` : ''}`
                          )}
                        </div>
                        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-dark-bg p-2 text-xs font-mono text-dark-muted">
                          {item.metadata.snippet}
                        </pre>
                      </>
                    ) : (
                      <pre className="text-xs font-mono text-dark-muted overflow-x-auto p-2 bg-dark-bg rounded-lg">
                        {JSON.stringify(item.metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
        {Object.entries(grouped).map(([type, items]) => {
          const Icon = evidenceIcons[type] || File;
          const satisfied = items.filter(i => 
            i.status === 'verified' || i.status === 'satisfied'
          ).length;
          
          return (
            <div key={type} className="card p-3 text-center">
              <Icon className="w-4 h-4 mx-auto mb-1 text-accent-middle" />
              <div className="text-xs text-dark-muted capitalize">{type}</div>
              <div className="text-sm font-semibold">
                {satisfied}/{items.length}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default EvidenceChain;