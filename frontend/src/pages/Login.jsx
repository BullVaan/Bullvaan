import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiCall } from '../utils/api';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiCall('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      // Store JWT token in localStorage (httpOnly cookie would be more secure in production)
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_id', data.user_id);
      localStorage.setItem('email', data.email);
      navigate('/dashboard');
    } catch (err) {
      if (err.message.includes('403')) {
        setError('Your account is pending admin approval.');
      } else {
        setError(err.message || 'Invalid credentials');
      }
    }
    setLoading(false);
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #0f172a 60%, #1e293b 100%)'
      }}
    >
      <div
        style={{
          background: 'rgba(30,41,59,0.95)',
          padding: 40,
          borderRadius: 18,
          width: 370,
          boxShadow: '0 8px 32px #0006',
          backdropFilter: 'blur(6px)'
        }}
      >
        <h2
          style={{
            textAlign: 'center',
            color: '#fff',
            marginBottom: 10,
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: 1
          }}
        >
          Sign In
        </h2>
        <p
          style={{
            textAlign: 'center',
            color: '#94a3b8',
            marginBottom: 28,
            fontSize: 15
          }}
        >
          Welcome back! Please login to your account.
        </p>
        <input
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{
            width: '100%',
            padding: 14,
            marginTop: 12,
            borderRadius: 10,
            border: '1px solid #334155',
            background: '#0f172a',
            color: '#fff',
            fontSize: 16,
            outline: 'none',
            marginBottom: 8,
            transition: 'border 0.2s'
          }}
        />
        <input
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{
            width: '100%',
            padding: 14,
            marginTop: 10,
            borderRadius: 10,
            border: '1px solid #334155',
            background: '#0f172a',
            color: '#fff',
            fontSize: 16,
            outline: 'none',
            marginBottom: 8,
            transition: 'border 0.2s'
          }}
        />
        <button
          onClick={handleLogin}
          disabled={loading}
          style={{
            width: '100%',
            padding: 14,
            marginTop: 18,
            background: 'linear-gradient(90deg,#2563eb,#38bdf8)',
            border: 'none',
            color: 'white',
            borderRadius: 10,
            fontWeight: 'bold',
            fontSize: 17,
            cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: '0 2px 8px #2563eb33',
            opacity: loading ? 0.7 : 1,
            transition: 'background 0.2s'
          }}
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>
        {error && (
          <div
            style={{
              color:
                error.includes('pending') || error.includes('approval')
                  ? '#fbbf24'
                  : '#f87171',
              background:
                error.includes('pending') || error.includes('approval')
                  ? '#78350f'
                  : '#7f1d1d',
              border: `1px solid ${error.includes('pending') || error.includes('approval') ? '#f59e0b' : '#991b1b'}`,
              padding: '12px 14px',
              borderRadius: '8px',
              marginTop: 14,
              textAlign: 'center',
              fontWeight: 500,
              fontSize: 13
            }}
          >
            {error}
          </div>
        )}
        <div style={{ textAlign: 'center', marginTop: 28 }}>
          <span style={{ color: '#94a3b8', fontSize: 15 }}>
            Don't have an account?
          </span>
          <button
            onClick={() => navigate('/signup')}
            style={{
              marginLeft: 8,
              background: 'none',
              border: 'none',
              color: '#38bdf8',
              fontSize: 15,
              cursor: 'pointer',
              textDecoration: 'underline',
              fontWeight: 'bold',
              padding: 0
            }}
          >
            Create New Account
          </button>
        </div>
      </div>
    </div>
  );
}

export default Login;
