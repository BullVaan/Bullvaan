import { useNavigate, useLocation } from 'react-router-dom';
import { isAuthenticated, clearAccessToken } from '../utils/auth';

export default function AppBar() {
  const navigate = useNavigate();
  const location = useLocation();

  const authed = isAuthenticated();
  const email = localStorage.getItem('email') || '';
  const initial = email ? email[0].toUpperCase() : 'U';

  const homeTarget = authed ? '/dashboard' : '/';

  const navLinks = [
    { label: 'Home', path: homeTarget },
    { label: 'About Us', path: '/about' },
    { label: 'Contact Us', path: '/contact' }
  ];

  const isActive = (path) => {
    if (
      path === homeTarget &&
      (location.pathname === '/dashboard' || location.pathname === '/')
    )
      return true;
    return location.pathname === path;
  };

  return (
    <div
      style={{
        height: 60,
        background: '#0a0f1e',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        alignItems: 'center',
        padding: '0 28px',
        gap: 20,
        flexShrink: 0,
        boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
        zIndex: 100
      }}
    >
      {/* Brand */}
      <div
        onClick={() => navigate(homeTarget)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer'
        }}
      >
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #2563eb, #38bdf8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 900,
            fontSize: 18,
            color: '#fff'
          }}
        >
          B
        </div>
        <span
          style={{
            fontSize: 20,
            fontWeight: 800,
            background: 'linear-gradient(90deg, #38bdf8, #ffffff)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}
        >
          BullVaan
        </span>
      </div>

      {/* Nav links */}
      <nav style={{ display: 'flex', gap: 4, marginLeft: 28 }}>
        {navLinks.map(({ label, path }) => {
          const active = isActive(path);
          return (
            <button
              key={label}
              onClick={() => navigate(path)}
              style={{
                padding: '7px 18px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: active ? 600 : 500,
                color: active ? '#38bdf8' : '#94a3b8',
                cursor: 'pointer',
                border: 'none',
                background: active ? 'rgba(56,189,248,0.1)' : 'transparent',
                transition: 'all 0.15s'
              }}
            >
              {label}
            </button>
          );
        })}
      </nav>

      {/* Right side */}
      <div
        style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: 10
        }}
      >
        {authed ? (
          <>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #2563eb, #38bdf8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: 14,
                color: '#fff'
              }}
            >
              {initial}
            </div>
            <span style={{ fontSize: 13, color: '#64748b' }}>{email}</span>
            <button
              onClick={() => {
                clearAccessToken();
                navigate('/');
              }}
              style={{
                padding: '6px 16px',
                borderRadius: 7,
                border: '1px solid rgba(239,68,68,0.3)',
                background: 'rgba(239,68,68,0.05)',
                color: '#ef4444',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => navigate('/login')}
              style={{
                padding: '7px 20px',
                borderRadius: 8,
                border: '1px solid #334155',
                background: 'transparent',
                color: '#94a3b8',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Sign In
            </button>
            <button
              onClick={() => navigate('/signup')}
              style={{
                padding: '7px 20px',
                borderRadius: 8,
                border: 'none',
                background: 'linear-gradient(135deg, #2563eb, #38bdf8)',
                color: '#fff',
                fontSize: 13,
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Get Started →
            </button>
          </>
        )}
      </div>
    </div>
  );
}
