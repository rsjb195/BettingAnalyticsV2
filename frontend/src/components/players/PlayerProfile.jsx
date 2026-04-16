import StatCard from '../shared/StatCard';

export default function PlayerProfile({ player }) {
  if (!player) return null;
  return (
    <div className="grid grid-cols-6 gap-3">
      <StatCard label="Appearances" value={player.appearances} accent="cyan" />
      <StatCard label="Goals" value={player.goals} accent="green" />
      <StatCard label="Assists" value={player.assists} accent="green" />
      <StatCard label="xG" value={player.xg?.toFixed(2)} accent="cyan" />
      <StatCard label="xG/90" value={player.xg_per90?.toFixed(2)} accent="amber" />
      <StatCard label="Rating" value={player.rating?.toFixed(2)} accent="purple" />
    </div>
  );
}
