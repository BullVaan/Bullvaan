import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SignalCard from '../components/SignalCard';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';

function Dashboard() {
  const navigate = useNavigate();

  const [signals, setSignals] = useState([]);
  const [indices, setIndices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [loading, setLoading] = useState(true);
  const [signal, setSignal] = useState('NEUTRAL');
  const [confidence, setConfidence] = useState(0);
  const [price, setPrice] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    const auth = localStorage.getItem('auth');
    if (!auth) navigate('/');
  }, [navigate]);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/indices')
      .then((res) => res.json())
      .then((data) => setIndices(data))
      .catch(() => setError('Backend not running'));
  }, []);

  const fetchSignals = async () => {
    try {
      setLoading(true);
      setError('');

      const res = await fetch(
        `http://127.0.0.1:8000/signals?symbol=${selectedSymbol}`
      );

      const data = await res.json();

      if (data.error) {
        setError(data.error);
        return;
      }

      setSignals(data.signals);
      setSignal(data.signal);
      setConfidence(data.confidence);
      setPrice(data.price);
    } catch {
      setError('Cannot connect to backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 30000);
    return () => clearInterval(interval);
  }, [selectedSymbol]);

  const color =
    signal === 'BUY' ? '#22c55e' : signal === 'SELL' ? '#ef4444' : '#eab308';

  return (
    <div>
      {/* HEADER */}
      <div
        style={{
          background: '#020617',
          padding: 15,
          display: 'flex',
          justifyContent: 'space-between',
          borderBottom: '1px solid #334155'
        }}
      >
        <h2>Bullvan Dashboard</h2>

        <MarketStatus />

        <button
          onClick={() => {
            localStorage.removeItem('auth');
            navigate('/');
          }}
          style={{
            background: '#dc2626',
            color: 'white',
            padding: '8px 14px',
            border: 'none',
            borderRadius: 6
          }}
        >
          Logout
        </button>
      </div>

      <MarketTicker />

      {/* SELECT PANEL */}
      <div style={{ textAlign: 'center', padding: 25 }}>
        <select
          value={selectedSymbol}
          onChange={(e) => setSelectedSymbol(e.target.value)}
          style={{
            padding: 10,
            borderRadius: 8,
            background: '#020617',
            color: 'white',
            border: '1px solid #475569'
          }}
        >
          {Object.entries(indices).map(([symbol, name]) => (
            <option key={symbol} value={symbol}>
              {name}
            </option>
          ))}
        </select>

        <h2>₹ {price}</h2>

        <h1 style={{ color }}>{signal}</h1>

        {/* confidence */}
        <div style={{ width: 300, margin: 'auto' }}>
          <div
            style={{
              height: 8,
              background: '#1e293b',
              borderRadius: 5,
              overflow: 'hidden'
            }}
          >
            <div
              style={{
                width: `${confidence}%`,
                height: '100%',
                background: color,
                transition: '0.4s'
              }}
            />
          </div>

          <div style={{ marginTop: 5 }}>Confidence: {confidence}%</div>
        </div>
      </div>

      {/* ERROR */}
      {error && (
        <div style={{ color: 'red', textAlign: 'center' }}>{error}</div>
      )}

      {/* CARDS */}
      {!loading && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 15,
            justifyContent: 'center',
            padding: 30
          }}
        >
          {signals.map((item, i) => (
            <SignalCard key={i} name={item.name} signal={item.signal} />
          ))}
        </div>
      )}
    </div>
  );
}

export default Dashboard;
