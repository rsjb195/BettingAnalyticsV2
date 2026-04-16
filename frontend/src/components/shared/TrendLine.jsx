import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import { COLOURS } from '../../utils/colours';

/**
 * Compact sparkline/trend chart for inline metric visualisation.
 *
 * @param {Array<{name: string, value: number}>} data
 * @param {string} [colour] - Line colour (default cyan)
 * @param {number} [height] - Chart height in px (default 80)
 * @param {boolean} [showAxis] - Show X/Y axes
 */
export default function TrendLine({ data, colour = COLOURS.cyan, height = 80, showAxis = false }) {
  if (!data || data.length === 0) {
    return <div className="text-text-muted text-xs font-data">No trend data</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        {showAxis && (
          <>
            <XAxis dataKey="name" tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: COLOURS.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} width={30} />
          </>
        )}
        <Tooltip
          contentStyle={{
            backgroundColor: COLOURS.elevated,
            border: `1px solid ${COLOURS.border}`,
            borderRadius: 0,
            fontSize: 11,
            fontFamily: 'JetBrains Mono, monospace',
          }}
          labelStyle={{ color: COLOURS.textMuted }}
          itemStyle={{ color: COLOURS.textPrimary }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={colour}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: colour }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
