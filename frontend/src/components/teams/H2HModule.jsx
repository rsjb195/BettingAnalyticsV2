import { useState, useEffect } from 'react';
import axios from 'axios';
import DataTable from '../shared/DataTable';
import { API_BASE } from '../../utils/constants';

export default function H2HModule({ homeTeamId, awayTeamId }) {
  const [h2h, setH2h] = useState(null);

  useEffect(() => {
    if (!homeTeamId || !awayTeamId) return;
    axios.get(`${API_BASE}/teams/h2h`, { params: { home: homeTeamId, away: awayTeamId } })
      .then((res) => setH2h(res.data))
      .catch(() => setH2h(null));
  }, [homeTeamId, awayTeamId]);

  if (!h2h) return <div className="text-text-muted font-data text-sm">Select two teams to view H2H</div>;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 text-center">
        <div><div className="text-xs font-data text-text-muted">Home Wins</div><div className="text-lg font-data font-bold text-accent-cyan">{h2h.home_wins}</div></div>
        <div><div className="text-xs font-data text-text-muted">Draws</div><div className="text-lg font-data font-bold text-text-primary">{h2h.draws}</div></div>
        <div><div className="text-xs font-data text-text-muted">Away Wins</div><div className="text-lg font-data font-bold text-accent-amber">{h2h.away_wins}</div></div>
      </div>
      <div className="text-xs font-data text-text-secondary text-center">
        {h2h.total_meetings} meetings | Avg goals: {h2h.avg_total_goals} | BTTS: {h2h.btts_rate}%
      </div>
      <DataTable
        columns={[
          { key: 'date', label: 'Date' },
          { key: 'home_goals', label: 'H', align: 'right' },
          { key: 'away_goals', label: 'A', align: 'right' },
        ]}
        data={h2h.matches || []}
      />
    </div>
  );
}
