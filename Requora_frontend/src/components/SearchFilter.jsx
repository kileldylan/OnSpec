import React, { useState } from 'react';
import { Search, Filter, X } from 'lucide-react';
import { clsx } from 'clsx';

export const SearchFilter = ({ 
  onSearch, 
  onFilter, 
  filters = [],
  placeholder = 'Search...',
  className,
}) => {
  const [query, setQuery] = useState('');
  const [activeFilters, setActiveFilters] = useState({});
  const [showFilters, setShowFilters] = useState(false);

  const handleSearch = (e) => {
    e.preventDefault();
    onSearch?.(query);
  };

  const handleFilterChange = (key, value) => {
    const newFilters = { ...activeFilters, [key]: value };
    if (!value) delete newFilters[key];
    setActiveFilters(newFilters);
    onFilter?.(newFilters);
  };

  const clearFilters = () => {
    setActiveFilters({});
    setQuery('');
    onSearch?.('');
    onFilter?.({});
  };

  return (
    <div className={clsx('space-y-3', className)}>
      <div className="flex items-center gap-3">
        <form onSubmit={handleSearch} className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              className="w-full pl-10 pr-4 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle transition-colors"
            />
          </div>
        </form>
        
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-xl border transition-colors',
            showFilters || Object.keys(activeFilters).length > 0
              ? 'border-accent-middle text-accent-middle'
              : 'border-dark-border text-dark-muted hover:border-accent-middle/30'
          )}
        >
          <Filter className="w-4 h-4" />
          {Object.keys(activeFilters).length > 0 && (
            <span className="w-5 h-5 rounded-full bg-accent-start text-white text-xs flex items-center justify-center">
              {Object.keys(activeFilters).length}
            </span>
          )}
        </button>

        {(query || Object.keys(activeFilters).length > 0) && (
          <button
            onClick={clearFilters}
            className="p-2 text-dark-muted hover:text-dark-text transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {showFilters && (
        <div className="card p-4 space-y-3 animate-slide-up">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Filters</h4>
            <button
              onClick={() => setShowFilters(false)}
              className="text-dark-muted hover:text-dark-text"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {filters.map((filter) => (
              <div key={filter.key}>
                <label className="text-sm text-dark-muted block mb-1">
                  {filter.label}
                </label>
                {filter.type === 'select' ? (
                  <select
                    value={activeFilters[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm"
                  >
                    <option value="">All</option>
                    {filter.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={filter.type || 'text'}
                    value={activeFilters[filter.key] || ''}
                    onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                    placeholder={filter.placeholder}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-xl focus:outline-none focus:border-accent-middle text-sm"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchFilter;