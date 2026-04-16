import { AlertTriangle } from 'lucide-react';

/**
 * Alert component for high-value or high-risk situations.
 */
export default function ValueAlert({ type = 'value', title, message }) {
  const styles = {
    value: 'bg-accent-green/5 border-accent-green/30 text-accent-green',
    warning: 'bg-accent-amber/5 border-accent-amber/30 text-accent-amber',
    danger: 'bg-accent-red/5 border-accent-red/30 text-accent-red',
  };

  return (
    <div className={`border px-3 py-2 flex items-start gap-2 ${styles[type]}`}>
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
      <div>
        <div className="text-xs font-data font-bold">{title}</div>
        <div className="text-xs font-data opacity-80 mt-0.5">{message}</div>
      </div>
    </div>
  );
}
