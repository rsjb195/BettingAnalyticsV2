import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import TrendLine from '../components/shared/TrendLine';
import useTeamStats from '../hooks/useTeamStats';
import { API_BASE } from '../utils/constants';
import { COLOURS } from '../utils/colours';
import { formatPct, formatOdds, parseForm } from '../utils/formatters';

export default function TeamsPage() {
  const { teamId } = useParams();
  const navigate = useNavigate();
  const [teams, setTeams] = useState([]);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  const { stats, form, matches, players, loading } = useTeamStats(teamId ? parseInt(teamId) : null);

  // Fetch team list when no specific team selected
  useEffect(() => {
    if (teamId) return;
    const fetchTeams = async () => {
      try {
        const res = await axios.get(`${API_BASE}/teams`, { params: { per_page: 100, search: search || undefined } });
        setTeams(res.data || []);
      } catch { setTeams([]); }
    };
    fetchTeams();
  }, [teamId, search]);

  // Team list view
  if (!teamId) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="Search teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-terminal-card border border-terminal-border px-3 py-2 text-sm font-data text-text-primary w-64 focus:border-accent-cyan focus:outline-none"
          />
        </div>
        <DataTable
          columns={[
            { key: 'name', label: 'Team' },
            { key: 'clean_name', label: 'Clean Name' },
            { key: 'season', label: 'Season' },
            { key: 'stadium', label: 'Stadium' },
          ]}
          data={teams}
          onRowClick={(row) => navigate(`/teams/${row.id}`)}
        />
      </div>
    );
  }

  // Team detail view
  const tabs = ['overview', 'attack', 'defence', 'form', 'h2h', 'squad'];
  const m = stats?.metrics || {};

  // Form chart data
  const formChartData = form?.form?.map((f, i) => ({
    name: f.date,
    goals: f.goals_for || 0,
    result: f.result,
    fill: f.result === 'W' ? COLOURS.green : f.result === 'D' ? COLOURS.amber : COLOURS.red,
  })) || [];

  // xG trend data
  const xgTrendData = form?.form?.map((f) => ({
    name: f.date,
    xg: f.xg_for,
    goals: f.goals_for,
  })) || [];

  // PPG rolling data
  const ppgData = form?.form?.map((f, i, arr) => {
    const window = arr.slice(Math.max(0, i - 4), i + 1);
    const avg = window.reduce((s, x) => s + (x.points || 0), 0) / window.length;
    return { name: f.date, value: avg };
  }) || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate('/teams')} className="text-xs text-text-muted hover:text-accent-cyan mb-1 block">
            &larr; Back to Teams
          </button>
          <h2 className="text-xl font-ui font-bold text-text-primary">
            {stats?.team_name || 'Loading...'}
          </h2>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs font-data text-text-secondary">{stats?.season}</span>
            {m.form_last5 && (
              <span className="font-data text-sm">
                {parseForm(m.form_last5).map((f, i) => (
                  <span key={i} className={f.colour}>{f.letter}</span>
                ))}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-6 border-b border-terminal-border">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 text-sm font-data uppercase tracking-wider ${
              activeTab === tab ? 'tab-active' : 'tab-inactive'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-text-muted font-data text-sm py-8 text-center">Loading team data...</div>
      ) : (
        <>
          {/* Overview tab */}
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div className="grid grid-cols-6 gap-3">
                <StatCard label="PPG" value={m.ppg_season?.toFixed(2)} accent="cyan" />
                <StatCard label="xG For" value={m.xg_for_avg?.toFixed(2)} accent="green" />
                <StatCard label="xG Against" value={m.xg_against_avg?.toFixed(2)} accent="red" />
                <StatCard label="Clean Sheet %" value={formatPct(m.clean_sheet_rate)} accent="green" />
                <StatCard label="BTTS %" value={formatPct(m.btts_rate)} accent="amber" />
                <StatCard label="Over 2.5 %" value={formatPct(m.over25_rate)} accent="purple" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="stat-card">
                  <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Form (Last 20)</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={formChartData}>
                      <XAxis dataKey="name" tick={false} axisLine={false} />
                      <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ backgroundColor: COLOURS.elevated, border: `1px solid ${COLOURS.border}`, borderRadius: 0, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                      <Bar dataKey="goals" fill={COLOURS.cyan} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="stat-card">
                  <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">xG vs Goals</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={xgTrendData}>
                      <XAxis dataKey="name" tick={false} axisLine={false} />
                      <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ backgroundColor: COLOURS.elevated, border: `1px solid ${COLOURS.border}`, borderRadius: 0, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                      <Line type="monotone" dataKey="xg" stroke={COLOURS.cyan} strokeWidth={1.5} dot={false} name="xG" />
                      <Line type="monotone" dataKey="goals" stroke={COLOURS.green} strokeWidth={1.5} dot={false} name="Goals" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Attack tab */}
          {activeTab === 'attack' && (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3">
                <StatCard label="Goals/Match" value={m.goals_scored_avg?.toFixed(2)} accent="green" />
                <StatCard label="Shots/Match" value={m.shots_for_avg?.toFixed(1)} accent="cyan" />
                <StatCard label="Conversion %" value={formatPct(m.conversion_rate)} accent="amber" />
                <StatCard label="xG Overperf" value={m.xg_overperformance?.toFixed(2)} accent={m.xg_overperformance > 0 ? 'green' : 'red'} />
              </div>
            </div>
          )}

          {/* Defence tab */}
          {activeTab === 'defence' && (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3">
                <StatCard label="Conceded/Match" value={m.goals_conceded_avg?.toFixed(2)} accent="red" />
                <StatCard label="Clean Sheet %" value={formatPct(m.clean_sheet_rate)} accent="green" />
                <StatCard label="CS Home %" value={formatPct(m.clean_sheet_home)} accent="green" />
                <StatCard label="CS Away %" value={formatPct(m.clean_sheet_away)} accent="amber" />
              </div>
            </div>
          )}

          {/* Form tab */}
          {activeTab === 'form' && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <StatCard label="PPG Last 5" value={m.ppg_last5?.toFixed(2)} accent="cyan" />
                <StatCard label="PPG Last 10" value={m.ppg_last10?.toFixed(2)} accent="cyan" />
                <StatCard label="Momentum" value={m.momentum_score?.toFixed(0)} subValue={m.momentum_direction} accent={m.momentum_direction === 'rising' ? 'green' : m.momentum_direction === 'falling' ? 'red' : 'amber'} />
              </div>
              <div className="stat-card">
                <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Rolling PPG</h3>
                <TrendLine data={ppgData} height={150} showAxis />
              </div>
              <DataTable
                columns={[
                  { key: 'date', label: 'Date' },
                  { key: 'opponent', label: 'Opponent' },
                  { key: 'venue', label: 'V' },
                  { key: 'goals_for', label: 'GF', align: 'right' },
                  { key: 'goals_against', label: 'GA', align: 'right' },
                  { key: 'result', label: 'Res', render: (v) => <span className={v === 'W' ? 'text-accent-green' : v === 'D' ? 'text-accent-amber' : 'text-accent-red'}>{v}</span> },
                  { key: 'xg_for', label: 'xG', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
                ]}
                data={matches}
              />
            </div>
          )}

          {/* H2H tab */}
          {activeTab === 'h2h' && (
            <div className="stat-card">
              <p className="text-text-muted font-data text-sm">Select an opponent from the fixture list to view head-to-head data.</p>
            </div>
          )}

          {/* Squad tab */}
          {activeTab === 'squad' && (
            <DataTable
              columns={[
                { key: 'name', label: 'Name' },
                { key: 'position', label: 'Pos' },
                { key: 'appearances', label: 'Apps', align: 'right' },
                { key: 'goals', label: 'Goals', align: 'right' },
                { key: 'assists', label: 'Assists', align: 'right' },
                { key: 'xg', label: 'xG', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
                { key: 'xa', label: 'xA', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
                { key: 'rating', label: 'Rating', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
              ]}
              data={players}
              onRowClick={(row) => navigate(`/players/${row.id}`)}
            />
          )}
        </>
      )}
    </div>
  );
}
