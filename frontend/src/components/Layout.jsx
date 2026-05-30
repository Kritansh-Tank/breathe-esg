import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Upload, ClipboardCheck, ScrollText,
  Leaf, LogOut,
} from 'lucide-react';
import { useAuth } from '../AuthContext';

const NAV = [
  { to: '/',       icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/ingest', icon: Upload,          label: 'Ingest Data' },
  { to: '/review', icon: ClipboardCheck,  label: 'Review Records' },
  { to: '/audit',  icon: ScrollText,      label: 'Audit Log' },
];

export default function Layout({ children, title, subtitle, actions }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  const initials = user
    ? `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() ||
      user.email[0].toUpperCase()
    : '?';

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Leaf size={17} strokeWidth={2.5} />
          </div>
          <div>
            <div className="logo-text">Breathe ESG</div>
            <div className="logo-sub">Emissions Platform</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon size={15} strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-avatar">{initials}</div>
            <div className="user-info">
              <div className="user-name">{user?.first_name} {user?.last_name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Sign out">
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <div className="topbar-title">{title}</div>
            {subtitle && <div className="topbar-sub">{subtitle}</div>}
          </div>
          <div className="topbar-right">
            {actions}
            {user?.organization?.name && (
              <span className="org-badge">{user.organization.name}</span>
            )}
          </div>
        </header>

        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
