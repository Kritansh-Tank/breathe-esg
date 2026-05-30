import { useState, useEffect } from 'react';
import {
  CheckCircle2, Flag, Lock, X, ChevronLeft, ChevronRight,
  SlidersHorizontal, CheckSquare,
} from 'lucide-react';
import Layout from '../components/Layout';
import { ingestionAPI } from '../api';
import {
  scopeBadge, statusBadge, sourceBadge, fmtCo2, fmtDate,
} from '../components/utils';
import { useAuth } from '../AuthContext';

/* ── Record detail drawer ──────────────────────────────────────────────────── */
function RecordDrawer({ record, onClose, onRefresh }) {
  const [currentRecord, setCurrentRecord] = useState(record);
  const [note,    setNote]    = useState(record?.analyst_note || '');
  const [loading, setLoading] = useState(false);
  const [msg,     setMsg]     = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    setCurrentRecord(record);
    setNote(record?.analyst_note || '');
    setMsg(null);
  }, [record]);

  if (!currentRecord) return null;

  const isLocked = currentRecord.status === 'locked';

  const act = async (fn, successMsg = 'Done') => {
    setLoading(true); setMsg(null);
    try {
      await fn();
      // Re-fetch this record so the drawer updates instantly
      const fresh = await ingestionAPI.record(currentRecord.id);
      setCurrentRecord(fresh.data);
      setNote(fresh.data.analyst_note || '');
      setMsg({ type: 'success', text: successMsg });
      onRefresh(); // also refresh the table behind
    } catch (e) {
      setMsg({ type: 'error', text: e.response?.data?.error || 'Something went wrong.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" id="record-drawer">
        {/* Header */}
        <div className="drawer-header">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="drawer-title truncate">{currentRecord.description}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
              {scopeBadge(currentRecord.scope)}
              {statusBadge(currentRecord.status)}
              {sourceBadge(currentRecord.source_type)}
            </div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" id="drawer-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="drawer-body">
          {/* Feedback */}
          {msg && (
            <div className={`alert alert-${msg.type === 'success' ? 'success' : 'error'} mb-3`}>
              {msg.type === 'success'
                ? <CheckCircle2 size={14} style={{ flexShrink: 0 }} />
                : <Flag size={14} style={{ flexShrink: 0 }} />}
              <span>{msg.text}</span>
            </div>
          )}

          {/* Emission highlight */}
          <div style={{
            background: 'var(--green-50)', border: '1px solid var(--green-100)',
            borderRadius: 'var(--radius)', padding: '14px 16px', marginBottom: 18,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div className="text-xs text-muted" style={{ marginBottom: 2 }}>Total CO₂e</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--green-700)' }}>
                {fmtCo2(currentRecord.co2e_kg)}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="text-xs text-muted">Emission factor</div>
              <div className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
                {currentRecord.emission_factor} kgCO₂e / {currentRecord.activity_unit}
              </div>
              <div className="text-xs text-muted">{currentRecord.emission_factor_source}</div>
            </div>
          </div>

          {/* Detail grid */}
          <dl className="dl">
            <dt>Source ID</dt>
            <dd><span className="font-mono text-sm">{currentRecord.source_id}</span></dd>

            <dt>Category</dt>
            <dd style={{ textTransform: 'capitalize' }}>
              {currentRecord.category?.replace(/_/g, ' ')}
            </dd>

            <dt>Activity</dt>
            <dd>
              {currentRecord.activity_quantity} {currentRecord.activity_unit}
              {currentRecord.activity_unit_original !== currentRecord.activity_unit && (
                <span className="text-muted text-xs"> (orig: {currentRecord.activity_unit_original})</span>
              )}
            </dd>

            <dt>Period</dt>
            <dd>{fmtDate(currentRecord.period_start)} – {fmtDate(currentRecord.period_end)}</dd>

            <dt>Facility</dt>
            <dd>{currentRecord.facility_code || '—'}</dd>

            <dt>Country</dt>
            <dd>{currentRecord.country || '—'}</dd>

            <dt>Supplier / Site</dt>
            <dd className="truncate">{currentRecord.supplier_or_site || '—'}</dd>

            {currentRecord.is_edited && (
              <>
                <dt>Last edited</dt>
                <dd>{fmtDate(currentRecord.last_edited_at)}</dd>
              </>
            )}

            {currentRecord.locked_at && (
              <>
                <dt>Locked</dt>
                <dd>{fmtDate(currentRecord.locked_at)}</dd>
              </>
            )}
          </dl>

          {/* Analyst note — only shown to analyst/admin when not locked */}
          {!isLocked && (user?.role === 'analyst' || user?.role === 'admin') && (
            <div style={{ marginTop: 18 }}>
              <div className="divider" />
              <div className="form-group">
                <label className="form-label" htmlFor="flag-note">Review note</label>
                <textarea
                  id="flag-note"
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  rows={3}
                  placeholder="Add a note or flag reason…"
                  style={{ resize: 'vertical', fontSize: 13 }}
                />
              </div>
            </div>
          )}

          {/* Show existing note to auditors read-only */}
          {currentRecord.analyst_note && user?.role === 'auditor' && (
            <div style={{
              marginTop: 14, padding: '10px 12px',
              background: 'var(--amber-50)', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--amber-100)',
            }}>
              <div className="text-xs font-semibold text-secondary" style={{ marginBottom: 3 }}>Review note</div>
              <p className="text-sm" style={{ color: 'var(--amber-600)' }}>{currentRecord.analyst_note}</p>
            </div>
          )}

          {currentRecord.analyst_note && isLocked && (
            <div style={{
              marginTop: 14, padding: '10px 12px',
              background: 'var(--amber-50)', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--amber-100)',
            }}>
              <div className="text-xs font-semibold text-secondary" style={{ marginBottom: 3 }}>Review note</div>
              <p className="text-sm" style={{ color: 'var(--amber-600)' }}>{currentRecord.analyst_note}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="drawer-footer">
          {/* Analyst / Admin actions */}
          {(user?.role === 'analyst' || user?.role === 'admin') && !isLocked && (
            <>
              <button
                id="btn-approve"
                className="btn btn-primary btn-sm"
                onClick={() => act(() => ingestionAPI.approve(currentRecord.id), 'Record approved')}
                disabled={loading || currentRecord.status === 'approved'}
              >
                <CheckCircle2 size={13} />
                Approve
              </button>
              <button
                id="btn-flag"
                className="btn btn-danger btn-sm"
                onClick={() => act(() => ingestionAPI.flag(currentRecord.id, note), 'Record flagged')}
                disabled={loading}
              >
                <Flag size={13} />
                Flag
              </button>
            </>
          )}

          {/* Admin-only lock */}
          {user?.role === 'admin' && !isLocked && currentRecord.status === 'approved' && (
            <button
              id="btn-lock"
              className="btn btn-sm"
              style={{ background: 'var(--violet-50)', color: 'var(--violet-600)', border: '1px solid var(--violet-100)' }}
              onClick={() => act(() => ingestionAPI.lock(currentRecord.id), 'Record locked for audit')}
              disabled={loading}
            >
              <Lock size={13} />
              Lock
            </button>
          )}

          {/* Locked notice */}
          {isLocked && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--violet-600)' }}>
              <Lock size={13} />
              Locked for audit
            </div>
          )}

          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </>
  );
}

/* ── Main Review page ─────────────────────────────────────────────────────── */
export default function ReviewPage() {
  const { user } = useAuth();
  const [records,    setRecords]    = useState([]);
  const [pagination, setPagination] = useState({ count: 0 });
  const [page,       setPage]       = useState(1);
  const [filters,    setFilters]    = useState({ scope: '', status: '', source_type: '' });
  const [selected,   setSelected]   = useState([]);
  const [active,     setActive]     = useState(null);
  const [loading,    setLoading]    = useState(true);

  const load = (p = page, f = filters) => {
    setLoading(true);
    const params = { page: p, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) };
    ingestionAPI.records(params)
      .then(r => { setRecords(r.data.results); setPagination(r.data); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { setPage(1); load(1, filters); }, [filters]);

  const setFilter = (k, v) => setFilters(f => ({ ...f, [k]: v }));
  const clearFilters = () => setFilters({ scope: '', status: '', source_type: '' });

  const canApprove = r => r.status === 'pending_review' || r.status === 'flagged';
  const approvableRecords = records.filter(canApprove);
  const approvableSelected = selected.filter(id => approvableRecords.some(r => r.id === id));

  const toggleSelect = id => {
    if (!canApprove(records.find(r => r.id === id))) return; // ignore clicks on non-approvable
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  };
  const allApprovableSelected = approvableRecords.length > 0 && approvableSelected.length === approvableRecords.length;
  const bulkApprove = async () => {
    if (!approvableSelected.length) return;
    try {
      await ingestionAPI.bulkApprove(approvableSelected);
      setSelected([]);
      load();
    } catch (e) { console.error(e); }
  };

  const totalPages = Math.ceil(pagination.count / 25);

  const nextPage = () => { const p = page + 1; setPage(p); load(p); };
  const prevPage = () => { const p = page - 1; setPage(p); load(p); };

  const filtersActive = Object.values(filters).some(v => v);

  return (
    <Layout
      title="Review Records"
      subtitle={`${pagination.count} total records`}
      actions={
        approvableSelected.length > 0 && (user?.role === 'analyst' || user?.role === 'admin') && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="text-sm text-muted">{approvableSelected.length} selected</span>
            <button id="bulk-approve-btn" className="btn btn-primary btn-sm" onClick={bulkApprove}>
              <CheckSquare size={13} /> Approve selected
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelected([])}>
              <X size={13} /> Clear
            </button>
          </div>
        )
      }
    >
      {/* Filters */}
      <div className="filters-row">
        <SlidersHorizontal size={14} color="var(--text-muted)" />

        <select id="filter-scope" value={filters.scope} onChange={e => setFilter('scope', e.target.value)}>
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>

        <select id="filter-status" value={filters.status} onChange={e => setFilter('status', e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending_review">Pending</option>
          <option value="approved">Approved</option>
          <option value="flagged">Flagged</option>
          <option value="locked">Locked</option>
        </select>

        <select id="filter-source" value={filters.source_type} onChange={e => setFilter('source_type', e.target.value)}>
          <option value="">All sources</option>
          <option value="sap">SAP</option>
          <option value="utility">Utility</option>
          <option value="travel">Travel</option>
        </select>

        {filtersActive && (
          <button className="btn btn-ghost btn-sm" onClick={clearFilters}>
            <X size={12} /> Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="card">
        {loading ? (
          <div className="page-loader"><div className="spinner" /> Loading records…</div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 36 }}>
                      {/* Select-all only covers approvable rows */}
                      {(user?.role === 'analyst' || user?.role === 'admin') && approvableRecords.length > 0 && (
                        <input
                          type="checkbox"
                          checked={allApprovableSelected}
                          onChange={e => setSelected(e.target.checked ? approvableRecords.map(r => r.id) : [])}
                        />
                      )}
                    </th>
                    <th>Source</th>
                    <th>Description</th>
                    <th>Scope</th>
                    <th>Period</th>
                    <th>Activity</th>
                    <th>CO₂e</th>
                    <th>Status</th>
                    <th style={{ width: 60 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {records.length === 0 ? (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--text-muted)' }}>
                        No records match the current filters.
                      </td>
                    </tr>
                  ) : records.map(r => (
                    <tr
                      key={r.id}
                      className={selected.includes(r.id) ? 'selected' : ''}
                    >
                      <td style={{ width: 36 }}>
                        {/* Checkbox only for approvable records and analyst/admin */}
                        {(user?.role === 'analyst' || user?.role === 'admin') && canApprove(r) && (
                          <input
                            type="checkbox"
                            checked={selected.includes(r.id)}
                            onChange={() => toggleSelect(r.id)}
                          />
                        )}
                      </td>
                      <td>{sourceBadge(r.source_type)}</td>
                      <td>
                        <div style={{ fontWeight: 500, fontSize: 13 }}>
                          {r.description?.substring(0, 52)}{r.description?.length > 52 ? '…' : ''}
                        </div>
                        {(r.facility_code || r.country) && (
                          <div className="text-xs text-muted" style={{ marginTop: 2 }}>
                            {[r.facility_code, r.country].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td>{scopeBadge(r.scope)}</td>
                      <td className="text-sm text-muted">{fmtDate(r.period_start)}</td>
                      <td className="text-sm">
                        <span className="font-mono">
                          {parseFloat(r.activity_quantity).toLocaleString('en-GB')}
                        </span>{' '}
                        <span className="text-muted">{r.activity_unit}</span>
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--green-700)' }}>
                        {fmtCo2(r.co2e_kg)}
                      </td>
                      <td>{statusBadge(r.status)}</td>
                      <td>
                        <button
                          className="btn btn-ghost btn-sm"
                          id={`view-${r.id}`}
                          onClick={() => setActive(r)}
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          <ChevronRight size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="pagination">
              <span className="page-info">
                Page {page} of {totalPages || 1} · {pagination.count} records
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn btn-secondary btn-sm" onClick={prevPage} disabled={!pagination.previous}>
                  <ChevronLeft size={13} />
                </button>
                <button className="btn btn-secondary btn-sm" onClick={nextPage} disabled={!pagination.next}>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Drawer */}
      {active && (
        <RecordDrawer
          record={active}
          onClose={() => setActive(null)}
          onRefresh={() => load()}
        />
      )}
    </Layout>
  );
}
