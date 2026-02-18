import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SignalCard from '../components/SignalCard';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';
import LiveChart from '../components/LiveChart';

function Dashboard() {
  const navigate = useNavigate();

  const [signals, setSignals] = useState([]);
  const [indices, setIndices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [loading, setLoading] = useState(true);
  const [engineMode, setEngineMode] = useState('');
  const [signal, setSignal] = useState('NEUTRAL');
  const [confidence, setConfidence] = useState(0);
  const [price, setPrice] = useState(0);
  const [atr, setAtr] = useState(0);
  const [atrPercent, setAtrPercent] = useState(0);
  const [atrState, setAtrState] = useState('');
  const [structure, setStructure] = useState('');
  const [filtersPassed, setFiltersPassed] = useState(false);
  const [trendStrength, setTrendStrength] = useState(null);

  const [logs, setLogs] = useState([]);

  // AUTH CHECK
  useEffect(() => {
    if (!localStorage.getItem('auth')) navigate('/');
  }, [navigate]);

  // LOAD INDICES
  useEffect(() => {
    fetch('http://127.0.0.1:8000/indices')
      .then((r) => r.json())
      .then(setIndices);
  }, []);

  // FETCH SIGNALS
  const fetchSignals = async () => {
    try {
      setLoading(true);

      const res = await fetch(
        `http://127.0.0.1:8000/signals?symbol=${selectedSymbol}`
      );
      const data = await res.json();

      if (data.error) return;

      setSignals(data.signals);
      setSignal(data.signal);
      setConfidence(data.confidence);
      setPrice(data.price);
      setAtr(data.atr);

      setAtrPercent(data.atr_percent);
      setAtrState(data.atr_state);
      setStructure(data.market_structure);
      setFiltersPassed(data.filters_passed);
      setTrendStrength(data.trend_strength);
      setEngineMode(data.engine_mode);

      setLogs((prev) => [
        `${new Date().toLocaleTimeString()} → ${data.signal} (${data.confidence}%)`,
        ...prev.slice(0, 8)
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 30000);
    return () => clearInterval(interval);
  }, [selectedSymbol]);

  const signalColor =
    signal === 'BUY' ? '#22c55e' : signal === 'SELL' ? '#ef4444' : '#eab308';

  return (
    <div
      style={{
        background: '#020617',
        color: 'white',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* HEADER */}
      <div
        style={{
          padding: 12,
          display: 'flex',
          justifyContent: 'space-between',
          borderBottom: '1px solid #334155'
        }}
      >
        <h2>Bullvan Terminal</h2>
        <MarketStatus />
        <button
          onClick={() => {
            localStorage.removeItem('auth');
            navigate('/');
          }}
          style={{
            background: '#dc2626',
            border: 'none',
            padding: '8px 15px',
            borderRadius: 6,
            color: 'white'
          }}
        >
          Logout
        </button>
      </div>

      <MarketTicker />

      {/* MAIN AREA */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '200px 1fr 420px'
        }}
      >
        {/* SIDEBAR */}
        <div style={{ borderRight: '1px solid #334155', padding: 15 }}>
          <h3>Menu</h3>

          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            style={{
              width: '100%',
              padding: 10,
              borderRadius: 6,
              background: '#020617',
              color: 'white',
              border: '1px solid #475569'
            }}
          >
            {Object.entries(indices).map(([s, n]) => (
              <option key={s} value={s}>
                {n}
              </option>
            ))}
          </select>

          <div style={{ marginTop: 20 }}>
            <div>ATR</div>
            <b>{atr}</b>
            <div>{atrPercent}%</div>
          </div>

          <div style={{ marginTop: 20 }}>
            Structure: <b>{structure}</b>
          </div>

          <div style={{ marginTop: 20 }}>
            ADX: <b>{trendStrength}</b>
          </div>

          <div
            style={{
              marginTop: 20,
              color: filtersPassed ? '#22c55e' : '#ef4444'
            }}
          >
            Filters {filtersPassed ? 'PASS' : 'BLOCK'}
          </div>
        </div>

        {/* CENTER PANEL */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center'
          }}
        >
          <h1 style={{ fontSize: 50 }}>₹ {price}</h1>

          <h1 style={{ fontSize: 60, color: signalColor }}>{signal}</h1>

          <div
            style={{
              marginTop: 5,
              fontSize: 14,
              color: '#94a3b8',
              letterSpacing: 1
            }}
          >
            Mode: <b>{engineMode}</b>
          </div>

          {/* CONFIDENCE CENTER */}
          <div style={{ width: 400 }}>
            <div
              style={{
                height: 14,
                background: '#1e293b',
                borderRadius: 8,
                overflow: 'hidden'
              }}
            >
              <div
                style={{
                  width: `${confidence}%`,
                  height: '100%',
                  background: signalColor
                }}
              />
            </div>

            <h2 style={{ textAlign: 'center' }}>{confidence}% Confidence</h2>
          </div>
        </div>

        {/* RIGHT PANEL SIGNAL CARDS */}
        <div
          style={{
            borderLeft: '1px solid #334155',
            padding: 15,
            overflowY: 'auto'
          }}
        >
          <h3>Strategy Signals</h3>

          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
          >
            {loading
              ? 'Loading...'
              : signals.map((s, i) => (
                  <SignalCard key={i} name={s.name} signal={s.signal} />
                ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
