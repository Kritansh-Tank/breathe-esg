import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Leaf, Mail, Lock, AlertCircle } from 'lucide-react';
import { useAuth } from '../AuthContext';

export default function LoginPage() {
  const [email, setEmail]       = useState('analyst@acme.com');
  const [password, setPassword] = useState('breathe123');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const { login } = useAuth();
  const navigate  = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch {
      setError('Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Header */}
        <div className="login-header">
          <div className="login-logo-icon">
            <Leaf size={22} strokeWidth={2.5} />
          </div>
          <div className="login-title">Breathe ESG</div>
          <div className="login-sub">Emissions Data Ingestion Platform</div>
        </div>

        {/* Error */}
        {error && (
          <div className="alert alert-error mb-3">
            <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              <Mail size={12} style={{ display: 'inline', marginRight: 4 }} />
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              <Lock size={12} style={{ display: 'inline', marginRight: 4 }} />
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          <button
            id="login-btn"
            className="btn btn-primary"
            style={{ justifyContent: 'center', marginTop: 4 }}
            disabled={loading}
          >
            {loading ? <><span className="spinner" style={{ borderTopColor: 'white' }} /> Signing in…</> : 'Sign in'}
          </button>
        </form>

        {/* Demo hint */}
        <div style={{
          marginTop: 20, padding: '12px 14px',
          background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)',
        }}>
          <div className="text-xs font-semibold text-secondary" style={{ marginBottom: 6 }}>Demo accounts</div>
          {[
            { email: 'analyst@acme.com',  role: 'Analyst' },
            { email: 'admin@acme.com',    role: 'Admin' },
            { email: 'auditor@acme.com',  role: 'Auditor' },
          ].map(({ email: e, role }) => (
            <div key={e} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span className="text-xs font-mono text-secondary">{e}</span>
              <span className="badge badge-success text-xs">{role}</span>
            </div>
          ))}
          <div className="text-xs text-muted" style={{ marginTop: 4 }}>Password: breathe123</div>
        </div>
      </div>
    </div>
  );
}
