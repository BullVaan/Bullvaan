import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiCall } from '../utils/api';

const inputStyle = {
  width: '100%',
  padding: '13px 16px',
  borderRadius: 10,
  border: '1px solid #1e3a5f',
  background: 'rgba(15,23,42,0.8)',
  color: '#fff',
  fontSize: 15,
  outline: 'none',
  marginBottom: 14,
  boxSizing: 'border-box',
  transition: 'border 0.2s'
};

const ChartDecor = () => (
  <svg
    width="320"
    height="120"
    viewBox="0 0 320 120"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={{ opacity: 0.18 }}
  >
    <polyline
      points="0,90 40,70 80,80 120,40 160,55 200,20 240,35 280,15 320,25"
      stroke="#38bdf8"
      strokeWidth="2.5"
      fill="none"
    />
    <polyline
      points="0,100 40,95 80,105 120,75 160,85 200,60 240,70 280,50 320,55"
      stroke="#10b981"
      strokeWidth="1.5"
      fill="none"
    />
    {[40, 120, 200, 280].map((x) => (
      <g key={x}>
        <rect
          x={x - 5}
          y={50}
          width={10}
          height={25}
          rx={2}
          fill="#38bdf8"
          opacity="0.5"
        />
        <line
          x1={x}
          y1={40}
          x2={x}
          y2={85}
          stroke="#38bdf8"
          strokeWidth="1.5"
          opacity="0.5"
        />
      </g>
    ))}
    {[80, 160, 240].map((x) => (
      <g key={x}>
        <rect
          x={x - 5}
          y={65}
          width={10}
          height={20}
          rx={2}
          fill="#ef4444"
          opacity="0.4"
        />
        <line
          x1={x}
          y1={55}
          x2={x}
          y2={90}
          stroke="#ef4444"
          strokeWidth="1.5"
          opacity="0.4"
        />
      </g>
    ))}
  </svg>
);

function Signup() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignup = async () => {
    setMessage('');
    if (!email || !password || !passwordConfirm) {
      setMessage('All fields required');
      return;
    }
    if (password.length < 6) {
      setMessage('Password must be at least 6 characters');
      return;
    }
    if (password !== passwordConfirm) {
      setMessage('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      const data = await apiCall('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      setMessage(
        '✅ ' +
          data.message +
          ' Click the Sign In button below to login once your account is approved.'
      );
    } catch (err) {
      setMessage(err.message || 'Signup failed.');
    }
    setLoading(false);
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0a0f1e' }}>
      {/* Left brand panel */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          background:
            'linear-gradient(145deg, #0d1b35 0%, #0a1628 50%, #061020 100%)',
          padding: 48,
          position: 'relative',
          overflow: 'hidden',
          minWidth: 0
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: '15%',
            left: '10%',
            width: 220,
            height: 220,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(37,99,235,0.18) 0%, transparent 70%)',
            pointerEvents: 'none'
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: '10%',
            right: '5%',
            width: 280,
            height: 280,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(16,185,129,0.12) 0%, transparent 70%)',
            pointerEvents: 'none'
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 40,
            left: 0,
            right: 0,
            display: 'flex',
            justifyContent: 'center'
          }}
        >
          <ChartDecor />
        </div>
        <img
          src="/BullVaan_Logo.png"
          alt="BullVaan"
          style={{
            width: 90,
            marginBottom: 24,
            filter: 'drop-shadow(0 0 18px rgba(56,189,248,0.4))'
          }}
        />
        <h1
          style={{
            color: '#fff',
            fontSize: 36,
            fontWeight: 800,
            letterSpacing: 2,
            margin: 0
          }}
        >
          BullVaan
        </h1>
        <p
          style={{
            color: '#38bdf8',
            fontSize: 15,
            marginTop: 10,
            letterSpacing: 1,
            fontWeight: 500
          }}
        >
          Smart Trading. Real Insights.
        </p>
        <div
          style={{
            marginTop: 40,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            width: '100%',
            maxWidth: 300
          }}
        >
          {[
            ['📈', 'Live NSE/BSE signals'],
            ['⚡', 'Real-time options data'],
            ['🤖', 'Automated trading engine']
          ].map(([icon, text]) => (
            <div
              key={text}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                background: 'rgba(255,255,255,0.04)',
                borderRadius: 10,
                padding: '10px 16px',
                border: '1px solid rgba(56,189,248,0.1)'
              }}
            >
              <span style={{ fontSize: 18 }}>{icon}</span>
              <span style={{ color: '#94a3b8', fontSize: 14 }}>{text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right form panel */}
      <div
        style={{
          width: 420,
          minWidth: 320,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          background: '#0f172a',
          padding: '48px 40px',
          boxShadow: '-4px 0 40px rgba(0,0,0,0.5)'
        }}
      >
        <div style={{ width: '100%', maxWidth: 340 }}>
          <h2
            style={{
              color: '#fff',
              fontSize: 26,
              fontWeight: 700,
              marginBottom: 6,
              textAlign: 'center'
            }}
          >
            Create Account
          </h2>
          <p
            style={{
              color: '#64748b',
              fontSize: 14,
              marginBottom: 32,
              textAlign: 'center'
            }}
          >
            Sign up and get started with BullVaan
          </p>

          <label
            style={{
              color: '#94a3b8',
              fontSize: 13,
              fontWeight: 500,
              marginBottom: 6,
              display: 'block'
            }}
          >
            Email
          </label>
          <input
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            style={inputStyle}
          />

          <label
            style={{
              color: '#94a3b8',
              fontSize: 13,
              fontWeight: 500,
              marginBottom: 6,
              display: 'block'
            }}
          >
            Password
          </label>
          <input
            placeholder="Min. 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            style={inputStyle}
          />

          <label
            style={{
              color: '#94a3b8',
              fontSize: 13,
              fontWeight: 500,
              marginBottom: 6,
              display: 'block'
            }}
          >
            Confirm Password
          </label>
          <input
            placeholder="Re-enter password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            type="password"
            onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
            style={inputStyle}
          />

          <button
            onClick={handleSignup}
            disabled={loading || !email}
            style={{
              width: '100%',
              padding: '14px',
              marginTop: 8,
              background:
                loading || !email
                  ? '#1e3a5f'
                  : 'linear-gradient(90deg, #2563eb, #38bdf8)',
              border: 'none',
              color: 'white',
              borderRadius: 10,
              fontWeight: 700,
              fontSize: 16,
              cursor: loading || !email ? 'not-allowed' : 'pointer',
              boxShadow:
                loading || !email ? 'none' : '0 4px 14px rgba(37,99,235,0.4)',
              transition: 'all 0.2s',
              letterSpacing: 0.5
            }}
          >
            {loading ? 'Creating account...' : 'Create Account'}
          </button>

          {message && (
            <div
              style={{
                marginTop: 16,
                padding: '11px 14px',
                borderRadius: 8,
                background: message.includes('✅')
                  ? 'rgba(6,78,59,0.5)'
                  : 'rgba(127,29,29,0.5)',
                border: `1px solid ${message.includes('✅') ? '#10b981' : '#991b1b'}`,
                color: message.includes('✅') ? '#34d399' : '#f87171',
                fontSize: 13,
                textAlign: 'center'
              }}
            >
              {message}
              {message.includes('✅') && (
                <button
                  onClick={() => navigate('/login')}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: '10px',
                    marginTop: 12,
                    background: 'linear-gradient(90deg, #10b981, #34d399)',
                    border: 'none',
                    color: 'white',
                    borderRadius: 8,
                    fontWeight: 700,
                    fontSize: 14,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(16,185,129,0.3)'
                  }}
                >
                  Go to Sign In
                </button>
              )}
            </div>
          )}

          <p
            style={{
              color: '#475569',
              fontSize: 13,
              textAlign: 'center',
              marginTop: 32
            }}
          >
            Already have an account?{' '}
            <button
              onClick={() => navigate('/login')}
              style={{
                background: 'none',
                border: 'none',
                color: '#38bdf8',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                padding: 0,
                textDecoration: 'underline'
              }}
            >
              Sign In
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Signup;
