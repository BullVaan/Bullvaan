import { X } from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend
} from 'chart.js';
import { useEffect, useState } from 'react';

ChartJS.register(
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend
);

export default function StockModal({ stock, onClose }) {
  const [chartData, setChartData] = useState(null);

  /* ---------------- FETCH CHART DATA ---------------- */
  useEffect(() => {
    if (!stock) return;

    fetch(`http://127.0.0.1:8000/history?symbol=${stock.symbol}`)
      .then((res) => res.json())
      .then((data) => {
        setChartData({
          labels: data.map((d) => d.time),
          datasets: [
            {
              label: stock.symbol,
              data: data.map((d) => d.price),
              tension: 0.4,

              borderColor: '#22c55e', // line color
              backgroundColor: 'rgba(34,197,94,0.2)', // fill color
              pointRadius: 0,
              borderWidth: 2
            }
          ]
        });
      })
      .catch(() => setChartData(null));
  }, [stock]);

  if (!stock) return null;

  const percentColor =
    stock.percentChange > 0
      ? '#22c55e'
      : stock.percentChange < 0
        ? '#ef4444'
        : '#94a3b8';

  const trade =
    stock.breakout === 'BREAKOUT' && stock.momentum > 70
      ? 'BUY CALL'
      : stock.breakout === 'BREAKDOWN' && stock.momentum > 70
        ? 'BUY PUT'
        : 'WATCH';

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        {/* HEADER */}
        <div style={header}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 'bold' }}>
              {stock.symbol}
            </div>
            <div style={{ fontSize: 13, color: '#94a3b8' }}>{stock.sector}</div>
          </div>

          <X size={22} style={{ cursor: 'pointer' }} onClick={onClose} />
        </div>

        {/* PRICE */}
        <div style={{ textAlign: 'center', margin: '18px 0' }}>
          <div style={{ fontSize: 32, fontWeight: 'bold' }}>
            ₹ {stock.price}
          </div>

          <div style={{ color: percentColor, fontWeight: 'bold' }}>
            {stock.percentChange}% ({stock.priceChange})
          </div>
        </div>

        {/* CHART */}
        <div style={{ marginBottom: 20 }}>
          {chartData ? (
            <Line
              data={chartData}
              options={{
                responsive: true,
                plugins: { legend: { display: false } },

                scales: {
                  x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: '#1e293b' }
                  },
                  y: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: '#1e293b' }
                  }
                }
              }}
            />
          ) : (
            <div style={{ textAlign: 'center', color: '#94a3b8' }}>
              Loading chart...
            </div>
          )}
        </div>

        {/* INFO GRID */}
        <div style={grid}>
          <Info label="Breakout" value={stock.breakout} />
          <Info label="Momentum" value={stock.momentum} />
          <Info label="Strike" value={stock.optionStrike} />
          <Info label="Trade" value={trade} />
        </div>

        {/* ACTION */}
        <button style={button}>Trade → {trade}</button>
      </div>
    </div>
  );
}

/* ---------- small info box ---------- */
function Info({ label, value }) {
  return (
    <div style={card}>
      <div style={{ fontSize: 12, color: '#94a3b8' }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 'bold' }}>{value}</div>
    </div>
  );
}

/* ---------- styles ---------- */

const overlay = {
  position: 'fixed',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
  background: 'rgba(0,0,0,0.7)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 999
};

const modal = {
  background: '#020617',
  padding: 24,
  borderRadius: 14,
  width: 460,
  border: '1px solid #334155'
};

const header = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center'
};

const grid = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 12,
  marginBottom: 18
};

const card = {
  background: '#0f172a',
  padding: 12,
  borderRadius: 8,
  textAlign: 'center'
};

const button = {
  width: '100%',
  padding: 14,
  borderRadius: 10,
  background: '#22c55e',
  border: 'none',
  fontWeight: 'bold',
  cursor: 'pointer',
  fontSize: 15
};
