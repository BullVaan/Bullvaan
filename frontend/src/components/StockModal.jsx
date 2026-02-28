import { X } from 'lucide-react';
import { useEffect, useState, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries
} from 'lightweight-charts';

export default function StockModal({ stock, onClose }) {
  const chartContainerRef = useRef(null);
  const chartInstance = useRef(null);
  const [tf, setTf] = useState('5m');

  /* ---------- SUPPORT / RESISTANCE ---------- */
  function drawSRLines(chart, data) {
    if (!data || data.length < 10) return;

    const highs = data.map((d) => d.high);
    const lows = data.map((d) => d.low);

    const resistance = Math.max(...highs.slice(-20));
    const support = Math.min(...lows.slice(-20));

    const resLine = chart.addSeries(LineSeries, {
      color: '#ef4444',
      lineWidth: 1,
      lineStyle: 2
    });

    resLine.setData([
      { time: data[0].time, value: resistance },
      { time: data[data.length - 1].time, value: resistance }
    ]);

    const supLine = chart.addSeries(LineSeries, {
      color: '#22c55e',
      lineWidth: 1,
      lineStyle: 2
    });

    supLine.setData([
      { time: data[0].time, value: support },
      { time: data[data.length - 1].time, value: support }
    ]);
  }

  /* ---------- CHART ---------- */
  useEffect(() => {
    if (!stock) return;
    if (chartInstance.current && chartInstance.current.remove) {
      try {
        chartInstance.current.remove();
      } catch (e) {}
    }
    const chart = createChart(chartContainerRef.current, {
      height: 300,
      layout: {
        background: { color: '#020617' },
        textColor: '#94a3b8'
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' }
      },
      timeScale: { timeVisible: true }
    });
    chartInstance.current = chart;
    /* CANDLES */
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444'
    });
    /* VOLUME */
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: ''
    });
    chart.priceScale('').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 }
    });
    fetch(`http://localhost:8000/candles?symbol=${stock.symbol}&interval=${tf}`)
      .then((res) => res.json())
      .then((data) => {
        candleSeries.setData(data);
        if (data[0] && data[0].volume !== undefined) {
          volumeSeries.setData(
            data.map((d) => ({
              time: d.time,
              value: d.volume,
              color: d.close > d.open ? '#22c55e' : '#ef4444'
            }))
          );
        }
        drawSRLines(chart, data);
      });
    return () => {
      if (chartInstance.current && chartInstance.current.remove) {
        try {
          chartInstance.current.remove();
        } catch (e) {}
      }
    };
  }, [stock, tf]);

  if (!stock) return null;

  const percentColor =
    stock.percentChange > 0
      ? '#22c55e'
      : stock.percentChange < 0
        ? '#ef4444'
        : '#94a3b8';

  return (
    <div style={overlay} onClick={onClose}>
      <div style={dialog} onClick={(e) => e.stopPropagation()}>
        <div style={header}>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{stock.symbol}</div>
          <X size={22} style={{ cursor: 'pointer' }} onClick={onClose} />
        </div>

        <div style={body}>
          <div style={{ textAlign: 'center', marginBottom: 18 }}>
            <div style={{ fontSize: 30, fontWeight: 'bold' }}>
              ₹ {stock.price}
            </div>
            <div style={{ color: percentColor, fontWeight: 600 }}>
              {stock.percentChange}% ({stock.priceChange})
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            {['1m', '5m', '15m'].map((t) => (
              <button
                key={t}
                onClick={() => setTf(t)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: '1px solid #334155',
                  background: tf === t ? '#22c55e' : '#020617',
                  color: tf === t ? 'black' : '#94a3b8',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                {t}
              </button>
            ))}
          </div>

          <div ref={chartContainerRef} />
        </div>
      </div>
    </div>
  );
}

/* ---------- styles ---------- */

const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.75)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 999,
  backdropFilter: 'blur(4px)'
};

const dialog = {
  width: 'min(720px, 92vw)',
  background: '#020617',
  borderRadius: 16,
  border: '1px solid #334155',
  display: 'flex',
  flexDirection: 'column',
  animation: 'scaleIn .18s ease'
};

const header = {
  padding: '12px 16px',
  borderBottom: '1px solid #334155',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center'
};

const body = {
  padding: '18px 20px',
  overflowY: 'auto'
};
