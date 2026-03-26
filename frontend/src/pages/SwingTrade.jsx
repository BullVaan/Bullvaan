import { useEffect, useState } from 'react';
import StockModal from '../components/common/StockModal';
import PremarketSignals from '../components/swingTrade/PremarketSignals';

export default function SwingTrade() {
  const [stocks, setStocks] = useState([]);
  const [sector, setSector] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('percentChange');
  const [sortDir, setSortDir] = useState('desc');
  const [selectedStock, setSelectedStock] = useState(null);

  /* ---------------- WS LIVE DATA ---------------- */
  useEffect(() => {
    const wsHost =
      window.location.port === '3000'
        ? `${window.location.hostname}:8000`
        : window.location.host;
    const ws = new WebSocket(`ws://${wsHost}/ws/nifty50`);

    ws.onmessage = (e) => {
      const res = JSON.parse(e.data);
      setStocks(res.data);
      setSector(res.sector);
    };

    return () => ws.close();
  }, []);

  /* ---------------- FILTER ---------------- */
  const filtered = stocks.filter((s) =>
    s.symbol.toLowerCase().includes(search.toLowerCase())
  );

  /* ---------------- SORT ---------------- */
  const sorted = [...filtered].sort((a, b) => {
    return sortDir === 'asc' ? a[sortBy] - b[sortBy] : b[sortBy] - a[sortBy];
  });

  const toggleSort = (key) => {
    if (sortBy === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
  };

  /* ---------------- STATS ---------------- */
  const advancers = stocks.filter((s) => s.percentChange > 0).length;
  const decliners = stocks.length - advancers;

  /* ---------------- HELPERS ---------------- */
  const percentColor = (val) => {
    if (val > 0) return '#22c55e';
    if (val < 0) return '#ef4444';
    return '#94a3b8';
  };

  const volSignalColor = (sig) => {
    if (sig === 'EXPLOSION') return '#22c55e';
    if (sig === 'SPIKE') return '#3b82f6';
    if (sig === 'NORMAL') return '#eab308';
    return '#64748b';
  };

  const volTrendColor = (t) => {
    if (t === '↑') return '#22c55e';
    if (t === '↓') return '#ef4444';
    return '#eab308';
  };

  const badge = (type) => {
    if (type === 'BREAKOUT') return '🚀';
    if (type === 'BREAKDOWN') return '🔻';
    return '';
  };

  const momentumLabel = (m) => {
    if (m > 80) return { text: 'STRONG', color: '#22c55e' };
    if (m > 60) return { text: 'GOOD', color: '#3b82f6' };
    if (m > 40) return { text: 'WEAK', color: '#eab308' };
    return { text: 'SLOW', color: '#64748b' };
  };

  const tradeSignal = (s) => {
    if (s.breakout === 'BREAKOUT' && s.momentum > 70) return 'BUY CALL';
    if (s.breakout === 'BREAKDOWN' && s.momentum > 70) return 'BUY PUT';
    return 'WATCH';
  };

  /* ---------------- UI ---------------- */
  return (
    <div style={{ padding: 24, color: 'white' }}>
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
          <h2 style={{ margin: 0 }}>Nifty50 Smart Movers</h2>
          <div style={{ fontSize: 14, color: '#94a3b8' }}>
            Strongest Sector: <b style={{ color: '#22c55e' }}>{sector}</b>
          </div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            🟢 {advancers} Advancers | 🔴 {decliners} Decliners
          </div>
        </div>

        {/* SEARCH */}
        <input
          placeholder="Search stock..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: '10px 14px',
            borderRadius: 10,
            border: '1px solid #334155',
            background: '#020617',
            color: 'white',
            width: 220
          }}
        />
      </div>

      {/* LIVE BADGE */}
      <div style={{ marginBottom: 10, fontSize: 13, color: '#22c55e' }}>
        ● LIVE DATA (updates every 10s)
      </div>

      {/* PREMARKET SIGNALS */}
      <PremarketSignals symbol="^NSEI" />

      {/* TABLE */}
      <div
        style={{
          borderRadius: 14,
          border: '1px solid #334155',
          background: '#020617',
          maxHeight: 480,
          overflow: 'auto',
          marginBottom: 24
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          {/* HEADER */}
          <thead
            style={{
              background: '#020617',
              position: 'sticky',
              top: 0,
              zIndex: 2
            }}
          >
            <tr>
              {[
                ['Symbol'],
                ['Price'],
                ['%', 'percentChange'],
                ['Δ', 'priceChange'],
                ['Vol', 'volumeRatio'],
                ['VolSig'],
                ['VolTrend'],
                ['Sector'],
                ['Signal'],
                ['Momentum', 'momentum'],
                ['Trade'],
                ['Strike']
              ].map(([label, key]) => (
                <th
                  key={label}
                  onClick={() => key && toggleSort(key)}
                  style={{
                    padding: '14px 10px',
                    fontSize: 13,
                    cursor: key ? 'pointer' : 'default',
                    color: '#94a3b8',
                    borderBottom: '1px solid #334155',
                    background: '#020617',
                    position: 'sticky',
                    top: 0,
                    zIndex: 2
                  }}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>

          {/* BODY */}
          <tbody>
            {sorted.map((s, i) => {
              const m = momentumLabel(s.momentum);

              return (
                <tr
                  key={s.symbol}
                  onClick={() => setSelectedStock(s)}
                  style={{
                    cursor: 'pointer',
                    background:
                      s.momentum > 80 ? 'rgba(34,197,94,0.08)' : '#020617'
                  }}
                >
                  <td style={td}>
                    {s.symbol} {badge(s.breakout)}
                  </td>

                  <td style={td}>₹ {s.price}</td>

                  <td style={{ ...td, color: percentColor(s.percentChange) }}>
                    {s.percentChange}%
                  </td>

                  <td style={{ ...td, color: percentColor(s.priceChange) }}>
                    {s.priceChange > 0 ? '+' : ''}₹{s.priceChange}
                  </td>
                  <td style={td}>{s.volumeRatio}x</td>

                  <td
                    style={{
                      ...td,
                      color: volSignalColor(s.volumeSignal),
                      fontWeight: 'bold'
                    }}
                  >
                    {s.volumeSignal}
                  </td>
                  <td
                    style={{
                      ...td,
                      color: volTrendColor(s.volumeTrend),
                      fontWeight: 'bold'
                    }}
                  >
                    {s.volumeTrend}
                  </td>

                  <td style={td}>{s.sector}</td>

                  <td style={td}>
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        fontSize: 12,
                        background:
                          s.breakout === 'BREAKOUT'
                            ? '#16a34a'
                            : s.breakout === 'BREAKDOWN'
                              ? '#dc2626'
                              : '#475569'
                      }}
                    >
                      {s.breakout}
                    </span>
                  </td>

                  <td style={td}>
                    <span
                      style={{
                        background: m.color,
                        padding: '4px 8px',
                        borderRadius: 6,
                        fontSize: 12,
                        color: 'black',
                        fontWeight: 'bold'
                      }}
                    >
                      {m.text}
                    </span>
                  </td>

                  <td style={td}>
                    <b>{tradeSignal(s)}</b>
                  </td>

                  <td style={td}>{s.optionStrike}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selectedStock && (
        <StockModal
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  );
}

const td = {
  padding: '12px 10px',
  fontSize: 14,
  textAlign: 'center'
};
