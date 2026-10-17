import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { TrendingUp, Calendar, Filter } from 'lucide-react';
import { aciApi } from '../api/aci';

const COLORS = ['#22c55e', '#f59e0b', '#ef4444', '#3b82f6'];

export const Analytics = () => {
  const [timeRange, setTimeRange] = useState('7d');
  const [trendData, setTrendData] = useState([]);
  const [statusDistribution, setStatusDistribution] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, [timeRange]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const response = await aciApi.getVerifications({ 
        limit: 100,
        ordering: '-created_at',
      });
      
      const verifications = response.data.results || response.data || [];
      
      // Process data for charts
      const dates = {};
      const statusCounts = { verified: 0, partial: 0, unverified: 0, pending: 0 };
      
      verifications.forEach(v => {
        const date = new Date(v.created_at).toLocaleDateString();
        if (!dates[date]) dates[date] = { date, verified: 0, partial: 0, unverified: 0, pending: 0 };
        if (v.status) {
          dates[date][v.status] = (dates[date][v.status] || 0) + 1;
          statusCounts[v.status] = (statusCounts[v.status] || 0) + 1;
        }
      });
      
      setTrendData(Object.values(dates).slice(-7));
      setStatusDistribution([
        { name: 'Verified', value: statusCounts.verified || 0 },
        { name: 'Partial', value: statusCounts.partial || 0 },
        { name: 'Unverified', value: statusCounts.unverified || 0 },
        { name: 'Pending', value: statusCounts.pending || 0 },
      ]);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-accent-middle"></div>
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-6 animate-slide-up">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2 sm:text-2xl">
          <TrendingUp className="w-6 h-6 text-accent-middle" />
          Analytics
        </h2>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-2 bg-dark-card border border-dark-border rounded-xl text-sm focus:outline-none focus:border-accent-middle"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
          <button className="flex items-center gap-2 px-3 py-2 bg-dark-card border border-dark-border rounded-xl hover:border-accent-middle/30 transition-colors text-sm">
            <Filter className="w-4 h-4" />
            Filter
          </button>
        </div>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2 sm:gap-6">
        {/* Trend Chart */}
        <div className="card min-w-0 p-4 sm:p-6">
          <h3 className="text-lg font-semibold mb-4">Verification Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                <XAxis dataKey="date" stroke="#8888aa" />
                <YAxis stroke="#8888aa" />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#14141e', 
                    borderColor: '#2a2a3a',
                    color: '#e2e2f0'
                  }} 
                />
                <Legend />
                <Line type="monotone" dataKey="verified" stroke="#22c55e" />
                <Line type="monotone" dataKey="partial" stroke="#f59e0b" />
                <Line type="monotone" dataKey="unverified" stroke="#ef4444" />
                <Line type="monotone" dataKey="pending" stroke="#3b82f6" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Distribution Chart */}
        <div className="card min-w-0 p-4 sm:p-6">
          <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {statusDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#14141e', 
                    borderColor: '#2a2a3a',
                    color: '#e2e2f0'
                  }} 
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-verified">
            {statusDistribution.find(s => s.name === 'Verified')?.value || 0}
          </div>
          <div className="text-sm text-dark-muted">Verified</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-partial">
            {statusDistribution.find(s => s.name === 'Partial')?.value || 0}
          </div>
          <div className="text-sm text-dark-muted">Partial</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-unverified">
            {statusDistribution.find(s => s.name === 'Unverified')?.value || 0}
          </div>
          <div className="text-sm text-dark-muted">Unverified</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-pending">
            {statusDistribution.find(s => s.name === 'Pending')?.value || 0}
          </div>
          <div className="text-sm text-dark-muted">Pending</div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;