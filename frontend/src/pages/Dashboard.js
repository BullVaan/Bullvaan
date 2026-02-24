import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RoleCard from '../components/RoleCard';
import OptionSuggestion from '../components/OptionSuggestion';
import MarketTicker from '../components/MarketTicker';
import MarketStatus from '../components/MarketStatus';

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
  const [stopLossWarning, setStopLossWarning] = useState(false);
  const [price, setPrice] = useState('-');
  const [india_vix, setIndiaVix] = useState({
    value: '-',
    change: 0,
    change_pct: 0,
    prev_close: '-'
  });
  const [atr, setAtr] = useState('-');
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
      setStopLossWarning(data.stop_loss_warning || false);
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
  }, [selectedSymbol, selectedTimeframe]);

  /* ---------- CONSENSUS COLOR ---------- */
  const consensusColor =
    consensus === 'BUY'
      ? '#22c55e'
      : consensus === 'SELL'
        ? '#ef4444'
        : '#eab308';

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* HEADER - Market Status centered */}
      <div
        style={{
          width: '100%',
          background: '#020617',
          padding: 15,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          borderBottom: '1px solid #334155'
        }}
      >
        <MarketStatus />
      </div>

      {/* MARKET STRIP */}
      <div style={{ width: '100%' }}>
        <MarketTicker />
      </div>

      {/* SELECT INDEX & TIMEFRAME */}
      <div style={{ width: '100%', maxWidth: 1100, textAlign: 'center', padding: 20 }}>
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
            <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
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

            {stopLossWarning && consensus !== 'NEUTRAL' && (
              <div
                style={{
                  marginTop: 6,
                  padding: '4px 10px',
                  background: '#fbbf24',
                  color: '#000',
                  fontSize: 12,
                  fontWeight: 'bold',
                  borderRadius: 4,
                  display: 'inline-block'
                }}
              >
                ⚠️ USE STOP LOSS
              </div>
            )}
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
            <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
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
                marginTop: 10,
                fontSize: 14,
                color: '#94a3b8',
                lineHeight: 1.4
              }}
            >
              {selectedTimeframe === '5m' && (
                <>
                  <div>⚡ Quick entries, exit in 5-15 mins</div>
                  <div style={{ marginTop: 4 }}>🎯 Target: 10-20 pts | SL: 10 pts</div>
                </>
              )}
              {selectedTimeframe === '15m' && (
                <>
                  <div>📊 Hold 15-45 mins for trend</div>
                  <div style={{ marginTop: 4 }}>🎯 Target: 30-50 pts | SL: 20 pts</div>
                </>
              )}
              {selectedTimeframe === '30m' && (
                <>
                  <div>🔄 Swing-scalp, hold 30-90 mins</div>
                  <div style={{ marginTop: 4 }}>🎯 Target: 50-100 pts | SL: 30 pts</div>
                </>
              )}
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
              <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
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
                  fontSize: 14,
                  color: india_vix.change_pct > 0 ? '#ef4444' : '#10b981',
                  marginTop: 3
                }}
              >
                {india_vix.change_pct > 0 ? '↑' : '↓'} {india_vix.change} (
                {Math.abs(india_vix.change_pct)}%)
              </div>
              <div
                style={{
                  fontSize: 13,
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
                  fontSize: 12,
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
              <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
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
              <div style={{ fontSize: 13, color: '#64748b', marginTop: 3 }}>
                points/day
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: '#94a3b8',
                  marginTop: 8,
                  lineHeight: 1.2
                }}
              >
                🎯 Stop Loss: -{atr !== '-' ? Math.round(atr) : '?'} pts
              </div>
              <div
                style={{
                  fontSize: 13,
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

      {/* OPTION SUGGESTION CARDS */}
      {!loading && (
        <div style={{ 
          width: '100%', 
          display: 'flex', 
          justifyContent: 'center', 
          gap: 20,
          padding: '0 30px',
          flexWrap: 'wrap'
        }}>
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
            width: '100%',
            maxWidth: 1050,
            display: 'flex',
            flexWrap: 'nowrap',
            gap: 12,
            justifyContent: 'center',
            alignItems: 'stretch',
            padding: '20px 15px',
            overflowX: 'auto'
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
    </div>
  );
}

export default Dashboard;
