import clsx from 'clsx';

/**
 * Terminal-style data table with sortable columns.
 *
 * @param {Array<{key: string, label: string, align?: string}>} columns
 * @param {Array<Object>} data - Row objects keyed by column.key
 * @param {Function} [onRowClick] - Callback receiving the row object
 * @param {string} [className]
 */
export default function DataTable({ columns, data, onRowClick, className }) {
  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(col.align === 'right' && 'text-right')}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="text-center text-text-muted py-8">
                No data available
              </td>
            </tr>
          )}
          {data.map((row, i) => (
            <tr
              key={row.id || i}
              onClick={() => onRowClick?.(row)}
              className={clsx(onRowClick && 'cursor-pointer')}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={clsx(col.align === 'right' && 'text-right tabular-nums')}
                >
                  {col.render ? col.render(row[col.key], row) : row[col.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
