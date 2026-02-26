import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Signup() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignup = async () => {
    setMessage('');
    setLoading(true);
    try {
      const res = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok) {
        setMessage(data.message);
        setEmail('');
        setTimeout(() => {
          navigate('/');
        }, 2000);
      } else {
        setMessage(data.detail || 'Signup failed.');
      }
    } catch {
      setMessage('Signup failed.');
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
          Create Account
        </h2>
        <p
          style={{
            textAlign: 'center',
            color: '#94a3b8',
            marginBottom: 28,
            fontSize: 15
          }}
        >
          Enter your email to request access. Admin will share your password.
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
        <button
          onClick={handleSignup}
          disabled={loading || !email}
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
          {loading ? 'Signing up...' : 'Signup'}
        </button>
        {message && (
          <div
            style={{
              marginTop: 14,
              color: '#38bdf8',
              textAlign: 'center',
              fontWeight: 500
            }}
          >
            {message}
          </div>
        )}
        <div style={{ textAlign: 'center', marginTop: 28 }}>
          <span style={{ color: '#94a3b8', fontSize: 15 }}>
            Already have an account?
          </span>
          <button
            onClick={() => navigate('/')}
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
            Sign In
          </button>
        </div>
      </div>
    </div>
  );
}

export default Signup;
