import StatCard from '../shared/StatCard';
import { formatPct } from '../../utils/formatters';

export default function TeamStats({ metrics }) {
  if (!metrics) return null;
  return (
    <div className="grid grid-cols-6 gap-3">
      <StatCard label="PPG" value={metrics.ppg_season?.toFixed(2)} accent="cyan" />
      <StatCard label="xG For" value={metrics.xg_for_avg?.toFixed(2)} accent="green" />
      <StatCard label="xG Against" value={metrics.xg_against_avg?.toFixed(2)} accent="red" />
      <StatCard label="Clean Sheet %" value={formatPct(metrics.clean_sheet_rate)} accent="green" />
      <StatCard label="BTTS %" value={formatPct(metrics.btts_rate)} accent="amber" />
      <StatCard label="Over 2.5 %" value={formatPct(metrics.over25_rate)} accent="purple" />
    </div>
  );
}
