import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid,
} from 'recharts';
import { TrendingUp, Zap, Settings, Plane, Clock } from 'lucide-react';
import Layout from '../components/Layout';
import { ingestionAPI } from '../api';
import { fmtCo2 } from '../components/utils';

const SCOPE_COLORS = { 1: '#f97316', 2: '#3b82f6', 3: '#8b5cf6' };
const SCOPE_BG     = { 1: '#fff7ed', 2: '#eff6ff', 3: '#f5f3ff' };

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'white', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
      boxShadow: 'var(--shadow-md)',
    }}>
      <div className="text-muted text-xs" style={{ marginBottom: 3 }}>
        {payload[0].payload.category?.replace(/_/g, ' ')}
      </div>
      <div style={{ fontWeight: 700, color: 'var(--text)' }}>{fmtCo2(payload[0].value)}</div>
    </div>
  );
};

const StatCard = ({ label, value, unit, icon: Icon, iconBg, iconColor, accent }) => (
  <div className="stat-card" style={{ borderTop: `3px solid ${accent}` }}>
    <div className="stat-header">
      <span className="stat-label">{label}</span>
      <div className="stat-icon" style={{ background: iconBg }}>
        <Icon size={14} color={iconColor} strokeWidth={2} />
      </div>
    </div>
    <div>
      <div className="stat-value">{value}</div>
      {unit && <div className="stat-unit">{unit}</div>}
    </div>
  </div>
);

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ingestionAPI.summary()
      .then(r => setSummary(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Layout title="Dashboard">
        <div className="page-loader"><div className="spinner" /> Loading…</div>
      </Layout>
    );
  }

  const scopeData    = summary?.by_scope || [];
  const categoryData = (summary?.by_category || []).map(c => ({
    ...c,
    label: c.category.replace(/_/g, ' ').replace('business travel ', '').replace('stationary ', '').replace('purchased ', ''),
  }));
  const statusData   = summary?.by_status || [];

  const getScope = n => scopeData.find(s => s.scope === n);
  const total    = parseFloat(summary?.total_co2e_kg || 0);
  const pending  = statusData.find(s => s.status === 'pending_review')?.count || 0;

  return (
    <Layout title="Dashboard" subtitle="Emissions summary across all ingested sources">
      {/* Stat cards */}
      <div className="stat-grid">
        <StatCard
          label="Total Emissions"
          value={(total / 1000).toFixed(2)}
          unit={`tCO₂e · ${summary?.total_records || 0} records`}
          icon={TrendingUp}
          iconBg="var(--green-50)" iconColor="var(--green-700)"
          accent="var(--green-600)"
        />
        <StatCard
          label="Scope 1 — Direct"
          value={getScope(1) ? fmtCo2(getScope(1).co2e_kg_total) : '—'}
          unit={`${getScope(1)?.record_count || 0} records · fuel combustion`}
          icon={Settings}
          iconBg="var(--orange-50)" iconColor="var(--orange-500)"
          accent="var(--orange-500)"
        />
        <StatCard
          label="Scope 2 — Electricity"
          value={getScope(2) ? fmtCo2(getScope(2).co2e_kg_total) : '—'}
          unit={`${getScope(2)?.record_count || 0} records · purchased energy`}
          icon={Zap}
          iconBg="var(--blue-50)" iconColor="var(--blue-500)"
          accent="var(--blue-500)"
        />
        <StatCard
          label="Scope 3 — Travel"
          value={getScope(3) ? fmtCo2(getScope(3).co2e_kg_total) : '—'}
          unit={`${getScope(3)?.record_count || 0} records · business travel`}
          icon={Plane}
          iconBg="var(--violet-50)" iconColor="var(--violet-500)"
          accent="var(--violet-500)"
        />
        <StatCard
          label="Pending Review"
          value={pending}
          unit="records awaiting approval"
          icon={Clock}
          iconBg="var(--amber-50)" iconColor="var(--amber-600)"
          accent="var(--amber-500)"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Category chart */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Emissions by Category</div>
              <div className="card-subtitle">kgCO₂e per activity category</div>
            </div>
          </div>
          <div style={{ padding: '16px 8px 8px' }}>
            {categoryData.length === 0 ? (
              <div className="page-loader" style={{ minHeight: 200 }}>
                <span className="text-muted text-sm">No data yet — upload a CSV to get started</span>
              </div>
            ) : (
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryData} layout="vertical" margin={{ left: 0, right: 20, top: 4, bottom: 4 }}>
                    <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickFormatter={v => `${(v / 1000).toFixed(1)}t`} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} width={120} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--bg-subtle)' }} />
                    <Bar dataKey="co2e_kg_total" radius={4} maxBarSize={24}>
                      {categoryData.map((entry, i) => (
                        <Cell key={i} fill={SCOPE_COLORS[entry.scope] || '#9ca3af'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* Status + scope breakdown */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Review Status</div>
              <div className="card-subtitle">Progress towards audit lock</div>
            </div>
          </div>
          <div style={{ padding: '16px 20px' }}>
            {[
              { key: 'pending_review', label: 'Pending Review', color: 'var(--amber-500)' },
              { key: 'approved',       label: 'Approved',       color: 'var(--green-600)' },
              { key: 'flagged',        label: 'Flagged',        color: 'var(--red-500)' },
              { key: 'locked',         label: 'Locked',         color: 'var(--violet-500)' },
            ].map(({ key, label, color }) => {
              const count = statusData.find(s => s.status === key)?.count || 0;
              const total_r = summary?.total_records || 1;
              const pct = Math.round((count / total_r) * 100);
              return (
                <div key={key} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5, fontSize: 13 }}>
                    <span style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>{label}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text)' }}>{count} <span className="text-muted text-xs">({pct}%)</span></span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}

            <div className="divider" />

            {/* Scope breakdown table */}
            <div className="card-title" style={{ marginBottom: 10 }}>Scope Summary</div>
            {scopeData.length === 0
              ? <p className="text-sm text-muted">No records yet.</p>
              : scopeData.map(s => (
                <div key={s.scope} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '9px 12px', borderRadius: 'var(--radius-sm)',
                  background: SCOPE_BG[s.scope] || 'var(--bg-subtle)',
                  marginBottom: 6,
                }}>
                  <span className={`badge badge-scope${s.scope}`}>Scope {s.scope}</span>
                  <span style={{ fontWeight: 700, fontSize: 13 }}>{fmtCo2(s.co2e_kg_total)}</span>
                  <span className="text-xs text-muted">{s.record_count} records</span>
                </div>
              ))
            }
          </div>
        </div>
      </div>
    </Layout>
  );
}
