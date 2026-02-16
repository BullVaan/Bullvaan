import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SignalCard from '../components/SignalCard';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';
import MainLayout from '../layout/MainLayout';

function Dashboard() {
  const navigate = useNavigate();

  const [signals, setSignals] = useState([]);
  const [indices, setIndices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [loading, setLoading] = useState(true);
  const [consensus, setConsensus] = useState('NEUTRAL');
  const [price, setPrice] = useState('-');
  const [error, setError] = useState('');

  /* ---------- AUTH CHECK ---------- */
  useEffect(() => {
    const auth = localStorage.getItem('auth');
    if (!auth) navigate('/');
  }, [navigate]);

  /* ---------- LOAD INDICES ---------- */
  useEffect(() => {
    fetch('http://127.0.0.1:8000/indices')
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data === 'object') {
          setIndices(data);
        } else {
          setError('Invalid indices response');
        }
      })
      .catch(() => setError('Backend not running'));
  }, []);

  /* ---------- FETCH SIGNALS ---------- */
  const fetchSignals = async () => {
    try {
      setLoading(true);
      setError('');

      const res = await fetch(
        `http://127.0.0.1:8000/signals?symbol=${selectedSymbol}`
      );

      const data = await res.json();

      if (!data) {
        setError('No response from backend');
        return;
      }

      setSignals(Array.isArray(data.signals) ? data.signals : []);
      setConsensus(data.consensus || 'NEUTRAL');
      setPrice(data.price ?? '-');
    } catch {
      setError('Cannot connect to backend API');
    } finally {
      setLoading(false);
    }
  };

  /* ---------- AUTO REFRESH ---------- */
  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 500000);
    return () => clearInterval(interval);
  }, [selectedSymbol]);

  /* ---------- CONSENSUS COLOR ---------- */
  const consensusColor =
    consensus === 'BUY'
      ? '#22c55e'
      : consensus === 'SELL'
        ? '#ef4444'
        : '#eab308';

  return (
    <MainLayout>
      <div
        style={{
          background: '#020617',
          padding: 15,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid #334155'
        }}
      >
        <h2 style={{ margin: 0 }}>Bullvan Dashboard</h2>

        <MarketStatus />

        <button
          onClick={() => {
            localStorage.removeItem('auth');
            navigate('/');
          }}
          style={{
            padding: '8px 14px',
            background: '#dc2626',
            border: 'none',
            color: 'white',
            cursor: 'pointer',
            borderRadius: 6
          }}
        >
          Logout
        </button>
      </div>

      {/* MARKET STRIP */}
      <MarketTicker />

      {/* SELECT INDEX CARD */}
      <div style={{ textAlign: 'center', padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              background: '#020617',
              border: '1px solid #334155',
              padding: '14px 22px',
              borderRadius: 12,
              width: 280,
              boxShadow: '0 0 15px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>
              Select Index
            </div>

            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              style={{
                width: '100%',
                padding: 10,
                borderRadius: 8,
                background: '#020617',
                color: 'white',
                border: '1px solid #475569',
                fontSize: 16,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {Object.keys(indices).length === 0 ? (
                <option>Loading...</option>
              ) : (
                Object.entries(indices).map(([symbol, name]) => (
                  <option key={symbol} value={symbol}>
                    {name}
                  </option>
                ))
              )}
            </select>

            <div style={{ marginTop: 14, fontSize: 20, fontWeight: 'bold' }}>
              ₹ {price}
            </div>

            <div
              style={{
                marginTop: 4,
                fontWeight: 'bold',
                fontSize: 22,
                color: consensusColor
              }}
            >
              {consensus}
            </div>
          </div>
        </div>
      </div>

      {/* ERROR */}
      {error && (
        <div style={{ textAlign: 'center', color: 'red' }}>{error}</div>
      )}

      {/* LOADING */}
      {loading && (
        <div style={{ textAlign: 'center', marginTop: 30 }}>
          Loading signals...
        </div>
      )}

      {/* SIGNAL CARDS */}
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
          {signals.length === 0 ? (
            <div>No signals available</div>
          ) : (
            signals.map((item, index) => (
              <SignalCard
                key={index}
                name={item.name || 'Strategy'}
                signal={item.signal || 'NEUTRAL'}
              />
            ))
          )}
        </div>
      )}
    </MainLayout>
  );
}

export default Dashboard;
