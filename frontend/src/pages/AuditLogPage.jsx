import { useState, useEffect } from 'react';
import {
  Upload, CheckCircle2, Flag, Lock, PenLine,
  ChevronLeft, ChevronRight, Filter,
} from 'lucide-react';
import Layout from '../components/Layout';
import { ingestionAPI } from '../api';
import { fmtDate } from '../components/utils';

const ACTION_META = {
  ingest:  { label: 'Ingested',  cls: 'audit-ingest',  Icon: Upload },
  approve: { label: 'Approved',  cls: 'audit-approve', Icon: CheckCircle2 },
  flag:    { label: 'Flagged',   cls: 'audit-flag',    Icon: Flag },
  lock:    { label: 'Locked',    cls: 'audit-lock',    Icon: Lock },
  edit:    { label: 'Edited',    cls: 'audit-edit',    Icon: PenLine },
};

export default function AuditLogPage() {
  const [logs,       setLogs]       = useState([]);
  const [pagination, setPagination] = useState({ count: 0 });
  const [page,       setPage]       = useState(1);
  const [action,     setAction]     = useState('');
  const [loading,    setLoading]    = useState(true);

  const load = (p = 1, a = action) => {
    setLoading(true);
    const params = { page: p };
    if (a) params.action = a;
    ingestionAPI.auditLog(params)
      .then(r => { setLogs(r.data.results); setPagination(r.data); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { setPage(1); load(1, action); }, [action]);

  const totalPages = Math.ceil(pagination.count / 25);

  const nextPage = () => { const p = page + 1; setPage(p); load(p); };
  const prevPage = () => { const p = page - 1; setPage(p); load(p); };

  return (
    <Layout title="Audit Log" subtitle="Immutable record of all actions on the dataset">
      <div style={{ maxWidth: 820 }}>
        <div className="card">
          {/* Toolbar */}
          <div className="card-header">
            <div>
              <div className="card-title">Activity History</div>
              <div className="card-subtitle">{pagination.count} entries</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Filter size={13} color="var(--text-muted)" />
              <select
                id="filter-action"
                value={action}
                onChange={e => setAction(e.target.value)}
                style={{ width: 'auto', fontSize: 12.5, padding: '5px 10px' }}
              >
                <option value="">All actions</option>
                <option value="ingest">Ingest</option>
                <option value="approve">Approve</option>
                <option value="flag">Flag</option>
                <option value="lock">Lock</option>
                <option value="edit">Edit</option>
              </select>
            </div>
          </div>

          {/* Log entries */}
          <div style={{ padding: '4px 20px' }}>
            {loading ? (
              <div className="page-loader"><div className="spinner" /></div>
            ) : logs.length === 0 ? (
              <div style={{ padding: '32px 0', textAlign: 'center' }}>
                <p className="text-sm text-muted">No audit log entries yet.</p>
              </div>
            ) : (
              logs.map(log => {
                const meta = ACTION_META[log.action] || ACTION_META.edit;
                const { Icon } = meta;
                return (
                  <div key={log.id} className="audit-item">
                    {/* Icon */}
                    <div className={`audit-icon-wrap ${meta.cls}`}>
                      <Icon size={13} strokeWidth={2} />
                    </div>

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <div>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{meta.label}</span>
                          {log.note && (
                            <span className="text-sm text-muted" style={{ marginLeft: 6 }}>
                              — {log.note.substring(0, 80)}{log.note.length > 80 ? '…' : ''}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-muted" style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
                          {new Date(log.timestamp).toLocaleString('en-GB', {
                            day: '2-digit', month: 'short', year: 'numeric',
                            hour: '2-digit', minute: '2-digit',
                          })}
                        </span>
                      </div>

                      <div className="text-xs text-muted" style={{ marginTop: 3 }}>
                        <span style={{ fontWeight: 500 }}>{log.user_email}</span>
                        <span style={{ margin: '0 5px' }}>·</span>
                        {log.target_type}
                        <span className="font-mono" style={{ marginLeft: 5, fontSize: 10.5 }}>
                          {log.target_id?.substring(0, 8)}…
                        </span>
                      </div>

                      {/* Diff viewer */}
                      {log.action === 'edit' && log.diff?.before && (
                        <details style={{ marginTop: 7 }}>
                          <summary style={{
                            fontSize: 11.5, color: 'var(--amber-600)',
                            cursor: 'pointer', userSelect: 'none',
                          }}>
                            View changes
                          </summary>
                          <div style={{
                            marginTop: 6,
                            background: 'var(--bg-subtle)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius-sm)',
                            overflow: 'auto',
                            maxHeight: 140,
                          }}>
                            <pre style={{ fontSize: 11, padding: '8px 12px', color: 'var(--text-secondary)' }}>
                              {JSON.stringify({ before: log.diff.before, after: log.diff.after }, null, 2)}
                            </pre>
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Pagination */}
          <div className="pagination">
            <span className="page-info">Page {page} of {totalPages || 1}</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-secondary btn-sm" onClick={prevPage} disabled={page === 1}>
                <ChevronLeft size={13} />
              </button>
              <button className="btn btn-secondary btn-sm" onClick={nextPage} disabled={!pagination.next}>
                <ChevronRight size={13} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
