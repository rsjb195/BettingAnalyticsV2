import StatCard from '../shared/StatCard';

export default function RefereeProfileCard({ profile, impact }) {
  if (!profile) return null;
  const disc = impact?.disciplinary || {};
  const bias = impact?.home_away_bias || {};
  return (
    <div className="grid grid-cols-5 gap-3">
      <StatCard label="Avg Cards (Career)" value={disc.avg_cards_career} accent="amber" />
      <StatCard label="Avg Cards (L20)" value={disc.avg_cards_l20} accent={disc.avg_cards_l20 > disc.avg_cards_career ? 'red' : 'green'} />
      <StatCard label="Home Bias" value={bias.home_bias_ratio?.toFixed(3)} subValue={bias.direction} accent={bias.direction === 'neutral' ? 'cyan' : 'amber'} />
      <StatCard label="Over 2.5 %" value={impact?.game_flow?.over25_rate ? `${impact.game_flow.over25_rate}%` : '—'} accent="purple" />
      <StatCard label="Pens/Match" value={impact?.penalties?.per_match?.toFixed(3)} accent="cyan" />
    </div>
  );
}
