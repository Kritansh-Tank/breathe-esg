import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  UploadCloud, FileText, CheckCircle2,
  AlertCircle, Clock, Download, Info,
} from 'lucide-react';
import Layout from '../components/Layout';
import { ingestionAPI } from '../api';
import { sourceBadge, fmtDate } from '../components/utils';
import { useAuth } from '../AuthContext';

const SOURCE_OPTIONS = [
  { value: 'sap',     label: 'SAP — Fuel & Procurement',    hint: 'ME80FN flat-file CSV export' },
  { value: 'utility', label: 'Utility — Electricity Bills', hint: 'Portal billing history CSV' },
  { value: 'travel',  label: 'Corporate Travel — Concur',   hint: 'Concur Intelligence report CSV' },
];

function UploadPanel({ onSuccess }) {
  const [sourceType, setSourceType] = useState('sap');
  const [uploading,  setUploading]  = useState(false);
  const [result,     setResult]     = useState(null);
  const [error,      setError]      = useState('');

  const onDrop = useCallback(async (files) => {
    if (!files.length) return;
    setUploading(true); setError(''); setResult(null);
    try {
      const res = await ingestionAPI.upload(files[0], sourceType);
      setResult(res.data);
      onSuccess?.();
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }, [sourceType, onSuccess]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    maxFiles: 1,
    disabled: uploading,
  });

  const selected = SOURCE_OPTIONS.find(o => o.value === sourceType);

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <div>
          <div className="card-title">Upload CSV File</div>
          <div className="card-subtitle">Select source type then drop your file</div>
        </div>
      </div>
      <div style={{ padding: '20px 24px' }}>
        {/* Source selector */}
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label className="form-label" htmlFor="source-type">Data source</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {SOURCE_OPTIONS.map(opt => (
              <button
                key={opt.value}
                id={`source-${opt.value}`}
                type="button"
                onClick={() => setSourceType(opt.value)}
                className={`btn ${sourceType === opt.value ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {selected && (
            <p className="text-xs text-muted" style={{ marginTop: 6 }}>
              Expected format: {selected.hint}
            </p>
          )}
        </div>

        {/* Drop zone */}
        <div {...getRootProps()} className={`upload-zone${isDragActive ? ' dragging' : ''}`}>
          <input {...getInputProps()} id="file-upload" />
          <div className="upload-zone-icon">
            <UploadCloud size={36} strokeWidth={1.5} />
          </div>
          <div className="upload-zone-title">
            {uploading ? 'Processing…' : isDragActive ? 'Drop to upload' : 'Drag & drop your CSV file'}
          </div>
          <div className="upload-zone-hint">or click to browse &nbsp;·&nbsp; .csv only &nbsp;·&nbsp; max 10 MB</div>
        </div>

        {/* Feedback */}
        {error && (
          <div className="alert alert-error mt-3">
            <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{error}</span>
          </div>
        )}

        {result && (
          <div className="alert alert-success mt-3">
            <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <div>
              <strong>{result.row_count} records ingested</strong>
              {result.error_count > 0 && (
                <span className="text-xs" style={{ marginLeft: 6 }}>
                  · {result.error_count} rows skipped
                </span>
              )}
            </div>
          </div>
        )}

        {result?.error_log?.length > 0 && (
          <div style={{
            marginTop: 10, background: 'var(--bg-subtle)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.4px' }}>
              Parse errors
            </div>
            {result.error_log.map((e, i) => (
              <div key={i} style={{ padding: '6px 12px', fontSize: 12, color: 'var(--red-600)', borderBottom: i < result.error_log.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontWeight: 600 }}>Row {e.row}:</span> {e.error}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BatchesTable({ batches }) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Ingestion History</div>
          <div className="card-subtitle">{batches.length} upload{batches.length !== 1 ? 's' : ''}</div>
        </div>
      </div>
      {batches.length === 0 ? (
        <div style={{ padding: '32px 24px', textAlign: 'center' }}>
          <Clock size={24} color="var(--text-muted)" style={{ marginBottom: 8 }} />
          <p className="text-sm text-muted">No uploads yet. Upload a CSV file above to get started.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>File</th>
                <th>Records</th>
                <th>Errors</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {batches.map(b => (
                <tr key={b.id}>
                  <td>{sourceBadge(b.source_type)}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <FileText size={13} color="var(--text-muted)" />
                      <span className="font-mono text-sm">{b.file_name}</span>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: 'var(--green-700)' }}>{b.row_count}</span>
                  </td>
                  <td>
                    {b.error_count > 0
                      ? <span style={{ color: 'var(--red-600)', fontWeight: 600 }}>{b.error_count}</span>
                      : <span className="text-muted">—</span>}
                  </td>
                  <td>
                    <span className={`badge ${b.status === 'processed' ? 'badge-approved' : b.status === 'failed' ? 'badge-flagged' : 'badge-pending'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="text-sm text-muted">{fmtDate(b.ingested_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function IngestPage() {
  const [batches, setBatches] = useState([]);
  const { user } = useAuth();

  const load = () =>
    ingestionAPI.batches().then(r => setBatches(r.data)).catch(console.error);

  useEffect(() => { load(); }, []);

  const isAuditor = user?.role === 'auditor';

  return (
    <Layout title="Ingest Data" subtitle="Upload CSV files from SAP, utility portals, or Concur">
      <div style={{ maxWidth: 860 }}>
        {isAuditor ? (
          <div className="alert alert-info mb-4" style={{ marginBottom: 20 }}>
            <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>Auditors have read-only access. Data uploads are restricted to analysts and admins.</span>
          </div>
        ) : (
          <UploadPanel onSuccess={load} />
        )}

        <BatchesTable batches={batches} />

        {/* Sample downloads */}
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Sample Files</div>
              <div className="card-subtitle">Download realistic test CSVs to try the upload</div>
            </div>
          </div>
          <div style={{ padding: '16px 20px', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {[
              { file: 'sample_sap.csv',     label: 'SAP Fuel CSV',        sub: '15 rows, 3 fuel types' },
              { file: 'sample_utility.csv', label: 'Utility Bills CSV',   sub: '8 rows, 3 UK sites' },
              { file: 'sample_travel.csv',  label: 'Concur Travel CSV',   sub: '12 rows, air/rail/car' },
            ].map(({ file, label, sub }) => (
              <a
                key={file}
                href={`/sample_data/${file}`}
                download
                className="btn btn-secondary"
                style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2, padding: '10px 14px', height: 'auto' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Download size={13} />
                  <span style={{ fontWeight: 600 }}>{label}</span>
                </div>
                <span className="text-xs text-muted">{sub}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}
