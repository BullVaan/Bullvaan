import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  History,
  Settings,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

export default function Sidebar() {
  const [open, setOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const menu = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: <LayoutDashboard size={20} />
    },
    { name: 'Trades', path: '/trades', icon: <BarChart3 size={20} /> },
    { name: 'History', path: '/history', icon: <History size={20} /> },
    { name: 'Settings', path: '/settings', icon: <Settings size={20} /> }
  ];

  return (
    <div
      style={{
        width: open ? 230 : 75,
        background: '#020617',
        height: '100vh',
        borderRight: '1px solid #334155',
        transition: '0.3s',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Toggle */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: 16,
          cursor: 'pointer',
          borderBottom: '1px solid #334155',
          textAlign: 'right',
          color: '#94a3b8'
        }}
      >
        {open ? <ChevronLeft /> : <ChevronRight />}{' '}
      </div>

      {/* Menu */}
      <div style={{ paddingTop: 10 }}>
        {menu.map((item) => {
          const active = location.pathname === item.path;

          return (
            <div
              key={item.name}
              onClick={() => navigate(item.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '14px 18px',
                cursor: 'pointer',
                background: active ? '#0f172a' : 'transparent',
                color: active ? '#22c55e' : '#cbd5f5',
                borderLeft: active
                  ? '4px solid #22c55e'
                  : '4px solid transparent',
                transition: '0.2s'
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = '#0f172a')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = active
                  ? '#0f172a'
                  : 'transparent')
              }
            >
              {item.icon}
              {open && <span style={{ fontSize: 15 }}>{item.name}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
