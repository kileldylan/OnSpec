import { clsx } from 'clsx';
import { CheckCircle, AlertTriangle, XCircle, Clock, AlertOctagon } from 'lucide-react';

const statusConfig = {
  verified: {
    color: 'text-verified bg-verified/10 border-verified/20',
    icon: CheckCircle,
    label: 'Verified',
  },
  satisfied: {
    color: 'text-verified bg-verified/10 border-verified/20',
    icon: CheckCircle,
    label: 'Satisfied',
  },
  partial: {
    color: 'text-partial bg-partial/10 border-partial/20',
    icon: AlertTriangle,
    label: 'Partial',
  },
  unverified: {
    color: 'text-unverified bg-unverified/10 border-unverified/20',
    icon: XCircle,
    label: 'Unverified',
  },
  pending: {
    color: 'text-pending bg-pending/10 border-pending/20',
    icon: Clock,
    label: 'Pending',
  },
  queued: {
    color: 'text-pending bg-pending/10 border-pending/20',
    icon: Clock,
    label: 'Queued',
  },
  running: {
    color: 'text-pending bg-pending/10 border-pending/20',
    icon: Clock,
    label: 'Running',
  },
  failed: {
    color: 'text-failed bg-failed/10 border-failed/20',
    icon: AlertOctagon,
    label: 'Failed',
  },
  missing: {
    color: 'text-unverified bg-unverified/10 border-unverified/20',
    icon: XCircle,
    label: 'Missing',
  },
};

export const StatusBadge = ({ status, size = 'md', showIcon = true, className }) => {
  const config = statusConfig[status?.toLowerCase()] || statusConfig.pending;
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-sm px-3 py-1 gap-1.5',
    lg: 'text-base px-4 py-1.5 gap-2',
  };

  return (
    <span className={clsx(
      'inline-flex items-center rounded-full border font-medium',
      sizeClasses[size],
      config.color,
      className
    )}>
      {showIcon && <Icon className={clsx('flex-shrink-0', {
        'w-3 h-3': size === 'sm',
        'w-4 h-4': size === 'md',
        'w-5 h-5': size === 'lg',
      })} />}
      <span>{config.label || status}</span>
    </span>
  );
};

export default StatusBadge;