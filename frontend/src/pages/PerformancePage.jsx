import { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import { API_BASE } from '../utils/constants';
import { COLOURS } from '../utils/colours';
import { formatCurrency, formatDate } from '../utils/formatters';

export default function PerformancePage() {
  const [performance, setPerformance] = useState(null);
  const [accLog, setAccLog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [perfRes, logRes] = await Promise.all([
          axios.get(`${API_BASE}/performance`),
          axios.get(`${API_BASE}/accumulator/log?per_page=50`),
        ]);
        setPerformance(perfRes.data);
        setAccLog(logRes.data.accumulators || []);
      } catch {
        // handled
      }
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) {
    return <div className="text-text-muted font-data text-sm py-8 text-center">Loading performance data...</div>;
  }

  const p = performance || {};

  // P&L chart data
  const pnlChartData = accLog.filter((a) => a.result !== 'pending').map((a) => ({
    date: a.slate_date,
    pnl: (a.actual_return || 0) - a.stake,
    fill: (a.actual_return || 0) - a.stake >= 0 ? COLOURS.green : COLOURS.red,
  })).reverse();

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-6 gap-3">
        <StatCard label="Total Accumulators" value={p.total_accumulators || 0} accent="cyan" />
        <StatCard label="Wins" value={p.wins || 0} accent="green" />
        <StatCard label="Losses" value={p.losses || 0} accent="red" />
        <StatCard label="Win Rate" value={p.win_rate ? `${p.win_rate.toFixed(1)}%` : '—'} accent="amber" />
        <StatCard label="Total Staked" value={formatCurrency(p.total_staked)} accent="cyan" />
        <StatCard
          label="Net P&L"
          value={formatCurrency(p.net_pnl)}
          subValue={`ROI: ${p.roi_pct || 0}%`}
          accent={p.net_pnl >= 0 ? 'green' : 'red'}
        />
      </div>

      {/* P&L chart */}
      {pnlChartData.length > 0 && (
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">P&L by Accumulator</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={pnlChartData}>
              <XAxis dataKey="date" tick={{ fill: COLOURS.textMuted, fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: COLOURS.elevated, border: `1px solid ${COLOURS.border}`, borderRadius: 0, fontSize: 11, fontFamily: 'JetBrains Mono' }}
                formatter={(value) => [`$${value.toFixed(2)}`, 'P&L']}
              />
              <Bar dataKey="pnl">
                {pnlChartData.map((entry, i) => (
                  <Bar key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Accumulator log */}
      <div className="stat-card">
        <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Selection Log</h3>
        <DataTable
          columns={[
            { key: 'slate_date', label: 'Date', render: (v) => formatDate(v) },
            { key: 'legs', label: 'Legs', render: (v) => `${v?.length || 0} legs` },
            { key: 'actual_odds', label: 'Odds', align: 'right', render: (v) => v?.toFixed(1) },
            { key: 'stake', label: 'Stake', align: 'right', render: (v) => formatCurrency(v) },
            { key: 'potential_return', label: 'Pot. Return', align: 'right', render: (v) => formatCurrency(v) },
            {
              key: 'result', label: 'Result', align: 'right',
              render: (v) => (
                <span className={`font-bold ${v === 'win' ? 'text-accent-green' : v === 'loss' ? 'text-accent-red' : 'text-accent-amber'}`}>
                  {v?.toUpperCase()}
                </span>
              ),
            },
            { key: 'actual_return', label: 'Return', align: 'right', render: (v) => formatCurrency(v) },
          ]}
          data={accLog}
        />
      </div>
    </div>
  );
}
