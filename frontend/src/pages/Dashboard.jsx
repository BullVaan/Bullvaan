import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RoleCard from '../components/common/RoleCard';
import OptionSuggestion from '../components/dashboard/OptionSuggestion';
import MarketTicker from '../components/dashboard/MarketTicker';
import MarketStatus from '../components/dashboard/MarketStatus';
import { getAuthHeaders } from '../utils/auth';
import { API_BASE_URL } from '../utils/api';

const BACKEND_URL = API_BASE_URL;

function Dashboard() {
  const navigate = useNavigate();

  const [signals_by_role, setSignalsByRole] = useState({});
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
  const [autoTrader, setAutoTrader] = useState({
    enabled: false,
    running: false
  });
  const [autoLoading, setAutoLoading] = useState(false);
  const [tradingMode, setTradingMode] = useState('paper'); // paper or real
  const [showModeWarning, setShowModeWarning] = useState(false);
  const [modeLoading, setModeLoading] = useState(false);
  /* ---------- AUTH CHECK ---------- */
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) navigate('/');
  }, [navigate]);

  /* ---------- LOAD INDICES & TIMEFRAMES ---------- */
  useEffect(() => {
    fetch(`${BACKEND_URL}/indices`, { headers: getAuthHeaders() })
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data === 'object') {
          setIndices(data);
        } else {
          setError('Invalid indices response');
        }
      })
      .catch(() => setError('Backend not running'));

    fetch(`${BACKEND_URL}/timeframes`, { headers: getAuthHeaders() })
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data === 'object') {
          setTimeframes(data);
        }
      })
      .catch((err) => console.log('Could not load timeframes'));
  }, []);

  /* ---------- FETCH SIGNALS ---------- */
  const fetchSignals = async () => {
    try {
      setLoading(true);
      setError('');

      const res = await fetch(
        `${BACKEND_URL}/signals?symbol=${selectedSymbol}&timeframe=${selectedTimeframe}`,
        { headers: getAuthHeaders() }
      );

      const data = await res.json();

      if (!data) {
        setError('No response from backend');
        return;
      }

      setSignalsByRole(data.signals_by_role || {});
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

  /* ---------- AUTO-TRADER ---------- */
  const fetchAutoStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/auto-trader/status`, {
        headers: getAuthHeaders()
      });
      const data = await res.json();
      setAutoTrader(data);
      setTradingMode(data.trading_mode || 'paper');
    } catch {
      /* ignore */
    }
  };

  const toggleAutoTrader = async () => {
    setAutoLoading(true);
    try {
      const endpoint = autoTrader.enabled_for_user ? 'stop' : 'start';
      const res = await fetch(`${BACKEND_URL}/auto-trader/${endpoint}`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await res.json();

      if (data.status === 'error' || data.detail) {
        alert(`❌ Error: ${data.detail || data.message}`);
      }

      await fetchAutoStatus();
    } catch (e) {
      console.error('Auto-trader toggle failed', e);
      alert(`❌ Auto-trader error: ${e.message}`);
    }
    setAutoLoading(false);
  };

  /* ---------- TRADING MODE TOGGLE ---------- */
  const initiateModeSwitchOp = (newMode) => {
    if (newMode === 'real' && autoTrader.enabled_for_user) {
      // Warn user that engine is running
      alert('Please stop the autotrader before switching to real money mode');
      return;
    }
    if (newMode === 'real') {
      setShowModeWarning(true);
    } else {
      confirmModeSwitch(newMode);
    }
  };

  const confirmModeSwitch = async (newMode) => {
    setModeLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/auto-trader/trading-mode`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mode: newMode })
      });
      const data = await res.json();

      console.log(
        'Mode switch response:',
        data,
        'Status from res:',
        res.status
      );

      if (data.status === 'ok') {
        setTradingMode(newMode);
        if (newMode === 'real') {
          const balance = data.account_balance
            ? `₹${data.account_balance}`
            : 'N/A';
          alert(`✓ Switched to REAL MONEY mode\nAvailable Balance: ${balance}`);
        } else {
          alert('✓ Switched back to PAPER TRADING mode');
        }
        await fetchAutoStatus();
      } else {
        const errorMsg =
          data.message ||
          data.error ||
          `Request failed with status: ${data.status}`;
        alert(`❌ Error: ${errorMsg}`);
      }
    } catch (e) {
      console.error('Mode switch error:', e);
      alert(`Error switching trading mode: ${e.message || 'Network error'}`);
    } finally {
      setShowModeWarning(false);
      setModeLoading(false);
    }
  };

  /* ---------- AUTO REFRESH ---------- */
  useEffect(() => {
    fetchSignals();
    fetchAutoStatus();
    const interval = setInterval(fetchSignals, 300000);
    return () => {
      clearInterval(interval);
    };
  }, [selectedSymbol, selectedTimeframe]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll auto-trader status only while engine is active
  useEffect(() => {
    if (!autoTrader.enabled_for_user) return;
    const autoInterval = setInterval(fetchAutoStatus, 3000);
    return () => clearInterval(autoInterval);
  }, [autoTrader.enabled_for_user]);

  /* ---------- CONSENSUS COLOR ---------- */
  const consensusColor =
    consensus === 'BUY'
      ? '#22c55e'
      : consensus === 'SELL'
        ? '#ef4444'
        : '#eab308';

  return (
    <div
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center'
      }}
    >
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
      <div
        style={{
          width: '100%',
          maxWidth: 1100,
          textAlign: 'center',
          padding: 20
        }}
      >
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
                  <div style={{ marginTop: 4 }}>
                    🎯 Target: 10-20 pts | SL: 10 pts
                  </div>
                </>
              )}
              {selectedTimeframe === '15m' && (
                <>
                  <div>📊 Hold 15-45 mins for trend</div>
                  <div style={{ marginTop: 4 }}>
                    🎯 Target: 30-50 pts | SL: 20 pts
                  </div>
                </>
              )}
              {selectedTimeframe === '30m' && (
                <>
                  <div>🔄 Swing-scalp, hold 30-90 mins</div>
                  <div style={{ marginTop: 4 }}>
                    🎯 Target: 50-100 pts | SL: 30 pts
                  </div>
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
      <div
        style={{
          width: '100%',
          display: loading ? 'none' : 'flex',
          justifyContent: 'center',
          gap: 20,
          padding: '0 30px',
          flexWrap: 'wrap'
        }}
      >
        <OptionSuggestion
          signal={consensus}
          price={parseFloat(price)}
          symbol={selectedSymbol}
          autoEnabled={autoTrader.enabled}
          tradingMode={tradingMode}
        />
      </div>

      {/* AUTO-TRADER CONTROL PANEL */}
      {!loading && (
        <div
          style={{
            width: '100%',
            maxWidth: 660,
            margin: '16px auto 0',
            padding: '14px 20px',
            background: autoTrader.enabled_for_user ? '#0a1628' : '#020617',
            border: `2px solid ${autoTrader.enabled_for_user ? '#22c55e' : '#334155'}`,
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            boxShadow: autoTrader.enabled_for_user
              ? '0 0 20px rgba(34,197,94,0.15)'
              : 'none'
          }}
        >
          {/* Left: Status info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: autoTrader.enabled_for_user ? '#22c55e' : '#475569',
                boxShadow: autoTrader.enabled_for_user
                  ? '0 0 8px #22c55e'
                  : 'none'
              }}
            />
            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: autoTrader.enabled_for_user ? '#22c55e' : '#94a3b8',
                  letterSpacing: 0.5
                }}
              >
                AUTO TRADER {autoTrader.enabled_for_user ? 'ACTIVE' : 'OFF'}
                {autoTrader.killed && (
                  <span style={{ color: '#ef4444', marginLeft: 8 }}>
                    KILLED
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                <span
                  style={{
                    color: tradingMode === 'real' ? '#dc2626' : '#94a3b8',
                    fontWeight: tradingMode === 'real' ? 700 : 400
                  }}
                >
                  {tradingMode === 'real' ? '🔴 REAL MONEY' : 'Paper Mode'}
                </span>
                • Capital: ₹
                {(
                  autoTrader.available_capital ??
                  autoTrader.capital ??
                  100000
                ).toLocaleString('en-IN')}
                {autoTrader.enabled_for_user && (
                  <>
                    {' '}
                    • Trades: {autoTrader.daily_trade_count || 0}/
                    {autoTrader.max_trades_per_day || 15}• P&L:{' '}
                    <span
                      style={{
                        color:
                          (autoTrader.daily_pnl || 0) >= 0
                            ? '#22c55e'
                            : '#ef4444',
                        fontWeight: 600
                      }}
                    >
                      {(autoTrader.daily_pnl || 0) >= 0 ? '+' : ''}₹
                      {(autoTrader.daily_pnl || 0).toFixed(2)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Right: Buttons */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* Mode Toggle */}
            <div
              style={{
                display: 'flex',
                gap: 4,
                background: '#0f172a',
                padding: 4,
                borderRadius: 6
              }}
            >
              <button
                onClick={() => initiateModeSwitchOp('paper')}
                disabled={modeLoading}
                style={{
                  padding: '6px 14px',
                  borderRadius: 4,
                  border: 'none',
                  fontWeight: 600,
                  fontSize: 11,
                  cursor: modeLoading ? 'wait' : 'pointer',
                  background:
                    tradingMode === 'paper' ? '#22c55e' : 'transparent',
                  color: tradingMode === 'paper' ? '#000' : '#94a3b8',
                  opacity: modeLoading ? 0.6 : 1,
                  transition: 'all 0.2s'
                }}
              >
                PAPER
              </button>
              <button
                onClick={() => initiateModeSwitchOp('real')}
                disabled={modeLoading}
                style={{
                  padding: '6px 14px',
                  borderRadius: 4,
                  border: 'none',
                  fontWeight: 600,
                  fontSize: 11,
                  cursor: modeLoading ? 'wait' : 'pointer',
                  background:
                    tradingMode === 'real' ? '#dc2626' : 'transparent',
                  color: tradingMode === 'real' ? '#fff' : '#94a3b8',
                  opacity: modeLoading ? 0.6 : 1,
                  transition: 'all 0.2s'
                }}
              >
                💰 REAL
              </button>
            </div>

            {/* Start/Stop Button */}
            <button
              onClick={toggleAutoTrader}
              disabled={autoLoading}
              style={{
                padding: '8px 20px',
                borderRadius: 8,
                border: 'none',
                fontWeight: 700,
                fontSize: 13,
                cursor: autoLoading ? 'wait' : 'pointer',
                background: autoTrader.enabled_for_user ? '#dc2626' : '#22c55e',
                color: '#fff',
                letterSpacing: 0.5,
                opacity: autoLoading ? 0.6 : 1
              }}
            >
              {autoLoading
                ? '...'
                : autoTrader.enabled_for_user
                  ? 'STOP'
                  : 'START'}
            </button>
          </div>
        </div>
      )}

      {/* REAL MONEY WARNING MODAL */}
      {showModeWarning && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '2px solid #dc2626',
              borderRadius: 12,
              padding: 32,
              maxWidth: 500,
              textAlign: 'center'
            }}
          >
            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: '#dc2626',
                marginBottom: 16
              }}
            >
              ⚠️ REAL MONEY MODE
            </div>
            <div
              style={{
                fontSize: 14,
                color: '#cbd5e1',
                lineHeight: 1.6,
                marginBottom: 24
              }}
            >
              <p>
                You are about to switch to <strong>REAL MONEY</strong> trading.
              </p>
              <p style={{ color: '#94a3b8', marginTop: 12 }}>
                • Trades will be executed on your real Kite account
                <br />• Only <strong>1 trade will be open at a time</strong> in
                real mode
                <br />
                • Available funds from your Kite account will be used
                <br />• You are responsible for all trades and losses
              </p>
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                onClick={() => setShowModeWarning(false)}
                disabled={modeLoading}
                style={{
                  padding: '10px 24px',
                  borderRadius: 8,
                  border: '1px solid #475569',
                  background: 'transparent',
                  color: '#cbd5e1',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: 13,
                  opacity: modeLoading ? 0.5 : 1
                }}
              >
                CANCEL
              </button>
              <button
                onClick={() => confirmModeSwitch('real')}
                disabled={modeLoading}
                style={{
                  padding: '10px 24px',
                  borderRadius: 8,
                  border: 'none',
                  background: '#dc2626',
                  color: '#fff',
                  fontWeight: 700,
                  cursor: modeLoading ? 'wait' : 'pointer',
                  fontSize: 13,
                  opacity: modeLoading ? 0.6 : 1
                }}
              >
                {modeLoading ? '...' : 'I UNDERSTAND - PROCEED'}
              </button>
            </div>
          </div>
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
