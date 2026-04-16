import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import { API_BASE } from '../utils/constants';
import { parseForm } from '../utils/formatters';

export default function LeaguePage() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const [leagues, setLeagues] = useState([]);
  const [table, setTable] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch league list
  useEffect(() => {
    if (leagueId) return;
    const fetchLeagues = async () => {
      try {
        const res = await axios.get(`${API_BASE}/leagues`);
        setLeagues(res.data || []);
      } catch { setLeagues([]); }
    };
    fetchLeagues();
  }, [leagueId]);

  // Fetch league table + stats
  useEffect(() => {
    if (!leagueId) return;
    const fetchData = async () => {
      setLoading(true);
      try {
        const [tableRes, statsRes] = await Promise.all([
          axios.get(`${API_BASE}/leagues/${leagueId}/table`),
          axios.get(`${API_BASE}/leagues/${leagueId}/stats`),
        ]);
        setTable(tableRes.data || []);
        setStats(statsRes.data);
      } catch {
        setTable([]);
        setStats(null);
      }
      setLoading(false);
    };
    fetchData();
  }, [leagueId]);

  // League list view
  if (!leagueId) {
    return (
      <div className="space-y-4">
        <DataTable
          columns={[
            { key: 'name', label: 'League' },
            { key: 'season', label: 'Season' },
            { key: 'tier', label: 'Tier', align: 'right' },
            { key: 'matches_played', label: 'Played', align: 'right' },
            { key: 'total_matches', label: 'Total', align: 'right' },
          ]}
          data={leagues}
          onRowClick={(row) => navigate(`/leagues/${row.id}`)}
        />
      </div>
    );
  }

  // League detail view
  return (
    <div className="space-y-4">
      <button onClick={() => navigate('/leagues')} className="text-xs text-text-muted hover:text-accent-cyan">
        &larr; Back to Leagues
      </button>

      {stats && (
        <>
          <h2 className="text-lg font-ui font-bold text-text-primary">{stats.league_name} — {stats.season}</h2>
          <div className="grid grid-cols-6 gap-3">
            <StatCard label="Matches" value={stats.completed_matches} accent="cyan" />
            <StatCard label="Avg Goals" value={stats.avg_goals_per_match} accent="green" />
            <StatCard label="BTTS %" value={stats.btts_rate ? `${stats.btts_rate}%` : '—'} accent="amber" />
            <StatCard label="Over 2.5 %" value={stats.over25_rate ? `${stats.over25_rate}%` : '—'} accent="purple" />
            <StatCard label="Home Win %" value={stats.home_win_rate ? `${stats.home_win_rate}%` : '—'} accent="cyan" />
            <StatCard label="Away Win %" value={stats.away_win_rate ? `${stats.away_win_rate}%` : '—'} accent="amber" />
          </div>
        </>
      )}

      {loading ? (
        <div className="text-text-muted font-data text-sm py-8 text-center">Loading standings...</div>
      ) : (
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Standings</h3>
          <DataTable
            columns={[
              {
                key: 'pos', label: '#', align: 'right',
                render: (_, row) => {
                  const idx = table.indexOf(row) + 1;
                  return <span className="font-bold">{idx}</span>;
                },
              },
              {
                key: 'team_name', label: 'Team',
                render: (v) => <span className="font-semibold">{v}</span>,
              },
              { key: 'played', label: 'P', align: 'right' },
              { key: 'wins', label: 'W', align: 'right' },
              { key: 'draws', label: 'D', align: 'right' },
              { key: 'losses', label: 'L', align: 'right' },
              { key: 'goals_for', label: 'GF', align: 'right' },
              { key: 'goals_against', label: 'GA', align: 'right' },
              { key: 'goal_difference', label: 'GD', align: 'right',
                render: (v) => <span className={v > 0 ? 'text-accent-green' : v < 0 ? 'text-accent-red' : ''}>{v > 0 ? `+${v}` : v}</span>,
              },
              { key: 'points', label: 'Pts', align: 'right',
                render: (v) => <span className="font-bold text-accent-cyan">{v}</span>,
              },
              {
                key: 'form', label: 'Form',
                render: (v) => (
                  <span className="font-data text-xs">
                    {parseForm(v).map((f, i) => (
                      <span key={i} className={f.colour}>{f.letter}</span>
                    ))}
                  </span>
                ),
              },
            ]}
            data={table}
            onRowClick={(row) => navigate(`/teams/${row.team_id}`)}
          />
        </div>
      )}
    </div>
  );
}
