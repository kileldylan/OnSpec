import { clsx } from 'clsx';

export const StatsCard = ({ title, value, icon: Icon, trend, color, onClick }) => {
  return (
    <div 
      onClick={onClick}
      className={clsx(
        'card p-6 cursor-pointer transition-all duration-300',
        'hover:border-accent-middle/30 hover:shadow-lg hover:shadow-accent-start/5',
        'group'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-dark-muted text-sm font-medium">{title}</p>
          <p className="text-3xl font-bold text-dark-text">{value}</p>
          {trend && (
            <p className={clsx(
              'text-xs font-medium',
              trend > 0 ? 'text-verified' : 'text-unverified'
            )}>
              {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}% from last week
            </p>
          )}
        </div>
        {Icon && (
          <div className={clsx(
            'p-3 rounded-xl transition-all duration-300',
            'bg-gradient-to-br from-accent-start/10 to-accent-end/10',
            'group-hover:from-accent-start/20 group-hover:to-accent-end/20'
          )}>
            <Icon className={clsx(
              'w-6 h-6',
              color || 'text-accent-middle'
            )} />
          </div>
        )}
      </div>
    </div>
  );
};

export default StatsCard;