import { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { ChevronDown, ChevronRight } from 'lucide-react';
import StatCard from '../components/shared/StatCard';
import { API_BASE } from '../utils/constants';
import { COLOURS } from '../utils/colours';
import { formatCurrency, formatDate, formatOdds } from '../utils/formatters';

function AccumulatorLog({ accumulators }) {
  const [expandedId, setExpandedId] = useState(null);

  if (!accumulators?.length) {
    return <div className="text-text-muted text-xs font-data py-4">No accumulators saved yet</div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="grid grid-cols-7 gap-2 px-2 py-1.5 border-b border-terminal-border text-[10px] font-data text-text-muted uppercase tracking-wider">
        <span>Date</span>
        <span>Legs</span>
        <span className="text-right">Odds</span>
        <span className="text-right">Stake</span>
        <span className="text-right">Pot. Return</span>
        <span className="text-right">Result</span>
        <span className="text-right">Return</span>
      </div>
      {accumulators.map((a) => (
        <div key={a.id}>
          <button
            onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
            className="w-full grid grid-cols-7 gap-2 px-2 py-2 border-b border-terminal-border/30 hover:bg-terminal-elevated/50 transition-colors text-xs font-data items-center"
          >
            <span className="flex items-center gap-1 text-text-secondary">
              {expandedId === a.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              {formatDate(a.slate_date)}
            </span>
            <span className="text-text-secondary">{a.legs?.length || 0} legs</span>
            <span className="text-right tabular-nums text-text-secondary">{a.actual_odds?.toFixed(1)}</span>
            <span className="text-right tabular-nums text-text-secondary">{formatCurrency(a.stake)}</span>
            <span className="text-right tabular-nums text-text-secondary">{formatCurrency(a.potential_return)}</span>
            <span className={`text-right font-bold ${a.result === 'win' ? 'text-accent-green' : a.result === 'loss' ? 'text-accent-red' : 'text-accent-amber'}`}>
              {a.result?.toUpperCase()}
            </span>
            <span className="text-right tabular-nums text-text-secondary">{formatCurrency(a.actual_return)}</span>
          </button>
          {expandedId === a.id && a.legs && (
            <div className="bg-terminal-elevated/30 border-b border-terminal-border/30 px-4 py-2 space-y-1.5">
              {a.legs.map((leg, i) => (
                <div key={i} className="flex items-center justify-between text-[11px] font-data pl-4 border-l-2 border-accent-cyan/30">
                  <span className="text-text-secondary">
                    {leg.home_team} v {leg.away_team}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="text-accent-cyan font-bold uppercase">{leg.selection}</span>
                    <span className="text-text-muted tabular-nums">@ {formatOdds(leg.odds)}</span>
                    <span className="text-text-muted tabular-nums">Prob: {leg.our_probability ? (leg.our_probability * 100).toFixed(1) + '%' : '—'}</span>
                    {leg.edge_pct != null && (
                      <span className={`tabular-nums ${leg.edge_pct > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                        Edge: {(leg.edge_pct * 100).toFixed(1)}%
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

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

      {/* Accumulator log with expandable legs */}
      <div className="stat-card">
        <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Selection Log</h3>
        <AccumulatorLog accumulators={accLog} />
      </div>
    </div>
  );
}
