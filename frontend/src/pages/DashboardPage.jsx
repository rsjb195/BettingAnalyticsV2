import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight } from 'lucide-react';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import EdgeIndicator from '../components/shared/EdgeIndicator';
import { API_BASE } from '../utils/constants';
import { formatOdds, formatPct, formatDate } from '../utils/formatters';

function RecentPnL({ performance }) {
  const [expandedId, setExpandedId] = useState(null);

  return (
    <div className="stat-card">
      <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-3">
        Recent P&L
      </h3>
      {performance?.recent?.length > 0 ? (
        <div className="space-y-1">
          {performance.recent.slice(0, 5).map((a) => (
            <div key={a.id}>
              <button
                onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
                className="w-full flex items-center justify-between py-1.5 border-b border-terminal-border/30 hover:bg-terminal-elevated/50 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  {expandedId === a.id ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
                  <span className="text-xs font-data text-text-secondary">{a.slate_date}</span>
                  <span className="text-[10px] font-data text-text-muted">({a.legs?.length || 0} legs)</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-xs font-data tabular-nums text-text-secondary">
                    {a.actual_odds?.toFixed(1)}x
                  </span>
                  <span className={`text-xs font-data font-bold ${a.result === 'win' ? 'text-accent-green' : a.result === 'loss' ? 'text-accent-red' : 'text-accent-amber'}`}>
                    {a.result?.toUpperCase()}
                  </span>
                  <span className="text-xs font-data tabular-nums text-text-secondary">
                    ${(a.actual_return || 0).toFixed(2)}
                  </span>
                </span>
              </button>
              {expandedId === a.id && a.legs && (
                <div className="ml-5 py-1 space-y-1 border-l-2 border-terminal-border/40 pl-3 mb-2">
                  {a.legs.map((leg, i) => (
                    <div key={i} className="flex items-center justify-between text-[10px] font-data">
                      <span className="text-text-secondary">
                        {leg.home_team} v {leg.away_team}
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="text-accent-cyan font-bold uppercase">{leg.selection}</span>
                        <span className="text-text-muted tabular-nums">@ {leg.odds?.toFixed(2)}</span>
                        {leg.edge_pct != null && (
                          <span className={leg.edge_pct > 0 ? 'text-accent-green' : 'text-accent-red'}>
                            {(leg.edge_pct * 100).toFixed(1)}%
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
      ) : (
        <div className="text-text-muted text-xs font-data py-4">No accumulator history yet</div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [upcoming, setUpcoming] = useState([]);
  const [analysed, setAnalysed] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [upcomingRes, analysedRes, perfRes] = await Promise.all([
          axios.get(`${API_BASE}/matches/upcoming?days=7`).catch(() => ({ data: { fixtures: [] } })),
          axios.get(`${API_BASE}/matches/recent-analysed?limit=50`).catch(() => ({ data: { fixtures: [] } })),
          axios.get(`${API_BASE}/performance`).catch(() => ({ data: null })),
        ]);
        setUpcoming(upcomingRes.data.fixtures || []);
        setAnalysed(analysedRes.data.fixtures || []);
        setPerformance(perfRes.data);
      } catch {
        // Handled by individual catch blocks above
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Use upcoming if available, otherwise show recent analysed
  const displayFixtures = upcoming.length > 0 ? upcoming : analysed;
  const isShowingRecent = upcoming.length === 0 && analysed.length > 0;

  const valueOpps = displayFixtures.filter(
    (f) => f.model && Math.max(f.model.home_edge || 0, f.model.draw_edge || 0, f.model.away_edge || 0) > 0.02
  );

  const fixtureColumns = [
    { key: 'match_date', label: 'Date', render: (v) => formatDate(v) },
    { key: 'home_team_name', label: 'Home' },
    {
      key: '_score', label: 'Score', align: 'center',
      render: (_, row) => {
        if (row.home_goals != null && row.away_goals != null) {
          return (
            <span className="font-data tabular-nums font-bold text-text-primary">
              {row.home_goals} – {row.away_goals}
            </span>
          );
        }
        return <span className="text-text-muted">vs</span>;
      },
    },
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
          label={isShowingRecent ? "Analysed Matches" : "Upcoming Fixtures"}
          value={displayFixtures.length}
          subValue={isShowingRecent ? "With model outputs" : "Next 7 days"}
          accent="cyan"
        />
        <StatCard
          label="Value Opportunities"
          value={valueOpps.length}
          subValue=">2% edge"
          accent="green"
        />
        <StatCard
          label="Model Coverage"
          value={displayFixtures.filter((f) => f.model).length}
          subValue="Matches with predictions"
          accent="amber"
        />
        <StatCard
          label="Avg Confidence"
          value={
            displayFixtures.filter((f) => f.model).length > 0
              ? (displayFixtures.filter((f) => f.model).reduce((s, f) => s + (f.model.confidence || 0), 0) / displayFixtures.filter((f) => f.model).length).toFixed(1)
              : '—'
          }
          subValue="Model rating (1-10)"
          accent="purple"
        />
      </div>

      {/* Fixture table */}
      <div className="stat-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-data font-semibold text-text-primary uppercase tracking-wider">
            {isShowingRecent ? 'Recent Analysed Matches' : 'Upcoming Fixtures'}
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
            data={displayFixtures}
            onRowClick={(row) => navigate(`/matches/${row.id}`)}
          />
        )}
      </div>

      {/* Bottom two columns */}
      <div className="grid grid-cols-2 gap-4">
        {/* Recent results */}
        <RecentPnL performance={performance} />

        {/* Referee alerts */}
        <div className="stat-card">
          <h3 className="text-xs font-data font-semibold text-text-muted uppercase tracking-wider mb-3">
            Referee Alerts
          </h3>
          {displayFixtures.filter((f) => f.referee_avg_cards && f.referee_avg_cards > 4).length > 0 ? (
            <div className="space-y-2">
              {displayFixtures.filter((f) => f.referee_avg_cards && f.referee_avg_cards > 4).slice(0, 5).map((f, i) => (
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
