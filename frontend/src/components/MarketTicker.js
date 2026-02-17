import { useEffect, useState, useRef } from 'react';

// Marquee animation CSS
const marqueeStyles = `
@keyframes marquee {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
`;

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

  // Duplicate ticker data for seamless loop
  const tickerItems = [...ticker, ...ticker];

  return (
    <>
      <style>{marqueeStyles}</style>
      <div
        style={{
          overflow: 'hidden',
          overflowX: 'hidden',
          maxWidth: '100vw',
          background: '#0f172a',
          borderBottom: '1px solid #1e293b',
          padding: '10px 0',
          position: 'relative',
        }}
      >
        {/* Connection indicator - fixed position */}
        <span
          title={connected ? 'Live' : 'Reconnecting...'}
          style={{
            position: 'absolute',
            left: 10,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
            boxShadow: connected ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
            zIndex: 10,
          }}
        />

        {ticker.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13 }}>
            Connecting to NSE...
          </div>
        ) : (
          /* Scrolling marquee container */
          <div
            style={{
              display: 'flex',
              animation: 'marquee 20s linear infinite',
              width: 'fit-content',
            }}
          >
            {tickerItems.map((item, idx) => {
              const up = item.change >= 0;
              const color =
                item.price == null ? '#64748b' : up ? '#22c55e' : '#ef4444';
              const arrow = up ? '▲' : '▼';

              return (
                <div
                  key={`${item.symbol}-${idx}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 24px',
                    marginRight: 30,
                    background: '#1e293b',
                    borderRadius: 8,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span
                    style={{ color: '#cbd5e1', fontWeight: 600, fontSize: 16 }}
                  >
                    {item.name}
                  </span>

                  {item.price != null ? (
                    <>
                      <span
                        style={{
                          color: '#f1f5f9',
                          fontWeight: 700,
                          fontSize: 18,
                          fontFamily: 'monospace',
                        }}
                      >
                        ₹{item.price.toLocaleString('en-IN')}
                      </span>
                      <span style={{ color, fontSize: 15, fontWeight: 600 }}>
                        {arrow} {Math.abs(item.change)} ({Math.abs(item.change_pct)}%)
                      </span>
                    </>
                  ) : (
                    <span style={{ color: '#64748b', fontSize: 16 }}>—</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

export default MarketTicker;
