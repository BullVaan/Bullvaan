import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';
import MainLayout from '../layout/MainLayout';

function Dashboard() {
  const navigate = useNavigate();
  const [indices, setIndices] = useState({});
  const [timeframes, setTimeframes] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [selectedTimeframe, setSelectedTimeframe] = useState('5m');
  const [loading, setLoading] = useState(true);
  const [consensus, setConsensus] = useState('NEUTRAL');
  const [price, setPrice] = useState('-');
  const [india_vix, setIndiaVix] = useState({
    value: '-',
    change: 0,
    change_pct: 0,
    prev_close: '-'
  });
  const [atr, setAtr] = useState('-');
  const [error, setError] = useState('');

  // Zerodha Option Price State
  const [zerodhaOptionInput, setZerodhaOptionInput] = useState('');
  const [zerodhaOptionPrice, setZerodhaOptionPrice] = useState(null);
  const [zerodhaOptionLoading, setZerodhaOptionLoading] = useState(false);
  const [zerodhaOptionError, setZerodhaOptionError] = useState('');

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

      // setSignals(Array.isArray(data.signals) ? data.signals : []);
      // setSignalsByRole(data.signals_by_role || {});
      setConsensus(data.consensus || 'NEUTRAL');
      setPrice(data.price ?? '-');
      setIndiaVix(
        data.india_vix || {
          value: '-',
          change: 0,
          change_pct: 0,
          prev_close: '-'
        }
      );
      setAtr(data.atr ?? '-');
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSymbol, selectedTimeframe]);

  /* ---------- CONSENSUS COLOR ---------- */
  const consensusColor =
    consensus === 'BUY'
      ? '#22c55e'
      : consensus === 'SELL'
        ? '#ef4444'
        : '#eab308';

  // Fetch Zerodha Option Price
  const fetchZerodhaOptionPrice = async () => {
    if (!zerodhaOptionInput.trim()) {
      setZerodhaOptionError(
        'Please enter a valid option (e.g. 25700 NIFTY CE)'
      );
      return;
    }
    setZerodhaOptionLoading(true);
    setZerodhaOptionError('');
    setZerodhaOptionPrice(null);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/zerodha-option-price?query=${encodeURIComponent(zerodhaOptionInput)}`
      );
      const data = await res.json();
      if (data.success && data.price) {
        setZerodhaOptionPrice(data.price);
      } else {
        setZerodhaOptionError(data.error || 'No price data');
      }
    } catch (e) {
      setZerodhaOptionError('Error fetching option price');
    } finally {
      setZerodhaOptionLoading(false);
    }
  };

  // Handle input change for option price
  const handleOptionInputChange = (e) => {
    setZerodhaOptionInput(e.target.value);
  };

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

          {/* India VIX Card */}
          {!loading && (
            <div
              style={{
                background: '#020617',
                border: '1px solid #334155',
                padding: '14px 22px',
                borderRadius: 12,
                width: 140,
                boxShadow: '0 0 15px rgba(0,0,0,0.4)',
                cursor: 'help',
                position: 'relative',
                group: 'hover'
              }}
              title="India VIX measures market fear/volatility. High VIX = more risk, use wider stops. Low VIX = stable market, tight stops work better."
            >
              <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
                📈 India VIX
              </div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: india_vix.change_pct > 0 ? '#ef4444' : '#10b981'
                }}
              >
                {india_vix.value}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: india_vix.change_pct > 0 ? '#ef4444' : '#10b981',
                  marginTop: 3
                }}
              >
                {india_vix.change_pct > 0 ? '↑' : '↓'} {india_vix.change} (
                {Math.abs(india_vix.change_pct)}%)
              </div>
              <div
                style={{
                  fontSize: 8,
                  color: '#64748b',
                  marginTop: 8,
                  lineHeight: 1.3
                }}
              >
                {india_vix.value > 20
                  ? '🔴 HIGH - Risk!'
                  : india_vix.value > 15
                    ? '🟡 MEDIUM'
                    : '🟢 LOW - Calm'}
              </div>
              <div
                style={{
                  fontSize: 8,
                  color: '#94a3b8',
                  marginTop: 6,
                  fontStyle: 'italic',
                  lineHeight: 1.2
                }}
              >
                Fear Gauge: 10-15=Safe, 15-25=Risky, 25+=Crisis
              </div>
            </div>
          )}

          {/* ATR Card */}
          {!loading && (
            <div
              style={{
                background: '#020617',
                border: '1px solid #334155',
                padding: '14px 22px',
                borderRadius: 12,
                width: 140,
                boxShadow: '0 0 15px rgba(0,0,0,0.4)',
                cursor: 'help'
              }}
              title="ATR shows expected daily price movement. Use ATR value to set Stop Loss (1x ATR) and Take Profit (2x ATR) levels."
            >
              <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
                ⚡ ATR (14)
              </div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: '#3b82f6'
                }}
              >
                {atr}
              </div>
              <div style={{ fontSize: 10, color: '#64748b', marginTop: 3 }}>
                points/day
              </div>
              <div
                style={{
                  fontSize: 8,
                  color: '#94a3b8',
                  marginTop: 8,
                  lineHeight: 1.2
                }}
              >
                🎯 Stop Loss: -{atr !== '-' ? Math.round(atr) : '?'} pts
              </div>
              <div
                style={{
                  fontSize: 8,
                  color: '#22c55e',
                  marginTop: 4,
                  lineHeight: 1.2
                }}
              >
                ✓ Target: +{atr !== '-' ? Math.round(atr * 2) : '?'} pts
              </div>
            </div>
          )}
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

      {/* ZERODHA OPTION PRICE UI */}
      <div
        style={{
          background: '#1e293b',
          border: '1px solid #334155',
          padding: '18px 28px',
          borderRadius: 16,
          width: 340,
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          margin: '24px auto',
          fontFamily: 'inherit',
          textAlign: 'center',
          position: 'relative'
        }}
      >
        <div
          style={{
            fontSize: 15,
            color: '#94a3b8',
            marginBottom: 10,
            fontWeight: 500
          }}
        >
          Zerodha Option Live Price
        </div>
        <input
          type="text"
          value={zerodhaOptionInput}
          onChange={handleOptionInputChange}
          placeholder="e.g. 25500 NIFTY CE 24FEB or NIFTY26FEB25550CE"
          style={{
            width: '80%',
            padding: 10,
            borderRadius: 8,
            background: '#1e293b',
            color: '#f1f5f9',
            border: '1px solid #475569',
            fontSize: 15,
            outline: 'none',
            marginBottom: 10,
            fontWeight: 500
          }}
          autoComplete="off"
        />
        <button
          onClick={fetchZerodhaOptionPrice}
          style={{
            padding: '8px 18px',
            background: '#2563eb',
            border: 'none',
            color: 'white',
            cursor: 'pointer',
            borderRadius: 8,
            fontWeight: 600,
            fontSize: 15,
            marginLeft: 12,
            transition: 'background 0.2s'
          }}
          disabled={zerodhaOptionLoading}
        >
          {zerodhaOptionLoading ? 'Fetching...' : 'Get Price'}
        </button>
        <div
          style={{
            fontSize: 18,
            color: '#22c55e',
            fontWeight: 700,
            marginTop: 10
          }}
        >
          {zerodhaOptionPrice !== null && `Live Price: ₹ ${zerodhaOptionPrice}`}
        </div>
        {zerodhaOptionError && (
          <div style={{ color: '#ef4444', marginTop: 6 }}>
            {zerodhaOptionError}
          </div>
        )}
      </div>
    </MainLayout>
  );
}

export default Dashboard;
