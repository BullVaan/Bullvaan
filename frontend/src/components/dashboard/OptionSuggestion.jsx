import { useState, useEffect, useRef, useCallback } from 'react';
import { getAuthHeaders } from '../../utils/auth';
import { API_BASE_URL, getWsUrl } from '../../utils/api';

const API = API_BASE_URL;

export default function OptionSuggestion({
  signal,
  price,
  symbol,
  autoEnabled = false,
  tradingMode = 'paper'
}) {
  const [options, setOptions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(false);
  const [openTrade, setOpenTrade] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedLots, setSelectedLots] = useState(1);
  const wsRef = useRef(null);
  const lastRecommendationRef = useRef(null);

  const symbolConfig = {
    '^NSEI': { name: 'NIFTY 50', lotSize: 65, prefix: 'NIFTY' },
    '^NSEBANK': { name: 'BANK NIFTY', lotSize: 30, prefix: 'BANKNIFTY' },
    '^BSESN': { name: 'SENSEX', lotSize: 20, prefix: 'SENSEX' }
  };
  const config = symbolConfig[symbol] || {
    name: symbol,
    lotSize: 1,
    prefix: ''
  };
  const lotSize = config.lotSize;
  const totalQty = lotSize * selectedLots;

  const signalColor = {
    BUY: '#22c55e',
    SELL: '#ef4444',
    NEUTRAL: '#eab308',
    WAIT: '#eab308'
  };

  // ── Fetch open trade for THIS index (no polling) ──
  const fetchOpenTrade = useCallback(async () => {
    try {
      const res = await fetch(`${API}/trades/active`, {
        headers: getAuthHeaders()
      });
      const data = await res.json();
      const active = data.trades?.find(
        (t) =>
          t.name?.toUpperCase().startsWith(config.prefix) &&
          t.status === 'open' &&
          (t.mode || 'paper') === tradingMode
      );
      setOpenTrade(active || null);
    } catch {
      setOpenTrade(null);
    }
  }, [config.prefix, tradingMode]);

  useEffect(() => {
    fetchOpenTrade();
  }, [fetchOpenTrade]);

  // ── BUY action ──
  const handleBuy = async (optionName, buyPrice) => {
    setActionLoading(true);
    try {
      await fetch(`${API}/trades`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name: optionName,
          lot: selectedLots,
          quantity: totalQty,
          buy_price: buyPrice,
          sell_price: 0
        })
      });
      await fetchOpenTrade();
    } catch (e) {
      console.error('Buy failed', e);
    }
    setActionLoading(false);
  };

  // ── SELL action ──
  const handleSell = async (sellPrice) => {
    if (!openTrade) return;
    setActionLoading(true);
    try {
      const ist = new Date().toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Asia/Kolkata'
      });
      await fetch(`${API}/trades/${openTrade.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ sell_price: sellPrice, sell_time: ist })
      });
      setOpenTrade(null);
      await fetchOpenTrade();
    } catch (e) {
      console.error('Sell failed', e);
    }
    setActionLoading(false);
  };

  // ── WebSocket ──
  useEffect(() => {
    let reconnectTimer;
    const connect = () => {
      const ws = new WebSocket(getWsUrl('/ws/options'));
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ symbol }));
        setConnected(true);
        setError('');
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
          setError(data.error);
        } else {
          setOptions(data);
          setError('');
        }
        setLoading(false);
      };
      ws.onerror = () => setConnected(false);
      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Send new symbol on change (without reconnecting) ──
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ symbol }));
    }
  }, [symbol]);

  // ── Filter options ──
  const getFilteredOptions = () => {
    if (!options?.options) return { atm: null, otm: null };
    if (signal === 'NEUTRAL') {
      return {
        atm: options.options.find((o) => o.label === 'atm_ce'),
        otm: options.options.find((o) => o.label === 'atm_pe')
      };
    }
    const type = signal === 'BUY' ? 'CE' : 'PE';
    return {
      atm: options.options.find(
        (o) => o.label.startsWith('atm') && o.type === type
      ),
      otm: options.options.find(
        (o) => o.label.startsWith('otm') && o.type === type
      )
    };
  };

  const { atm, otm } = getFilteredOptions();
  const best = atm;
  const bestStrike = best?.strike;
  const bestType = best?.type;
  const bestLtp = best?.ltp;

  useEffect(() => {
    if (signal !== 'NEUTRAL' && bestStrike != null) {
      lastRecommendationRef.current = {
        signal,
        strike: bestStrike,
        type: bestType,
        ltp: bestLtp,
        symbol
      };
    }
  }, [signal, bestStrike, bestType, bestLtp, symbol]);

  const getOpenTradeLivePrice = () => {
    if (!openTrade || !options) return null;
    // Use dedicated open trade LTP from backend (correct even when ATM shifts)
    if (options.open_trade_ltp != null) return options.open_trade_ltp;
    // Fallback: match by exact strike and type from trade name
    if (!options.options) return null;
    const parts = openTrade.name?.split(' ');
    if (parts && parts.length >= 3) {
      const tradeStrike = parseFloat(parts[1]);
      const tradeType = parts[2];
      const match = options.options.find(
        (o) => o.strike === tradeStrike && o.type === tradeType
      );
      if (match) return match.ltp;
    }
    return null;
  };

  const formatExpiry = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  const tradeName = best ? `${config.prefix} ${best.strike} ${best.type}` : '';
  const hasPosition = !!openTrade;
  const livePrice = getOpenTradeLivePrice();

  // ══════════════════════════════════════════════════
  // RENDER — two tiles side by side
  // ══════════════════════════════════════════════════
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>
      {/* ════════ LEFT TILE: Options Card ════════ */}
      <div style={tileStyle}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 10,
            borderBottom: '1px solid #1e293b',
            paddingBottom: 8
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: '#64748b', letterSpacing: 1 }}>
              Signal
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 'bold',
                color: signalColor[signal] || '#eab308'
              }}
            >
              {signal}
            </div>
          </div>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#64748b' }}>Expiry</div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#f59e0b' }}>
              {options ? formatExpiry(options.expiry) : '—'}
            </div>
          </div>
          <div style={{ flex: 1, textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: '#64748b' }}>{config.name}</div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>
              ₹{Math.round(price)}
            </div>
          </div>
        </div>

        {/* Options rows */}
        {loading ? (
          <div style={{ textAlign: 'center', color: '#64748b', padding: 20 }}>
            Loading live options...
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', color: '#ef4444', padding: 20 }}>
            {error}
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {atm && (
                <OptionRow
                  label={signal === 'NEUTRAL' ? 'ATM' : 'ATM'}
                  strike={atm.strike}
                  type={atm.type}
                  ltp={atm.ltp}
                  color="#3b82f6"
                />
              )}
              {otm && (
                <OptionRow
                  label={signal === 'NEUTRAL' ? 'ATM' : 'OTM'}
                  strike={otm.strike}
                  type={otm.type}
                  ltp={otm.ltp}
                  color={signal === 'NEUTRAL' ? '#ef4444' : '#a855f7'}
                />
              )}
            </div>

            {/* Recommended + Live indicator */}
            {signal !== 'NEUTRAL' && best ? (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <div
                  style={{
                    fontSize: 9,
                    color: '#94a3b8',
                    letterSpacing: 1,
                    marginBottom: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: connected ? '#22c55e' : '#ef4444',
                      display: 'inline-block',
                      animation: connected ? 'pulse 1.5s infinite' : 'none'
                    }}
                  />
                  RECOMMENDED
                </div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 800,
                    color: signalColor[signal]
                  }}
                >
                  {config.prefix} {best.strike} {best.type}
                </div>
              </div>
            ) : (
              <>
                {/* NEUTRAL — wait box with live dot inside */}
                <div
                  style={{
                    marginTop: 8,
                    padding: '6px 10px',
                    background: 'rgba(234, 179, 8, 0.08)',
                    border: '2px solid #eab308',
                    borderRadius: 8,
                    textAlign: 'center',
                    boxShadow: '0 0 10px #eab30833'
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: '#eab308',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: connected ? '#22c55e' : '#ef4444',
                        display: 'inline-block',
                        animation: connected ? 'pulse 1.5s infinite' : 'none'
                      }}
                    />
                    ⏸ WAIT — NO CLEAR SIGNAL
                  </div>
                  <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                    Strategies are mixed. Avoid entry.
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* ════════ RIGHT TILE: Buy/Sell Action Card ════════ */}
      <div style={tileStyle}>
        {/* ── BUY/SELL signal: show action card ── */}
        {signal !== 'NEUTRAL' && best ? (
          <>
            {/* Recommended — only show when no open position */}
            {!hasPosition && (
              <div style={{ textAlign: 'center', marginBottom: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 800 }}>
                  {config.prefix} {best.strike} {best.type}
                </div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 800,
                    color: signalColor[signal],
                    marginTop: 4
                  }}
                >
                  ₹{best.ltp?.toFixed(2) || '—'}
                </div>
              </div>
            )}

            {/* Open position banner */}
            {hasPosition && (
              <div
                style={{
                  padding: '5px 8px',
                  marginBottom: 8,
                  background: 'rgba(245,158,11,0.08)',
                  border: '1px solid #f59e0b44',
                  borderRadius: 6,
                  textAlign: 'center'
                }}
              >
                <div
                  style={{ fontSize: 9, color: '#f59e0b', letterSpacing: 0.5 }}
                >
                  OPEN POSITION
                </div>
                <div
                  style={{ fontSize: 11, fontWeight: 700, color: '#e2e8f0' }}
                >
                  {openTrade.name} — Bought @ ₹
                  {Number(openTrade.buy_price).toFixed(2)}
                </div>
                {livePrice > 0 && (
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 800,
                      marginTop: 2,
                      color:
                        livePrice >= openTrade.buy_price ? '#22c55e' : '#ef4444'
                    }}
                  >
                    LTP ₹{livePrice.toFixed(2)}{' '}
                    <span style={{ fontSize: 10 }}>
                      ({livePrice >= openTrade.buy_price ? '+' : ''}₹
                      {(
                        (livePrice - openTrade.buy_price) *
                        (openTrade.quantity || openTrade.lot)
                      ).toFixed(2)}
                      )
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Lot selector + Total */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 0',
                borderTop: '1px solid #1e293b',
                borderBottom: '1px solid #1e293b'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div>
                  <div
                    style={{
                      fontSize: 9,
                      color: '#64748b',
                      letterSpacing: 0.5
                    }}
                  >
                    LOTS
                  </div>
                  <select
                    value={hasPosition ? openTrade.lot || 1 : selectedLots}
                    onChange={(e) => setSelectedLots(Number(e.target.value))}
                    disabled={hasPosition}
                    style={{
                      background: '#0f172a',
                      color: hasPosition ? '#475569' : '#e2e8f0',
                      border: '1px solid #334155',
                      borderRadius: 4,
                      padding: '4px 6px',
                      fontSize: 14,
                      fontWeight: 700,
                      cursor: hasPosition ? 'not-allowed' : 'pointer',
                      outline: 'none',
                      width: 50
                    }}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 9,
                      color: '#64748b',
                      letterSpacing: 0.5
                    }}
                  >
                    QTY
                  </div>
                  <div
                    style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}
                  >
                    {hasPosition
                      ? openTrade.quantity || openTrade.lot
                      : totalQty}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                {hasPosition && livePrice != null && livePrice > 0 ? (
                  (() => {
                    const qty = openTrade.quantity || openTrade.lot;
                    const pnl = (livePrice - openTrade.buy_price) * qty;
                    const isProfit = pnl >= 0;
                    return (
                      <>
                        <div
                          style={{
                            fontSize: 9,
                            color: '#64748b',
                            letterSpacing: 0.5
                          }}
                        >
                          P&L
                        </div>
                        <div
                          style={{
                            fontSize: 15,
                            fontWeight: 800,
                            color: isProfit ? '#22c55e' : '#ef4444'
                          }}
                        >
                          {isProfit ? '+' : ''}₹
                          {pnl.toLocaleString('en-IN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                          })}
                        </div>
                      </>
                    );
                  })()
                ) : (
                  <>
                    <div
                      style={{
                        fontSize: 9,
                        color: '#64748b',
                        letterSpacing: 0.5
                      }}
                    >
                      TOTAL COST
                    </div>
                    <div
                      style={{
                        fontSize: 15,
                        fontWeight: 800,
                        color: signalColor[signal]
                      }}
                    >
                      ₹
                      {best.ltp
                        ? (best.ltp * totalQty).toLocaleString('en-IN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                          })
                        : '—'}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* BUY + SELL buttons */}
            {autoEnabled && (
              <div
                style={{
                  textAlign: 'center',
                  padding: '6px 0',
                  fontSize: 11,
                  fontWeight: 700,
                  color: '#22c55e',
                  letterSpacing: 1
                }}
              >
                ⚡ AUTO TRADER ACTIVE
              </div>
            )}
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: autoEnabled ? 0 : 10
              }}
            >
              <button
                onClick={() => handleBuy(tradeName, best.ltp)}
                disabled={actionLoading || hasPosition || autoEnabled}
                title={
                  autoEnabled
                    ? 'Auto-trader is active'
                    : hasPosition
                      ? 'Sell existing position first'
                      : `Buy ${tradeName}`
                }
                style={{
                  flex: 1,
                  padding: '10px 0',
                  borderRadius: 6,
                  border: 'none',
                  background:
                    hasPosition || autoEnabled ? '#1e293b' : '#22c55e',
                  color: hasPosition || autoEnabled ? '#475569' : '#fff',
                  fontWeight: 800,
                  fontSize: 13,
                  cursor:
                    hasPosition || autoEnabled
                      ? 'not-allowed'
                      : actionLoading
                        ? 'wait'
                        : 'pointer',
                  opacity: actionLoading && !hasPosition ? 0.6 : 1
                }}
              >
                {actionLoading && !hasPosition ? 'PLACING...' : 'BUY'}
              </button>
              <button
                onClick={() => handleSell(livePrice || best.ltp)}
                disabled={actionLoading || !hasPosition || autoEnabled}
                title={
                  autoEnabled
                    ? 'Auto-trader is active'
                    : !hasPosition
                      ? 'No open position'
                      : 'Sell to exit'
                }
                style={{
                  flex: 1,
                  padding: '10px 0',
                  borderRadius: 6,
                  border: 'none',
                  background:
                    !hasPosition || autoEnabled ? '#1e293b' : '#ef4444',
                  color: !hasPosition || autoEnabled ? '#475569' : '#fff',
                  fontWeight: 800,
                  fontSize: 13,
                  cursor:
                    !hasPosition || autoEnabled
                      ? 'not-allowed'
                      : actionLoading
                        ? 'wait'
                        : 'pointer',
                  opacity: actionLoading && hasPosition ? 0.6 : 1
                }}
              >
                {actionLoading && hasPosition ? 'SELLING...' : 'SELL'}
              </button>
            </div>
          </>
        ) : /* ── NEUTRAL + open trade: sell only ── */
        signal === 'NEUTRAL' && hasPosition ? (
          <>
            <div style={{ textAlign: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 9, color: '#f59e0b', letterSpacing: 1 }}>
                OPEN POSITION
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 800,
                  color: '#e2e8f0',
                  marginTop: 4
                }}
              >
                {openTrade.name}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                Bought @ ₹{Number(openTrade.buy_price).toFixed(2)}
              </div>
              {livePrice && (
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    marginTop: 6,
                    color:
                      livePrice >= openTrade.buy_price ? '#22c55e' : '#ef4444'
                  }}
                >
                  LTP ₹{livePrice.toFixed(2)}{' '}
                  <span style={{ fontSize: 11 }}>
                    ({livePrice >= openTrade.buy_price ? '+' : ''}₹
                    {(
                      (livePrice - openTrade.buy_price) *
                      (openTrade.quantity || openTrade.lot)
                    ).toFixed(2)}
                    )
                  </span>
                </div>
              )}
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 0',
                borderTop: '1px solid #1e293b'
              }}
            >
              <div>
                <div style={{ fontSize: 9, color: '#64748b' }}>QTY</div>
                <div
                  style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}
                >
                  {openTrade.quantity || openTrade.lot}
                </div>
              </div>
              <button
                onClick={() => handleSell(livePrice || openTrade.buy_price)}
                disabled={actionLoading || autoEnabled}
                style={{
                  background: autoEnabled ? '#1e293b' : '#ef4444',
                  color: autoEnabled ? '#475569' : '#fff',
                  fontWeight: 800,
                  fontSize: 13,
                  padding: '8px 20px',
                  borderRadius: 6,
                  border: 'none',
                  cursor:
                    actionLoading || autoEnabled ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.6 : 1
                }}
              >
                {autoEnabled
                  ? 'AUTO'
                  : actionLoading
                    ? 'SELLING...'
                    : 'SELL TO EXIT'}
              </button>
            </div>
          </>
        ) : /* ── NEUTRAL + no trade + had prev signal: disabled ── */
        signal === 'NEUTRAL' &&
          !hasPosition &&
          lastRecommendationRef.current &&
          lastRecommendationRef.current.symbol === symbol ? (
          <div
            style={{
              textAlign: 'center',
              opacity: 0.4,
              filter: 'grayscale(0.5)'
            }}
          >
            <div
              style={{
                fontSize: 9,
                color: '#475569',
                letterSpacing: 1,
                marginBottom: 4
              }}
            >
              LAST SIGNAL — DISABLED
            </div>
            <div style={{ fontSize: 12, fontWeight: 800, color: '#475569' }}>
              {lastRecommendationRef.current.signal}{' '}
              {lastRecommendationRef.current.strike}{' '}
              {lastRecommendationRef.current.type}
            </div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 800,
                color: '#475569',
                marginTop: 4
              }}
            >
              ₹{lastRecommendationRef.current.ltp?.toFixed(2) || '—'}
            </div>
            <div style={{ fontSize: 10, color: '#475569', marginTop: 6 }}>
              No position. Cannot buy or sell.
            </div>
          </div>
        ) : (
          /* ── NEUTRAL + nothing: wait ── */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 800, color: '#eab308' }}>
              ⏸ WAIT
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 6 }}>
              No clear signal. Avoid entry.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function OptionRow({ label, strike, type, ltp, color }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '5px 8px',
        background: '#0f172a',
        borderRadius: 5,
        border: `1px solid ${color}`
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color,
            background: `${color}18`,
            padding: '1px 6px',
            borderRadius: 3,
            letterSpacing: 1
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700 }}>
          {strike} {type}
        </span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b' }}>
        ₹{ltp?.toFixed(2) || '—'}
      </div>
    </div>
  );
}

const tileStyle = {
  background: '#020617',
  border: '2px solid #334155',
  borderRadius: 10,
  padding: 14,
  width: 300,
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 0 15px rgba(0,0,0,0.4)'
};
