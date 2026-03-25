import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Landmark,
  ListOrderedIcon
} from 'lucide-react';

export default function Sidebar() {
  const [open, setOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const menu = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: <LayoutDashboard size={24} />
    },
    {
      name: 'Active Orders',
      path: '/trades',
      icon: <ListOrderedIcon size={24} />
    },
    {
      name: 'Stock Screener',
      path: '/swing-trade',
      icon: <Landmark size={24} />
    },
    {
      name: 'Charting',
      path: '/candles-charts',
      icon: <BarChart3 size={24} />
    },
    { name: 'History', path: '/history', icon: <History size={24} /> },
    { name: 'Settings', path: '/settings', icon: <Settings size={24} /> }
  ];

  return (
    <div
      style={{
        width: open ? 220 : 80,
        background: '#020617',
        height: '100vh',
        borderRight: '1px solid #334155',
        transition: '0.3s',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0
      }}
    >
      {/* Logo/Brand */}
      <div
        style={{
          padding: open ? '12px 8px 0px 0' : '6px 0px 0px 0',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: open ? 'space-between' : 'center',
          minHeight: open ? 30 : 40,
          position: 'relative'
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 0,
            transition: '0.3s'
          }}
        >
          <img
            src="/BullVaan_Logo.png"
            alt="BullVaan"
            style={{
              width: open ? 140 : 90,
              height: open ? 140 : 90,
              objectFit: 'contain',
              transition: '0.3s',
              marginLeft: open ? -30 : -6,
              marginRight: open ? -35 : 0,
              marginTop: open ? -40 : -20,
              marginBottom: open ? -40 : -20
            }}
          />
          {open && (
            <span
              style={{
                fontWeight: 700,
                fontSize: 28,
                color: '#FFFFFF',
                letterSpacing: 1,
                whiteSpace: 'nowrap'
              }}
            >
              BullVaan
            </span>
          )}
        </div>
        <div
          onClick={() => setOpen(!open)}
          style={{
            cursor: 'pointer',
            color: '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            position: open ? 'static' : 'absolute',
            right: open ? 'auto' : 4,
            top: open ? 'auto' : '50%',
            transform: open ? 'none' : 'translateY(-50%)'
          }}
        >
          {open ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </div>
      </div>

      {/* Menu */}
      <div style={{ paddingTop: 10, flex: 1 }}>
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
              {open && <span style={{ fontSize: 18 }}>{item.name}</span>}
            </div>
          );
        })}
      </div>

      {/* Logout Button */}
      <div
        onClick={() => {
          localStorage.removeItem('auth');
          navigate('/');
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 18px',
          cursor: 'pointer',
          background: 'transparent',
          color: '#ef4444',
          borderLeft: '4px solid transparent',
          borderTop: '1px solid #334155',
          transition: '0.2s'
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#0f172a')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <span style={{ fontSize: 24 }}>🚪</span>
        {open && <span style={{ fontSize: 18 }}>Logout</span>}
      </div>
    </div>
  );
}
