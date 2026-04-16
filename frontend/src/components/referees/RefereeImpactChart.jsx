import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { COLOURS } from '../../utils/colours';

export default function RefereeImpactChart({ impact }) {
  if (!impact || !impact.disciplinary?.card_distribution) return null;

  const dist = impact.disciplinary.card_distribution;
  const data = [
    { range: '0-2', count: dist['0-2'] || 0 },
    { range: '3-4', count: dist['3-4'] || 0 },
    { range: '5-6', count: dist['5-6'] || 0 },
    { range: '7+', count: dist['7+'] || 0 },
  ];

  return (
    <div>
      <h4 className="text-xs font-data text-text-muted uppercase tracking-wider mb-2">Card Distribution</h4>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data}>
          <XAxis dataKey="range" tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
          <Bar dataKey="count" fill={COLOURS.amber} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
