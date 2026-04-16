import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import StatCard from '../components/shared/StatCard';
import DataTable from '../components/shared/DataTable';
import { API_BASE } from '../utils/constants';

export default function PlayersPage() {
  const { playerId } = useParams();
  const navigate = useNavigate();
  const [players, setPlayers] = useState([]);
  const [player, setPlayer] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('rating');
  const [loading, setLoading] = useState(false);

  // Fetch player list
  useEffect(() => {
    if (playerId) return;
    const fetchPlayers = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API_BASE}/players`, {
          params: { per_page: 100, sort_by: sortBy, search: search || undefined },
        });
        setPlayers(res.data.players || []);
      } catch { setPlayers([]); }
      setLoading(false);
    };
    fetchPlayers();
  }, [playerId, search, sortBy]);

  // Fetch individual player
  useEffect(() => {
    if (!playerId) return;
    const fetchPlayer = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API_BASE}/players/${playerId}`);
        setPlayer(res.data);
      } catch { setPlayer(null); }
      setLoading(false);
    };
    fetchPlayer();
  }, [playerId]);

  // Player list view
  if (!playerId) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="Search players..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-terminal-card border border-terminal-border px-3 py-2 text-sm font-data text-text-primary w-64 focus:border-accent-cyan focus:outline-none"
          />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-terminal-card border border-terminal-border px-3 py-2 text-sm font-data text-text-primary focus:border-accent-cyan focus:outline-none"
          >
            <option value="rating">Rating</option>
            <option value="goals">Goals</option>
            <option value="assists">Assists</option>
            <option value="xg">xG</option>
            <option value="xg_per90">xG/90</option>
            <option value="appearances">Appearances</option>
          </select>
        </div>

        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'team_name', label: 'Team' },
            { key: 'position', label: 'Pos' },
            { key: 'appearances', label: 'Apps', align: 'right' },
            { key: 'goals', label: 'Goals', align: 'right' },
            { key: 'assists', label: 'Ast', align: 'right' },
            { key: 'xg', label: 'xG', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
            { key: 'xg_per90', label: 'xG/90', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
            { key: 'rating', label: 'Rating', align: 'right', render: (v) => v?.toFixed(2) ?? '—' },
          ]}
          data={players}
          onRowClick={(row) => navigate(`/players/${row.id}`)}
        />
      </div>
    );
  }

  // Player detail view
  if (loading || !player) {
    return <div className="text-text-muted font-data text-sm py-8 text-center">Loading player...</div>;
  }

  return (
    <div className="space-y-4">
      <button onClick={() => navigate('/players')} className="text-xs text-text-muted hover:text-accent-cyan">
        &larr; Back to Players
      </button>

      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-xl font-ui font-bold text-text-primary">{player.clean_name || player.name}</h2>
          <div className="flex items-center gap-3 text-xs font-data text-text-secondary">
            <span>{player.team_name}</span>
            <span>{player.position}</span>
            <span>Age: {player.age ?? '—'}</span>
            <span>{player.nationality}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-3">
        <StatCard label="Appearances" value={player.appearances} accent="cyan" />
        <StatCard label="Goals" value={player.goals} accent="green" />
        <StatCard label="Assists" value={player.assists} accent="green" />
        <StatCard label="xG" value={player.xg?.toFixed(2)} accent="cyan" />
        <StatCard label="xG/90" value={player.xg_per90?.toFixed(2)} accent="amber" />
        <StatCard label="Rating" value={player.rating?.toFixed(2)} accent="purple" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Shooting</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] font-data text-text-muted">Shots</span>
              <div className="text-lg font-data font-bold text-text-primary">{player.shots ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">On Target</span>
              <div className="text-lg font-data font-bold text-text-primary">{player.shots_on_target ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Conversion</span>
              <div className="text-lg font-data font-bold text-accent-green">{player.shot_conversion_rate ? `${(player.shot_conversion_rate * 100).toFixed(1)}%` : '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Minutes</span>
              <div className="text-lg font-data font-bold text-text-primary">{player.minutes_played?.toLocaleString() ?? '—'}</div>
            </div>
          </div>
        </div>

        <div className="stat-card">
          <h3 className="text-xs font-data text-text-muted uppercase tracking-wider mb-3">Discipline & Creativity</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] font-data text-text-muted">Yellow Cards</span>
              <div className="text-lg font-data font-bold text-accent-amber">{player.yellow_cards ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">Red Cards</span>
              <div className="text-lg font-data font-bold text-accent-red">{player.red_cards ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">xA</span>
              <div className="text-lg font-data font-bold text-accent-cyan">{player.xa?.toFixed(2) ?? '—'}</div>
            </div>
            <div>
              <span className="text-[10px] font-data text-text-muted">xA/90</span>
              <div className="text-lg font-data font-bold text-accent-cyan">{player.xa_per90?.toFixed(2) ?? '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
