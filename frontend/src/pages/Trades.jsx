import { useEffect, useState, useRef } from 'react';
import { getAuthHeaders } from '../utils/auth';

const API = '';

export default function Trades() {
  const [trades, setTrades] = useState([]);
  const [totalPnl, setTotalPnl] = useState(0);
  const [tradeCount, setTradeCount] = useState(0);
  const [todayDate, setTodayDate] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [liveLtp, setLiveLtp] = useState({}); // { "NIFTY 25400 CE": 128.5 }
  const [sellingId, setSellingId] = useState(null); // trade id currently being sold
  const wsRef = useRef(null);
  const [form, setForm] = useState({
    name: '',
    lot: 1,
    buy_price: '',
    sell_price: '',
    buy_time: '',
    sell_time: ''
  });

  const fetchTrades = async (date) => {
    try {
      const url = date ? `${API}/trades?date=${date}` : `${API}/trades`;
      const res = await fetch(url, { headers: getAuthHeaders() });
      const data = await res.json();
      setTrades(data.trades || []);
      setTotalPnl(data.total_pnl || 0);
      setTradeCount(data.trade_count || 0);
      setTodayDate(data.date || '');
    } catch {
      console.error('Failed to fetch trades');
    }
  };

  // Fetch live LTP for open trades — NOT USED, kept for fallback
  // Real-time LTP comes via WebSocket below

  // Sell an open trade at the current live price
  const sellTrade = async (trade) => {
    const ltp = liveLtp[trade.name];
    if (!ltp) return;
    setSellingId(trade.id);
    try {
      const now = new Date();
      const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
      const sellTime = ist.toISOString().slice(11, 16);
      await fetch(`${API}/trades/${trade.id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ sell_price: ltp, sell_time: sellTime })
      });
      fetchTrades(filterDate || undefined);
    } catch (e) {
      console.error('Failed to sell trade', e);
    }
    setSellingId(null);
  };

  useEffect(() => {
    fetchTrades(filterDate || undefined);
  }, [filterDate]);

  // WebSocket: real-time LTP for open trades
  useEffect(() => {
    const hasOpen = trades.some((t) => t.status === 'open');
    if (!hasOpen) {
      // No open trades — close WS if open
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setLiveLtp({});
      return;
    }

    // Connect WebSocket
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
        // Reconnect after 2s if still has open trades
        setTimeout(() => {
          if (
            trades.some((t) => t.status === 'open') &&
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
  }, [trades]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API}/trades`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(form)
      });
      setForm({
        name: '',
        lot: 1,
        buy_price: '',
        sell_price: '',
        buy_time: '',
        sell_time: ''
      });
      setShowForm(false);
      fetchTrades(filterDate || undefined);
    } catch {
      console.error('Failed to add trade');
    }
  };

  const deleteTrade = async (id) => {
    try {
      await fetch(`${API}/trades/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      fetchTrades(filterDate || undefined);
    } catch {
      console.error('Failed to delete trade');
    }
  };

  const pnlColor =
    totalPnl > 0 ? '#22c55e' : totalPnl < 0 ? '#ef4444' : '#94a3b8';
  const pnlSign = totalPnl > 0 ? '+' : '';

  return (
    <div
      style={{ width: '100%', maxWidth: 1100, margin: '0 auto', padding: 20 }}
    >
      {/* DAY P&L HEADER */}
      <div
        style={{
          background: '#020617',
          border: '2px solid #334155',
          borderRadius: 12,
          padding: '20px 30px',
          marginBottom: 20,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <div>
          <div style={{ fontSize: 13, color: '#64748b', letterSpacing: 1 }}>
            {filterDate && filterDate !== todayDate ? 'P&L' : "TODAY'S P&L"}
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 800,
              color: pnlColor,
              fontFamily: 'monospace'
            }}
          >
            {pnlSign}₹
            {totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div
          style={{
            textAlign: 'right',
            display: 'flex',
            alignItems: 'center',
            gap: 10
          }}
        >
          <input
            type="date"
            value={filterDate}
            onChange={(e) => setFilterDate(e.target.value)}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: '#0f172a',
              color: 'white',
              fontSize: 13,
              outline: 'none',
              cursor: 'pointer'
            }}
          />
          {filterDate && (
            <button
              onClick={() => setFilterDate('')}
              title="Back to today"
              style={{
                background: '#334155',
                border: 'none',
                color: '#cbd5e1',
                cursor: 'pointer',
                fontSize: 11,
                padding: '4px 10px',
                borderRadius: 4,
                fontWeight: 600
              }}
            >
              ↻ Today
            </button>
          )}
          <div style={{ marginLeft: 5 }}>
            <div style={{ fontSize: 14, color: '#cbd5e1', fontWeight: 600 }}>
              {todayDate}
            </div>
            <div style={{ fontSize: 13, color: '#64748b', marginTop: 2 }}>
              {tradeCount} trade{tradeCount !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>

      {/* ADD TRADE BUTTON */}
      <div
        style={{
          marginBottom: 15,
          display: 'flex',
          justifyContent: 'flex-end'
        }}
      >
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            background: showForm ? '#334155' : '#3b82f6',
            color: 'white',
            border: 'none',
            padding: '8px 18px',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          {showForm ? '✕ Cancel' : '+ Add Trade'}
        </button>
      </div>

      {/* ADD TRADE FORM */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 10,
            padding: 20,
            marginBottom: 20,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: 12
          }}
        >
          <InputField
            label="Trade Name"
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            placeholder="NIFTY 25700 CE"
          />
          <InputField
            label="Lot"
            value={form.lot}
            onChange={(v) => setForm({ ...form, lot: v })}
            type="number"
          />
          <InputField
            label="Buy Price (₹)"
            value={form.buy_price}
            onChange={(v) => setForm({ ...form, buy_price: v })}
            type="number"
            step="0.05"
          />
          <InputField
            label="Sell Price (₹)"
            value={form.sell_price}
            onChange={(v) => setForm({ ...form, sell_price: v })}
            type="number"
            step="0.05"
            placeholder="Leave empty if open"
          />
          <InputField
            label="Buy Time (IST)"
            value={form.buy_time}
            onChange={(v) => setForm({ ...form, buy_time: v })}
            type="time"
          />
          <InputField
            label="Sell Time (IST)"
            value={form.sell_time}
            onChange={(v) => setForm({ ...form, sell_time: v })}
            type="time"
          />
          <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
            <button
              type="submit"
              style={{
                background: '#22c55e',
                color: '#000',
                border: 'none',
                padding: '10px 30px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Save Trade
            </button>
          </div>
        </form>
      )}

      {/* TRADES TABLE */}
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
                'Date',
                'Trade',
                'Lot',
                'Qty',
                'Buy Price',
                'Sell Price',
                'Total Price',
                'Buy Time',
                'Sell Time',
                'P/L (₹)',
                ''
              ].map((h, i) => (
                <th
                  key={i}
                  style={{
                    padding: '12px 14px',
                    fontSize: 11,
                    color: '#64748b',
                    fontWeight: 600,
                    letterSpacing: 1,
                    textAlign: i <= 1 ? 'left' : 'center',
                    borderBottom: '1px solid #1e293b'
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td
                  colSpan={11}
                  style={{
                    textAlign: 'center',
                    color: '#475569',
                    padding: 40,
                    fontSize: 14
                  }}
                >
                  No trades today. Click "+ Add Trade" to log one.
                </td>
              </tr>
            ) : (
              trades.map((t) => {
                const pnl = t.pnl || 0;
                const isOpen = t.status === 'open';
                const currentLtp = liveLtp[t.name];
                const livePnl =
                  isOpen && currentLtp
                    ? (currentLtp - t.buy_price) * (t.quantity || t.lot)
                    : 0;
                const rowPnlColor = isOpen
                  ? livePnl > 0
                    ? '#22c55e'
                    : livePnl < 0
                      ? '#ef4444'
                      : '#64748b'
                  : pnl > 0
                    ? '#22c55e'
                    : pnl < 0
                      ? '#ef4444'
                      : '#64748b';
                return (
                  <tr key={t.id} style={{ borderBottom: '1px solid #1e293b' }}>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        color: '#94a3b8',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {t.date || '—'}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        fontWeight: 600,
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {t.name}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center'
                      }}
                    >
                      {t.lot}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center'
                      }}
                    >
                      {t.quantity || t.lot}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontFamily: 'monospace'
                      }}
                    >
                      ₹{Number(t.buy_price).toFixed(2)}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontFamily: 'monospace'
                      }}
                    >
                      {isOpen ? (
                        currentLtp ? (
                          <span
                            style={{
                              color:
                                currentLtp >= t.buy_price
                                  ? '#22c55e'
                                  : '#ef4444',
                              fontWeight: 600
                            }}
                          >
                            ₹{Number(currentLtp).toFixed(2)}
                          </span>
                        ) : (
                          <span style={{ color: '#f59e0b', fontSize: 11 }}>
                            OPEN
                          </span>
                        )
                      ) : (
                        `₹${Number(t.sell_price).toFixed(2)}`
                      )}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontFamily: 'monospace',
                        color: '#f59e0b'
                      }}
                    >
                      ₹
                      {(
                        Number(t.buy_price) * (t.quantity || t.lot)
                      ).toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                      })}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        textAlign: 'center',
                        color: '#94a3b8'
                      }}
                    >
                      {t.buy_time || '—'}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 12,
                        textAlign: 'center',
                        color: '#94a3b8'
                      }}
                    >
                      {t.sell_time || '—'}
                    </td>
                    <td
                      style={{
                        padding: '10px 14px',
                        fontSize: 13,
                        textAlign: 'center',
                        fontWeight: 700,
                        color: rowPnlColor,
                        fontFamily: 'monospace'
                      }}
                    >
                      {isOpen
                        ? currentLtp
                          ? `${livePnl >= 0 ? '+' : ''}₹${livePnl.toFixed(2)}`
                          : '—'
                        : pnl !== 0
                          ? `${pnl > 0 ? '+' : ''}₹${pnl.toFixed(2)}`
                          : '—'}
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
                          onClick={() => sellTrade(t)}
                          disabled={sellingId === t.id}
                          style={{
                            background: '#ef4444',
                            color: '#fff',
                            border: 'none',
                            padding: '4px 12px',
                            borderRadius: 5,
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: sellingId === t.id ? 'wait' : 'pointer',
                            opacity: sellingId === t.id ? 0.6 : 1,
                            marginRight: 6
                          }}
                        >
                          {sellingId === t.id ? '...' : 'SELL'}
                        </button>
                      ) : null}
                      <button
                        onClick={() => deleteTrade(t.id)}
                        title="Delete trade"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#475569',
                          cursor: 'pointer',
                          fontSize: 14
                        }}
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
  step
}) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>
        {label}
      </div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        step={step}
        style={{
          width: '100%',
          padding: '8px 10px',
          borderRadius: 6,
          border: '1px solid #334155',
          background: '#020617',
          color: 'white',
          fontSize: 13,
          outline: 'none',
          boxSizing: 'border-box'
        }}
      />
    </div>
  );
}
