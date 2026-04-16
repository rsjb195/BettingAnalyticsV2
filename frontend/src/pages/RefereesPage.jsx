import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import useRefereeData from '../hooks/useRefereeData';
import { API_BASE } from '../utils/constants';
import { COLOURS } from '../utils/colours';

export default function RefereesPage() {
  const { refereeId } = useParams();
  const navigate = useNavigate();
  const [referees, setReferees] = useState([]);

  const { profile, matchLog, impact, loading } = useRefereeData(refereeId ? parseInt(refereeId) : null);

  useEffect(() => {
    if (refereeId) return;
    const fetchReferees = async () => {
      try {
        const res = await axios.get(`${API_BASE}/referees?min_matches=5`);
        setReferees(res.data || []);
      } catch { setReferees([]); }
    };
    fetchReferees();
  }, [refereeId]);

  // Referee list view
  if (!refereeId) {
    const columns = [
      { key: 'name', label: 'Name' },
      { key: 'total_matches', label: 'Matches', align: 'right' },
      {
        key: 'avg_cards_per_match', label: 'Avg Cards', align: 'right',
        render: (v) => {
          const colour = v > 5 ? 'text-accent-red' : v > 3.5 ? 'text-accent-amber' : 'text-accent-green';
          return <span className={`font-data ${colour}`}>{v?.toFixed(2) ?? '—'}</span>;
        },
      },
      { key: 'avg_yellows_per_match', label: 'Avg Yellows', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
      {
        key: 'home_bias_score', label: 'Home Bias', align: 'right',
        render: (v) => {
          if (!v) return '—';
          const colour = v > 1.15 ? 'text-accent-amber' : v < 0.85 ? 'text-accent-amber' : 'text-text-secondary';
          return <span className={`font-data ${colour}`}>{v.toFixed(3)}</span>;
        },
      },
      { key: 'penalties_per_match', label: 'Pens/Match', align: 'right', render: (v) => v?.toFixed(3) ?? '—' },
    ];

    return (
      <div className="space-y-4">
        <DataTable columns={columns} data={referees} onRowClick={(row) => navigate(`/referees/${row.id}`)} />
      </div>
    );
  }

  // Referee detail view
  if (loading) {
    return <div className="text-text-muted font-data text-sm py-8 text-center">Loading referee profile...</div>;
  }

  const disc = impact?.disciplinary || {};
  const bias = impact?.home_away_bias || {};
  const flow = impact?.game_flow || {};
  const pens = impact?.penalties || {};

  // Card distribution chart
  const cardDistData = disc.card_distribution ? [
    { range: '0-2', count: disc.card_distribution['0-2'] || 0 },
    { range: '3-4', count: disc.card_distribution['3-4'] || 0 },
    { range: '5-6', count: disc.card_distribution['5-6'] || 0 },
    { range: '7+', count: disc.card_distribution['7+'] || 0 },
  ] : [];

  // Home vs Away yellows comparison
  const biasData = [
    { category: 'Home Yellows', value: bias.home_yellows_total || 0, fill: COLOURS.cyan },
    { category: 'Away Yellows', value: bias.away_yellows_total || 0, fill: COLOURS.amber },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <button onClick={() => navigate('/referees')} className="text-xs text-text-muted hover:text-accent-cyan mb-1 block">
          &larr; Back to Referees
        </button>
        <h2 className="text-xl font-ui font-bold text-text-primary">{impact?.referee_name || 'Referee'}</h2>
        <span className="text-xs font-data text-text-secondary">{impact?.total_matches || 0} matches</span>
      </div>

      {/* Stat cards row */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard label="Avg Cards (Career)" value={disc.avg_cards_career} accent="amber" />
        <StatCard label="Avg Cards (L20)" value={disc.avg_cards_l20} accent={disc.avg_cards_l20 > disc.avg_cards_career ? 'red' : 'green'} />
        <StatCard label="Home Bias" value={bias.home_bias_ratio?.toFixed(3)} subValue={bias.direction} accent={bias.direction === 'neutral' ? 'cyan' : 'amber'} />
        <StatCard label="Goals/Match" value={flow.avg_goals_per_match} accent="green" />
        <StatCard label="Over 2.5 %" value={flow.over25_rate ? `${flow.over25_rate}%` : '—'} accent="purple" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Card 1: Disciplinary Profile */}
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Disciplinary Profile</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <span className="text-[10px] font-data text-text-muted">Total Yellows</span>
              <div className="text-lg font-data font-bold text-accent-amber">{disc.total_yellows ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Total Reds</span>
              <div className="text-lg font-data font-bold text-accent-red">{disc.total_reds ?? '—'}</div>
            </div>
          </div>
          {cardDistData.length > 0 && (
            <>
              <span className="text-[10px] font-data text-text-muted">Card Distribution</span>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={cardDistData}>
                  <XAxis dataKey="range" tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Bar dataKey="count" fill={COLOURS.amber} />
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </div>

        {/* Card 2: Home/Away Bias */}
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Home / Away Bias</h3>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={biasData} layout="vertical">
              <XAxis type="number" tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="category" tick={{ fill: COLOURS.textSecondary, fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
              <Bar dataKey="value">
                {biasData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs font-data text-text-secondary mt-2">
            {bias.direction === 'home_heavy'
              ? 'This referee gives more cards to home teams on average.'
              : bias.direction === 'away_heavy'
              ? 'This referee gives more cards to away teams on average.'
              : 'This referee shows no significant home/away bias.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Card 3: Game Flow Impact */}
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Game Flow Impact</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] font-data text-text-muted">Avg Goals Under This Ref</span>
              <div className="text-lg font-data font-bold text-accent-green">{flow.avg_goals_per_match ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Over 2.5 Rate</span>
              <div className="text-lg font-data font-bold text-accent-purple">{flow.over25_rate ? `${flow.over25_rate}%` : '—'}</div>
            </div>
          </div>
        </div>

        {/* Card 4: Penalty Profile */}
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Penalty Profile</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] font-data text-text-muted">Total Awarded</span>
              <div className="text-lg font-data font-bold text-text-primary">{pens.total_awarded ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Per Match</span>
              <div className="text-lg font-data font-bold text-text-primary">{pens.per_match?.toFixed(3) ?? '—'}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Match log */}
      <div className="stat-card">
        <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Recent Match Log</h3>
        <DataTable
          columns={[
            { key: 'date', label: 'Date' },
            { key: 'home_team', label: 'Home' },
            { key: 'away_team', label: 'Away' },
            { key: 'score', label: 'Score' },
            { key: 'home_yellows', label: 'H Yel', align: 'right' },
            { key: 'away_yellows', label: 'A Yel', align: 'right' },
            { key: 'total_cards', label: 'Total', align: 'right', render: (v) => <span className={v > 5 ? 'text-accent-red font-bold' : ''}>{v}</span> },
            { key: 'penalties_awarded', label: 'Pens', align: 'right' },
            { key: 'over_25', label: 'O2.5', render: (v) => v ? <span className="text-accent-green">Y</span> : <span className="text-text-muted">N</span> },
          ]}
          data={matchLog}
        />
      </div>
    </div>
  );
}
