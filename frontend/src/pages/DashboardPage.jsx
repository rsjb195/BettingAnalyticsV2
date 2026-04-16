import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import EdgeIndicator from '../components/shared/EdgeIndicator';
import { API_BASE } from '../utils/constants';
import { formatOdds, formatPct, formatDate } from '../utils/formatters';

export default function DashboardPage() {
  const navigate = useNavigate();
  const [upcoming, setUpcoming] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [upcomingRes, perfRes] = await Promise.all([
          axios.get(`${API_BASE}/matches/upcoming?days=7`).catch(() => ({ data: { fixtures: [] } })),
          axios.get(`${API_BASE}/performance`).catch(() => ({ data: null })),
        ]);
        setUpcoming(upcomingRes.data.fixtures || []);
        setPerformance(perfRes.data);
      } catch {
        // Handled by individual catch blocks above
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const valueOpps = upcoming.filter(
    (f) => f.model && Math.max(f.model.home_edge || 0, f.model.draw_edge || 0, f.model.away_edge || 0) > 0.02
  );

  const fixtureColumns = [
    { key: 'match_date', label: 'Date', render: (v) => formatDate(v) },
    { key: 'home_team_name', label: 'Home' },
    { key: 'away_team_name', label: 'Away' },
    {
      key: 'odds_home', label: 'Mkt H', align: 'right',
      render: (v) => <span className="font-data tabular-nums">{formatOdds(v)}</span>,
    },
    {
      key: 'odds_draw', label: 'Mkt D', align: 'right',
      render: (v) => <span className="font-data tabular-nums">{formatOdds(v)}</span>,
    },
    {
      key: 'odds_away', label: 'Mkt A', align: 'right',
      render: (v) => <span className="font-data tabular-nums">{formatOdds(v)}</span>,
    },
    {
      key: 'model', label: 'Our H%', align: 'right',
      render: (v) => <span className="font-data tabular-nums">{v ? formatPct(v.our_home_prob) : '—'}</span>,
    },
    {
      key: '_edge', label: 'Best Edge', align: 'right',
      render: (_, row) => {
        if (!row.model) return '—';
        const best = Math.max(row.model.home_edge || 0, row.model.draw_edge || 0, row.model.away_edge || 0);
        return <EdgeIndicator edge={best} showLabel />;
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Upcoming Fixtures"
          value={upcoming.length}
          subValue="Next 7 days"
          accent="cyan"
        />
        <StatCard
          label="Value Opportunities"
          value={valueOpps.length}
          subValue=">2% edge"
          accent="green"
        />
        <StatCard
          label="Model Accuracy"
          value={performance ? `${performance.win_rate.toFixed(1)}%` : '—'}
          subValue="Rolling selections"
          accent="amber"
        />
        <StatCard
          label="Net P&L"
          value={performance ? `$${performance.net_pnl.toFixed(2)}` : '—'}
          subValue={performance ? `ROI: ${performance.roi_pct}%` : ''}
          accent={performance && performance.net_pnl >= 0 ? 'green' : 'red'}
        />
      </div>

      {/* Fixture table */}
      <div className="stat-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-data font-semibold text-text-primary uppercase tracking-wider">
            Upcoming Fixtures
          </h2>
          <button
            onClick={() => navigate('/slate')}
            className="btn-primary text-xs"
          >
            View Saturday Slate
          </button>
        </div>

        {loading ? (
          <div className="text-text-muted font-data text-sm py-8 text-center">Loading fixtures...</div>
        ) : (
          <DataTable
            columns={fixtureColumns}
            data={upcoming}
            onRowClick={(row) => navigate(`/teams/${row.home_team_id}`)}
          />
        )}
      </div>

      {/* Bottom two columns */}
      <div className="grid grid-cols-2 gap-4">
        {/* Recent results */}
        <div className="stat-card">
          <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-3">
            Recent P&L
          </h3>
          {performance && performance.recent && performance.recent.length > 0 ? (
            <div className="space-y-2">
              {performance.recent.slice(0, 5).map((a) => (
                <div key={a.id} className="flex items-center justify-between py-1 border-b border-terminal-border/30">
                  <span className="text-xs font-data text-text-secondary">{a.slate_date}</span>
                  <span className="text-xs font-data tabular-nums text-text-secondary">
                    {a.actual_odds.toFixed(1)}x
                  </span>
                  <span className={`text-xs font-data font-bold ${a.result === 'win' ? 'text-accent-green' : a.result === 'loss' ? 'text-accent-red' : 'text-accent-amber'}`}>
                    {a.result.toUpperCase()}
                  </span>
                  <span className="text-xs font-data tabular-nums text-text-secondary">
                    ${(a.actual_return || 0).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-text-muted text-xs font-data py-4">No accumulator history yet</div>
          )}
        </div>

        {/* Referee alerts */}
        <div className="stat-card">
          <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-3">
            Referee Alerts
          </h3>
          {upcoming.filter((f) => f.referee_avg_cards && f.referee_avg_cards > 4).length > 0 ? (
            <div className="space-y-2">
              {upcoming.filter((f) => f.referee_avg_cards && f.referee_avg_cards > 4).slice(0, 5).map((f, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-terminal-border/30">
                  <span className="text-xs font-data text-text-secondary">
                    {f.home_team_name} v {f.away_team_name}
                  </span>
                  <span className="text-xs font-data text-accent-red">
                    {f.referee_name} ({f.referee_avg_cards?.toFixed(1)} cards/match)
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-text-muted text-xs font-data py-4">No high-card referees in upcoming fixtures</div>
          )}
        </div>
      </div>
    </div>
  );
}
