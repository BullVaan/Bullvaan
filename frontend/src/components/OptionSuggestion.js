import { useState, useEffect, useRef } from 'react';

export default function OptionSuggestion({ signal, price, symbol }) {
  const [options, setOptions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  const symbolConfig = {
    '^NSEI': { name: 'NIFTY 50' },
    '^NSEBANK': { name: 'BANK NIFTY' },
    '^BSESN': { name: 'SENSEX' }
  };
  const config = symbolConfig[symbol] || { name: symbol };

  const signalColor = {
    BUY: '#22c55e',
    SELL: '#ef4444',
    NEUTRAL: '#eab308',
    WAIT: '#eab308'
  };

  // WebSocket — open once, send new symbol on change
  useEffect(() => {
    let reconnectTimer;

    const connect = () => {
      const ws = new WebSocket('ws://127.0.0.1:8000/ws/options');
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

      ws.onerror = () => {
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent auto-reconnect on unmount
        wsRef.current.close();
      }
    };
  }, []);

  // Send new symbol when index changes (reuse existing connection)
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setLoading(true);
      wsRef.current.send(JSON.stringify({ symbol }));
    }
  }, [symbol]);

  // Filter options based on signal
  const getFilteredOptions = () => {
    if (!options?.options) return { atm: null, otm: null, atm2: null, otm2: null };
    if (signal === 'NEUTRAL') {
      // Show both CE and PE for NEUTRAL
      const atmCe = options.options.find((o) => o.label === 'atm_ce');
      const atmPe = options.options.find((o) => o.label === 'atm_pe');
      return { atm: atmCe, otm: atmPe, atm2: null, otm2: null };
    }
    const type = signal === 'BUY' ? 'CE' : 'PE';
    const atm = options.options.find(
      (o) => o.label.startsWith('atm') && o.type === type
    );
    const otm = options.options.find(
      (o) => o.label.startsWith('otm') && o.type === type
    );
    return { atm, otm, atm2: null, otm2: null };
  };

  const { atm, otm } = getFilteredOptions();

  // Determine best option (ATM for safer trade)
  const best = atm;

  const formatExpiry = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  return (
    <div style={containerStyle}>
      {/* HEADER */}
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

      {/* LIVE OPTIONS */}
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
          {/* ATM & OTM Rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {atm && (
              <OptionRow
                label={signal === 'NEUTRAL' ? 'CE' : 'ATM'}
                strike={atm.strike}
                type={atm.type}
                ltp={atm.ltp}
                color={signal === 'NEUTRAL' ? '#3b82f6' : '#3b82f6'}
              />
            )}
            {otm && (
              <OptionRow
                label={signal === 'NEUTRAL' ? 'PE' : 'OTM'}
                strike={otm.strike}
                type={otm.type}
                ltp={otm.ltp}
                color={signal === 'NEUTRAL' ? '#ef4444' : '#a855f7'}
              />
            )}
          </div>

          {/* RECOMMENDED / BEST — only for BUY or SELL */}
          {best && signal !== 'NEUTRAL' && (
            <div
              style={{
                marginTop: 8,
                padding: '6px 10px',
                background:
                  signal === 'BUY'
                    ? 'rgba(34, 197, 94, 0.08)'
                    : 'rgba(239, 68, 68, 0.08)',
                border: `2px solid ${signalColor[signal]}`,
                borderRadius: 8,
                textAlign: 'center',
                boxShadow: `0 0 10px ${signalColor[signal]}33`
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  color: '#94a3b8',
                  letterSpacing: 1,
                  marginBottom: 2
                }}
              >
                RECOMMENDED
              </div>
              <div style={{ fontSize: 12, fontWeight: 800 }}>
                BUY {best.strike} {best.type}
              </div>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 800,
                  color: signalColor[signal],
                  marginTop: 2
                }}
              >
                ₹{best.ltp?.toFixed(2) || '—'}
              </div>
            </div>
          )}

          {/* NEUTRAL — wait message */}
          {signal === 'NEUTRAL' && (
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
              <div style={{ fontSize: 12, fontWeight: 800, color: '#eab308' }}>
                ⏸ WAIT — NO CLEAR SIGNAL
              </div>
              <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                Strategies are mixed. Avoid entry.
              </div>
            </div>
          )}

          {/* Live indicator */}
          <div
            style={{
              marginTop: 10,
              fontSize: 10,
              color: connected ? '#22c55e' : '#ef4444',
              textAlign: 'center',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4
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
            {connected ? 'LIVE' : 'Reconnecting...'}
          </div>
        </>
      )}
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

const containerStyle = {
  background: '#020617',
  border: '2px solid #334155',
  borderRadius: 10,
  padding: 14,
  marginBottom: 14,
  width: 310,
  minHeight: 150,
  boxShadow: '0 0 15px rgba(0,0,0,0.4)'
};
