import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RoleCard from '../components/RoleCard';
import OptionSuggestion from '../components/OptionSuggestion';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';
import MainLayout from '../layout/MainLayout';

function Dashboard() {
  const navigate = useNavigate();

  const [signals, setSignals] = useState([]);
  const [signals_by_role, setSignalsByRole] = useState({});
  const [indices, setIndices] = useState({});
  const [timeframes, setTimeframes] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [selectedTimeframe, setSelectedTimeframe] = useState('5m');
  const [loading, setLoading] = useState(true);
  const [consensus, setConsensus] = useState('NEUTRAL');
  const [price, setPrice] = useState('-');
  const [error, setError] = useState('');

  /* ---------- AUTH CHECK ---------- */
  useEffect(() => {
    const auth = localStorage.getItem('auth');
    if (!auth) navigate('/');
  }, [navigate]);

  /* ---------- LOAD INDICES & TIMEFRAMES ---------- */
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

    fetch('http://127.0.0.1:8000/timeframes')
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data === 'object') {
          setTimeframes(data);
        }
      })
      .catch((err) => console.log('Could not load timeframes'));
  }, []);

  /* ---------- FETCH SIGNALS ---------- */
  const fetchSignals = async (symbol) => {
    try {
      setLoading(true);
      setError('');

      const res = await fetch(
        `http://127.0.0.1:8000/signals?symbol=${selectedSymbol}&timeframe=${selectedTimeframe}`
      );

      const data = await res.json();

      if (!data) {
        setError('No response from backend');
        return;
      }

      setSignals(Array.isArray(data.signals) ? data.signals : []);
      setSignalsByRole(data.signals_by_role || {});
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
    fetchSignals(selectedSymbol);
    const interval = setInterval(() => fetchSignals(selectedSymbol), 300000);
    return () => clearInterval(interval);
  }, [selectedSymbol, selectedTimeframe]);

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
        <div style={{ width: 80 }} />
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
            borderRadius: 6,
            flexShrink: 0
          }}
        >
          Logout
        </button>
      </div>

      {/* MARKET STRIP */}
      <MarketTicker />

      {/* SELECT INDEX & TIMEFRAME */}
      <div style={{ textAlign: 'center', padding: 20 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 15,
            flexWrap: 'wrap'
          }}
        >
          {/* Index Selector */}
          <div
            style={{
              background: '#020617',
              border: '1px solid #334155',
              padding: '14px 22px',
              borderRadius: 12,
              width: 250,
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
                fontSize: 14,
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

            <div style={{ marginTop: 12, fontSize: 18, fontWeight: 'bold' }}>
              ₹ {price}
            </div>

            <div
              style={{
                marginTop: 4,
                fontWeight: 'bold',
                fontSize: 20,
                color: consensusColor
              }}
            >
              {consensus}
            </div>
          </div>

          {/* Timeframe Selector */}
          <div
            style={{
              background: '#020617',
              border: '1px solid #334155',
              padding: '14px 22px',
              borderRadius: 12,
              width: 250,
              boxShadow: '0 0 15px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>
              Scalping Timeframe
            </div>

            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              style={{
                width: '100%',
                padding: 10,
                borderRadius: 8,
                background: '#020617',
                color: 'white',
                border: '1px solid #475569',
                fontSize: 14,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {Object.keys(timeframes).length === 0 ? (
                <option>Loading...</option>
              ) : (
                Object.entries(timeframes).map(([tf, config]) => (
                  <option key={tf} value={tf}>
                    {tf} - {config.description}
                  </option>
                ))
              )}
            </select>

            <div
              style={{
                marginTop: 12,
                fontSize: 12,
                color: '#cbd5e1',
                lineHeight: 1.5
              }}
            >
              <div>📊 {selectedTimeframe} Scalping</div>
              <div style={{ marginTop: 4, fontSize: 11 }}>
                {timeframes[selectedTimeframe]?.description}
              </div>
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

      {/* OPTION SUGGESTION CARD */}
      {!loading && consensus !== 'NEUTRAL' && (
        <div style={{ padding: '0 30px' }}>
          <OptionSuggestion
            signal={consensus}
            price={parseFloat(price)}
            symbol={selectedSymbol}
          />
        </div>
      )}

      {/* SIGNAL CARDS BY ROLE */}
      {!loading && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'nowrap',
            gap: 12,
            justifyContent: 'center',
            alignItems: 'stretch',
            padding: '20px 15px',
            overflowX: 'auto',
            maxWidth: '1050px',
            margin: '0 auto'
          }}
        >
          {!signals_by_role || Object.keys(signals_by_role).length === 0 ? (
            <div>No signals available</div>
          ) : (
            Object.entries(signals_by_role).map(([role, indicators]) => (
              <RoleCard key={role} role={role} indicators={indicators} />
            ))
          )}
        </div>
      )}
    </MainLayout>
  );
}

export default Dashboard;
