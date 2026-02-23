import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Landmark
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
    { name: 'Trades', path: '/trades', icon: <BarChart3 size={24} /> },
    {
      name: 'Stocks',
      path: '/swing-trade',
      icon: <Landmark size={24} />
    },
    { name: 'History', path: '/history', icon: <History size={24} /> },
    { name: 'Settings', path: '/settings', icon: <Settings size={24} /> }
  ];

  return (
    <div
      style={{
        width: open ? 240 : 80,
        background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)',
        height: '100vh',
        borderRight: '1px solid #334155',
        boxShadow: '2px 0 16px 0 rgba(20,30,60,0.12)',
        transition: '0.3s',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0
      }}
    >
      {/* Logo/Brand */}
      <div
        style={{
          padding: open ? '18px 8px 0px 0' : '10px 0px 0px 0',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: open ? 'space-between' : 'center',
          minHeight: open ? 40 : 50,
          position: 'relative',
          background: 'rgba(15,23,42,0.95)',
          boxShadow: open ? '0 2px 8px rgba(20,30,60,0.08)' : 'none'
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
              width: open ? 100 : 48,
              height: open ? 100 : 48,
              objectFit: 'contain',
              transition: '0.3s',
              marginLeft: open ? -10 : 0,
              marginRight: open ? -10 : 0,
              marginTop: open ? -10 : 0,
              marginBottom: open ? -10 : 0
            }}
          />
          {open && (
            <span
              style={{
                fontWeight: 700,
                fontSize: 22,
                color: '#FFFFFF',
                letterSpacing: 1,
                whiteSpace: 'nowrap',
                marginLeft: 6,
                textShadow: '0 2px 8px rgba(0,0,0,0.12)'
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
            color: '#38bdf8',
            background: '#1e293b',
            borderRadius: 20,
            padding: 4,
            display: 'flex',
            alignItems: 'center',
            position: open ? 'static' : 'absolute',
            right: open ? 'auto' : 4,
            top: open ? 'auto' : '50%',
            transform: open ? 'none' : 'translateY(-50%)',
            boxShadow: '0 2px 8px rgba(20,30,60,0.10)'
          }}
        >
          {open ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </div>
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
                background: active
                  ? 'linear-gradient(90deg,#1e293b 60%,#22c55e22 100%)'
                  : 'transparent',
                color: active ? '#22c55e' : '#cbd5f5',
                borderLeft: active
                  ? '4px solid #22c55e'
                  : '4px solid transparent',
                transition: '0.2s',
                borderRadius: 8,
                margin: '4px 6px',
                boxShadow: active ? '0 2px 8px #22c55e22' : 'none'
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background =
                  'linear-gradient(90deg,#1e293b 60%,#38bdf822 100%)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = active
                  ? 'linear-gradient(90deg,#1e293b 60%,#22c55e22 100%)'
                  : 'transparent')
              }
            >
              {item.icon}
              {open && <span style={{ fontSize: 18 }}>{item.name}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
