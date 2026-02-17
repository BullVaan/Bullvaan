import { useEffect, useState, useRef } from 'react';

function MarketTicker() {
  const [ticker, setTicker] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = () => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket('ws://127.0.0.1:8000/ws/ticker');
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) setTicker(data);
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  };

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 20,
        padding: '10px 16px',
        background: '#0f172a',
        borderBottom: '1px solid #1e293b',
        flexWrap: 'wrap',
      }}
    >
      {/* Connection indicator */}
      <span
        title={connected ? 'Live' : 'Reconnecting...'}
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: connected ? '#22c55e' : '#ef4444',
          boxShadow: connected ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
          display: 'inline-block',
        }}
      />

      {ticker.length === 0 && (
        <span style={{ color: '#64748b', fontSize: 13 }}>
          Connecting to NSE...
        </span>
      )}

      {ticker.map((item) => {
        const up = item.change >= 0;
        const color =
          item.price == null ? '#64748b' : up ? '#22c55e' : '#ef4444';
        const arrow = up ? '▲' : '▼';

        return (
          <div
            key={item.symbol}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '6px 14px',
              background: '#1e293b',
              borderRadius: 8,
              minWidth: 220,
            }}
          >
            <span
              style={{ color: '#cbd5e1', fontWeight: 600, fontSize: 13 }}
            >
              {item.name}
            </span>

            {item.price != null ? (
              <>
                <span
                  style={{
                    color: '#f1f5f9',
                    fontWeight: 700,
                    fontSize: 15,
                    fontFamily: 'monospace',
                  }}
                >
                  ₹{item.price.toLocaleString('en-IN')}
                </span>
                <span style={{ color, fontSize: 12, fontWeight: 600 }}>
                  {arrow} {Math.abs(item.change)} ({Math.abs(item.change_pct)}%)
                </span>
              </>
            ) : (
              <span style={{ color: '#64748b', fontSize: 13 }}>—</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default MarketTicker;
