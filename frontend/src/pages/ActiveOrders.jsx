import { useEffect, useState, useRef, useCallback } from 'react';
import { RefreshCw, AlertCircle } from 'lucide-react';
import { getAuthHeaders } from '../utils/auth';

const API = 'http://localhost:8000';

export default function ActiveOrders() {
  const [activeTrades, setActiveTrades] = useState([]);
  const [pnlByMode, setPnlByMode] = useState({ real: 0, paper: 0 });
  const [liveLtp, setLiveLtp] = useState({});
  const [selectedTab, setSelectedTab] = useState('paper');
  const [selectedDate, setSelectedDate] = useState('');
  const [displayDate, setDisplayDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sellingId, setSellingId] = useState(null);
  const wsRef = useRef(null);

  // Initialize with today's date
  useEffect(() => {
    const now = new Date();
    const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
    const todayStr = ist.toISOString().slice(0, 10);
    setSelectedDate(todayStr);
  }, []);

  // Fetch trades for selected date
  const fetchActiveTrades = useCallback(
    async (dateStr = selectedDate) => {
      try {
        setLoading(true);
        const url = dateStr
          ? `${API}/trades/active?date=${dateStr}`
          : `${API}/trades/active`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        const data = await res.json();
        const trades = data.trades || [];
        setActiveTrades(trades);
        setDisplayDate(data.date);
        setPnlByMode(data.pnl_by_mode || { real: 0, paper: 0 });

        setSelectedTab((prev) => {
          const realCount = trades.filter(
            (t) => (t.mode || 'paper') === 'real'
          ).length;
          const paperCount = trades.filter(
            (t) => (t.mode || 'paper') === 'paper'
          ).length;
          if (prev === 'real' && realCount === 0 && paperCount > 0)
            return 'paper';
          if (prev === 'paper' && paperCount === 0 && realCount > 0)
            return 'real';
          return prev;
        });

        setError('');
      } catch (err) {
        setError(`Failed to fetch trades: ${err.message}`);
      } finally {
        setLoading(false);
      }
    },
    [selectedDate]
  );

  // Sell an open trade at current LTP
  const sellTrade = async (trade) => {
    const ltp = liveLtp[trade.name];
    if (!ltp) {
      setError('LTP not available');
      return;
    }
    setSellingId(trade.id);
    try {
      const now = new Date();
      const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
      const sellTime = ist.toISOString().slice(11, 16);
      const res = await fetch(`${API}/trades/${trade.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ sell_price: ltp, sell_time: sellTime })
      });
      if (res.ok) {
        fetchActiveTrades(selectedDate);
      }
    } catch (e) {
      setError(`Failed to sell trade: ${e.message}`);
    }
    setSellingId(null);
  };

  // Initial fetch
  useEffect(() => {
    if (selectedDate) {
      fetchActiveTrades(selectedDate);
    }
  }, [selectedDate, fetchActiveTrades]);

  // Handle date change
  const handleDateChange = (e) => {
    setSelectedDate(e.target.value);
  };

  // Reset to today
  const resetToToday = () => {
    const now = new Date();
    const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
    const todayStr = ist.toISOString().slice(0, 10);
    setSelectedDate(todayStr);
  };

  // Get today's date string
  const getTodayStr = () => {
    const now = new Date();
    const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
    return ist.toISOString().slice(0, 10);
  };

  // WebSocket for live LTP
  useEffect(() => {
    if (activeTrades.length === 0) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setLiveLtp({});
      return;
    }

    const connect = () => {
      const wsHost =
        window.location.port === '3000'
          ? `${window.location.hostname}:8000`
          : window.location.host;
      const ws = new WebSocket(`ws://${wsHost}/ws/trades`);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setLiveLtp(data);
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        setTimeout(() => {
          if (
            activeTrades.length > 0 &&
            (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED)
          ) {
            connect();
          }
        }, 2000);
      };

      ws.onerror = () => ws.close();
    };

    if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
      connect();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [activeTrades]);

  // Filter trades by selected mode
  const filteredTrades = activeTrades.filter(
    (t) => (t.mode || 'paper') === selectedTab
  );

  const realCount = activeTrades.filter(
    (t) => (t.mode || 'paper') === 'real'
  ).length;
  const paperCount = activeTrades.filter(
    (t) => (t.mode || 'paper') === 'paper'
  ).length;

  // Calculate live total P&L for selected tab
  const calculateTotalPnl = () => {
    let total = 0;
    filteredTrades.forEach((trade) => {
      const isOpen = trade.status === 'open';
      if (isOpen) {
        const currentLtp = liveLtp[trade.name];
        if (currentLtp) {
          const unrealizedPnl =
            (currentLtp - trade.buy_price) * (trade.quantity || trade.lot);
          total += unrealizedPnl;
        }
      } else {
        total += trade.pnl || 0;
      }
    });
    return total;
  };

  const totalPnl = calculateTotalPnl();
  const totalPnlColor =
    totalPnl > 0 ? '#22c55e' : totalPnl < 0 ? '#ef4444' : '#64748b';

  return (
    <div
      style={{ width: '100%', maxWidth: 1200, margin: '0 auto', padding: 20 }}
    >
      {/* HEADER */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 700,
              margin: 0,
              color: '#ffffff'
            }}
          >
            Active Orders
          </h1>
          <p style={{ fontSize: 13, color: '#64748b', margin: '6px 0 0 0' }}>
            Monitor all trades
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="date"
            value={selectedDate}
            onChange={handleDateChange}
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: '#020617',
              color: '#ffffff',
              fontSize: 13,
              outline: 'none',
              cursor: 'pointer'
            }}
          />
          {selectedDate !== getTodayStr() && (
            <button
              onClick={resetToToday}
              title="Back to today"
              style={{
                background: '#334155',
                border: 'none',
                color: '#cbd5e1',
                cursor: 'pointer',
                fontSize: 12,
                padding: '6px 12px',
                borderRadius: 4,
                fontWeight: 600
              }}
            >
              ↻ Today
            </button>
          )}
          <button
            onClick={() => fetchActiveTrades(selectedDate)}
            disabled={loading}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: '#3b82f6',
              color: 'white',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              opacity: loading ? 0.6 : 1,
              fontSize: 13,
              fontWeight: 600
            }}
          >
            <RefreshCw
              size={16}
              style={{
                animation: loading ? 'spin 1s linear infinite' : 'none'
              }}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* ERROR MESSAGE */}
      {error && (
        <div
          style={{
            background: '#7f1d1d',
            border: '1px solid #991b1b',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: '#fca5a5'
          }}
        >
          <AlertCircle size={18} />
          <span style={{ fontSize: 13 }}>{error}</span>
        </div>
      )}

      {/* TABS */}
      <div
        style={{
          display: 'flex',
          gap: 2,
          marginBottom: 20,
          borderBottom: '1px solid #334155'
        }}
      >
        {[
          { id: 'real', label: 'Real Orders' },
          { id: 'paper', label: 'Paper Orders' }
        ].map((tab) => {
          const count = activeTrades.filter(
            (t) => (t.mode || 'paper') === tab.id
          ).length;
          const pnl = pnlByMode[tab.id] || 0;
          const pnlColor =
            pnl > 0 ? '#22c55e' : pnl < 0 ? '#ef4444' : '#64748b';

          return (
            <button
              key={tab.id}
              onClick={() => setSelectedTab(tab.id)}
              style={{
                padding: '12px 20px',
                border: 'none',
                background: 'transparent',
                color: selectedTab === tab.id ? '#22c55e' : '#64748b',
                borderBottom:
                  selectedTab === tab.id
                    ? '2px solid #22c55e'
                    : '2px solid transparent',
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: 600,
                transition: '0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 12
              }}
            >
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start'
                }}
              >
                <span>{tab.label}</span>
                <span
                  style={{
                    fontSize: 11,
                    color: pnlColor,
                    fontWeight: 700,
                    marginTop: 2,
                    fontFamily: 'monospace'
                  }}
                >
                  {pnl > 0 ? '+' : ''}
                  {pnl ? `₹${pnl.toFixed(2)}` : '₹0.00'} ({count})
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* LIVE PORTFOLIO P&L SUMMARY */}
      <div
        style={{
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          border: `2px solid ${totalPnl > 0 ? '#22c55e' : totalPnl < 0 ? '#ef4444' : '#334155'}`,
          borderRadius: 12,
          padding: '20px 24px',
          marginBottom: 20,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <div>
          <p
            style={{
              fontSize: 12,
              color: '#64748b',
              margin: 0,
              fontWeight: 600,
              letterSpacing: 0.5,
              textTransform: 'uppercase'
            }}
          >
            Portfolio P&L ({selectedTab === 'real' ? 'Real Mode' : 'Paper Mode'}
            )
          </p>
          <p
            style={{
              fontSize: 14,
              color: '#cbd5e1',
              margin: '4px 0 0 0',
              fontWeight: 500
            }}
          >
            {filteredTrades.length} active {selectedTab} trade
            {filteredTrades.length !== 1 ? 's' : ''} · Including{' '}
            {filteredTrades.filter((t) => t.status === 'open').length} open ·{' '}
            {filteredTrades.filter((t) => t.status === 'closed').length} closed
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p
            style={{
              fontSize: 12,
              color: '#64748b',
              margin: 0,
              fontWeight: 600,
              letterSpacing: 0.5
            }}
          >
            TOTAL P&L
          </p>
          <p
            style={{
              fontSize: 32,
              fontWeight: 800,
              margin: '4px 0 0 0',
              color: totalPnlColor,
              fontFamily: 'monospace'
            }}
          >
            {totalPnl > 0 ? '+' : ''}₹{totalPnl.toFixed(2)}
          </p>
          <p
            style={{
              fontSize: 11,
              color: totalPnlColor,
              margin: '2px 0 0 0',
              fontWeight: 700,
              opacity: 0.8
            }}
          >
            {totalPnl > 0
              ? '📈 Profit'
              : totalPnl < 0
                ? '📉 Loss'
                : '↔️ Neutral'}
          </p>
        </div>
      </div>

      {/* NO TRADES MESSAGE */}
      {filteredTrades.length === 0 ? (
        <div
          style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 10,
            padding: 40,
            textAlign: 'center',
            color: '#64748b'
          }}
        >
          <p style={{ margin: 0, fontSize: 14 }}>
            No {selectedTab} orders today
          </p>
          <p style={{ margin: '4px 0 0 0', fontSize: 12, color: '#475569' }}>
            Trades will appear here as they are executed
          </p>
        </div>
      ) : (
        /* TRADES TABLE */
        <div
          style={{
            background: '#020617',
            border: '1px solid #334155',
            borderRadius: 10,
            overflow: 'auto',
            maxHeight: 'calc(100vh - 280px)'
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
              <tr style={{ background: '#0f172a' }}>
                {[
                  'Trade',
                  'Lot',
                  'Qty',
                  'Buy Price',
                  'Exit Price',
                  'Entry Time',
                  'Exit Time',
                  'P&L',
                  'Status',
                  'Action'
                ].map((h, i) => (
                  <th
                    key={i}
                    style={{
                      padding: '12px 14px',
                      fontSize: 11,
                      color: '#64748b',
                      fontWeight: 600,
                      letterSpacing: 1,
                      textAlign: i === 0 ? 'left' : 'center',
                      borderBottom: '1px solid #1e293b'
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((trade) => {
                const isOpen = trade.status === 'open';
                const currentLtp = liveLtp[trade.name];
                const unrealizedPnl = currentLtp
                  ? (currentLtp - trade.buy_price) *
                    (trade.quantity || trade.lot)
                  : 0;
                const realizedPnl = trade.pnl || 0;
                const displayPnl = isOpen ? unrealizedPnl : realizedPnl;
                const pnlColor =
                  displayPnl > 0
                    ? '#22c55e'
                    : displayPnl < 0
                      ? '#ef4444'
                      : '#64748b';

                return (
                  <tr
                    key={trade.id}
                    style={{
                      borderBottom: '1px solid #1e293b',
                      opacity: isOpen ? 1 : 0.7
                    }}
                  >
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        fontWeight: 600,
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {trade.name}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center'
                      }}
                    >
                      {trade.lot}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center'
                      }}
                    >
                      {trade.quantity || trade.lot}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontFamily: 'monospace'
                      }}
                    >
                      ₹{Number(trade.buy_price).toFixed(2)}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontFamily: 'monospace',
                        fontWeight: 600
                      }}
                    >
                      {isOpen ? (
                        currentLtp ? (
                          <span
                            style={{
                              color:
                                currentLtp >= trade.buy_price
                                  ? '#22c55e'
                                  : '#ef4444'
                            }}
                          >
                            ₹{Number(currentLtp).toFixed(2)}
                          </span>
                        ) : (
                          <span style={{ color: '#f59e0b' }}>--</span>
                        )
                      ) : (
                        <span style={{ color: '#94a3b8' }}>
                          ₹{Number(trade.sell_price).toFixed(2)}
                        </span>
                      )}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        textAlign: 'center',
                        color: '#94a3b8'
                      }}
                    >
                      {trade.buy_time || '--'}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        textAlign: 'center',
                        color: '#94a3b8'
                      }}
                    >
                      {trade.sell_time || '--'}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontWeight: 700,
                        color: pnlColor,
                        fontFamily: 'monospace'
                      }}
                    >
                      {isOpen
                        ? currentLtp
                          ? `${unrealizedPnl >= 0 ? '+' : ''}₹${unrealizedPnl.toFixed(2)}`
                          : '--'
                        : `${realizedPnl > 0 ? '+' : ''}₹${realizedPnl.toFixed(2)}`}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        textAlign: 'center'
                      }}
                    >
                      <span
                        style={{
                          background: isOpen ? '#1e3a8a' : '#1e293b',
                          color: isOpen ? '#3b82f6' : '#64748b',
                          padding: '4px 10px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase'
                        }}
                      >
                        {isOpen ? 'Open' : 'Closed'}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        textAlign: 'center',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {isOpen && currentLtp ? (
                        <button
                          onClick={() => sellTrade(trade)}
                          disabled={sellingId === trade.id}
                          style={{
                            background: '#ef4444',
                            color: '#fff',
                            border: 'none',
                            padding: '6px 14px',
                            borderRadius: 5,
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: sellingId === trade.id ? 'wait' : 'pointer',
                            opacity: sellingId === trade.id ? 0.6 : 1
                          }}
                        >
                          {sellingId === trade.id ? '...' : 'SELL'}
                        </button>
                      ) : (
                        <span style={{ color: '#64748b', fontSize: 12 }}>
                          --
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
