import { Zap, Settings, Plane, Clock, CheckCircle2, Flag, Lock } from 'lucide-react';

/* ── Scope badge ──────────────────────────────────────────────────────────── */
export function scopeBadge(scope) {
  return <span className={`badge badge-scope${scope}`}>Scope {scope}</span>;
}

/* ── Status badge ─────────────────────────────────────────────────────────── */
const STATUS_META = {
  pending_review: { label: 'Pending',  cls: 'badge-pending',  Icon: Clock },
  approved:       { label: 'Approved', cls: 'badge-approved', Icon: CheckCircle2 },
  flagged:        { label: 'Flagged',  cls: 'badge-flagged',  Icon: Flag },
  locked:         { label: 'Locked',   cls: 'badge-locked',   Icon: Lock },
};

export function statusBadge(status) {
  const { label, cls, Icon } = STATUS_META[status] || STATUS_META.pending_review;
  return (
    <span className={`badge ${cls}`}>
      <Icon size={10} strokeWidth={2.5} />
      {label}
    </span>
  );
}

/* ── Source badge ─────────────────────────────────────────────────────────── */
const SOURCE_META = {
  sap:     { label: 'SAP',     cls: 'badge-sap',     Icon: Settings },
  utility: { label: 'Utility', cls: 'badge-utility', Icon: Zap },
  travel:  { label: 'Travel',  cls: 'badge-travel',  Icon: Plane },
};

export function sourceBadge(source) {
  const { label, cls, Icon } = SOURCE_META[source] || { label: source, cls: '', Icon: Settings };
  return (
    <span className={`badge ${cls}`}>
      <Icon size={10} strokeWidth={2.5} />
      {label}
    </span>
  );
}

/* ── Formatters ───────────────────────────────────────────────────────────── */
export function fmtCo2(kg) {
  if (kg === null || kg === undefined) return '—';
  const n = parseFloat(kg);
  if (isNaN(n)) return '—';
  if (n >= 1000) return `${(n / 1000).toFixed(2)} tCO₂e`;
  return `${n.toFixed(2)} kgCO₂e`;
}

export function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

export function fmtNum(n, decimals = 0) {
  if (n === null || n === undefined) return '—';
  return parseFloat(n).toLocaleString('en-GB', { maximumFractionDigits: decimals });
}
