import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { COLOURS } from '../../utils/colours';

export default function FormChart({ formData }) {
  if (!formData || formData.length === 0) return null;

  const chartData = formData.map((f) => ({
    name: f.date,
    goals: f.goals_for || 0,
    fill: f.result === 'W' ? COLOURS.green : f.result === 'D' ? COLOURS.amber : COLOURS.red,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData}>
        <XAxis dataKey="name" tick={false} axisLine={false} />
        <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ backgroundColor: COLOURS.elevated, border: `1px solid ${COLOURS.border}`, borderRadius: 0, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
        <Bar dataKey="goals" fill={COLOURS.cyan} />
      </BarChart>
    </ResponsiveContainer>
  );
}
