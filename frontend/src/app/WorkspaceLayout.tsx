import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, ArrowLeft, Boxes, CircleDot, Fingerprint, LockKeyhole, Microscope, PanelLeftClose, ShieldCheck } from 'lucide-react';
import { useRuntime } from '../services/runtime';
import { useState } from 'react';
import { ConnectionPill } from '../components/ConnectionPill';
import { ThemeToggle } from './ThemeControl';

const nav = [
  { to: '/workspace', label: 'Data Workspace', icon: Boxes },
  { to: '/engine', label: 'Privacy Engine', icon: Activity },
  { to: '/identities', label: 'Identity Resolution', icon: Fingerprint },
  { to: '/integrity', label: 'Privacy & Integrity', icon: ShieldCheck },
  { to: '/research', label: 'Research Data Explorer', icon: Microscope },
  { to: '/release', label: 'Release Center', icon: LockKeyhole },
];

const titles: Record<string, string> = {
  '/workspace': 'Data Workspace', '/engine': 'Privacy Engine', '/identities': 'Identity Resolution',
  '/integrity': 'Privacy & Integrity', '/release': 'Release Center', '/research': 'Research Data Explorer',
};

export default function WorkspaceLayout() {
  const {connected}=useRuntime();
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  return (
    <div className={`workspace-shell ${collapsed ? 'is-collapsed' : ''}`}>
      <aside className="sidebar" aria-label="Workspace navigation">
        <div className="sidebar-top">
          <NavLink to="/" className="brand brand-compact" aria-label="Shield home">
            <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
            {!collapsed && <span className="brand-name">shield<span className="brand-dot">.</span></span>}
          </NavLink>
          <button className="icon-button collapse-control" onClick={() => setCollapsed(v => !v)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
            <PanelLeftClose size={16} />
          </button>
        </div>
        <div className="rail-label">{!collapsed && 'WORKSPACE'}</div>
        <nav className="rail-nav">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `rail-link ${isActive ? 'active' : ''}`} title={collapsed ? label : undefined}>
              <Icon size={17} strokeWidth={1.65} /><span>{!collapsed && label}</span>{!collapsed && location.pathname === to && <CircleDot size={9} className="nav-current" />}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="connection-block"><span className="connection-dot" />{!collapsed && <><span>{connected ? "Engine connected" : "Engine not connected"}</span><span className="connection-tiny">{connected ? "LOCAL" : "OFFLINE"}</span></>}</div>
          <div className="sidebar-bottom">
            <NavLink to="/" className="rail-link back-link"><ArrowLeft size={16} /><span>{!collapsed && 'Back to overview'}</span></NavLink>
          </div>
        </div>
      </aside>
      <main className="workspace-main">
        <header className="workspace-header">
          <div className="crumb"><span>Shield</span><span className="crumb-slash">/</span><strong>{titles[location.pathname] ?? 'Workspace'}</strong></div>
          <div className="header-right"><ConnectionPill compact /><ThemeToggle /><span className="header-vault"><span className="tiny-vault" />LOCAL SESSION</span></div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
