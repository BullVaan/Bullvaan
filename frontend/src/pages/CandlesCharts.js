import React, { useEffect, useRef, useState } from 'react';

import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';

const indexSymbolList = ['NIFTY', 'BANKNIFTY', 'SENSEX'];
const intervalOptions = [
  { label: '1 min', value: '1m' },
  { label: '5 min', value: '5m' },
  { label: '15 min', value: '15m' }
];

export default function CandlesCharts() {
  const chartContainerRef = useRef(null);
  const chartInstance = useRef(null);
  const [tf, setTf] = useState('5m');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pattern, setPattern] = useState(null);
  const [symbol, setSymbol] = useState('NIFTY'); // Default index
  const [chartKey, setChartKey] = useState(0); // force remount

  useEffect(() => {
    setLoading(true);
    fetch(`http://localhost:8000/candles?symbol=${symbol}&interval=${tf}`)
      .then((res) => res.json())
      .then((data) => {
        setLoading(false);
        if (!Array.isArray(data)) {
          setError('Failed to load chart data');
          return;
        }
        // Remove chart only if not already disposed
        if (chartInstance.current && chartInstance.current.remove) {
          try {
            chartInstance.current.remove();
          } catch (e) {}
        }
        const chart = createChart(chartContainerRef.current, {
          height: 500,
          layout: {
            background: { color: '#18181b' },
            textColor: '#fff'
          },
          grid: {
            vertLines: { color: '#334155' },
            horzLines: { color: '#334155' }
          },
          timeScale: { timeVisible: true }
        });
        chartInstance.current = chart;

        // Candles
        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#22c55e',
          downColor: '#ef4444',
          wickUpColor: '#22c55e',
          wickDownColor: '#ef4444'
        });
        candleSeries.setData(data);

        // Support/Resistance lines
        drawSRLines(chart, data);

        // Pattern detection
        const detected = detectPattern(data);
        setPattern(detected);
      })
      .catch(() => {
        setLoading(false);
        setError('Failed to load chart data');
      });
    setChartKey((k) => k + 1);
    return () => {
      if (chartInstance.current && chartInstance.current.remove) {
        try {
          chartInstance.current.remove();
        } catch (e) {}
      }
    };
  }, [symbol, tf]);

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

  function detectPattern(candles) {
    if (!candles || candles.length < 2) return null;
    const last = candles[candles.length - 1];
    const body = Math.abs(last.close - last.open);
    const lowerWick =
      last.open < last.close ? last.open - last.low : last.close - last.low;
    if (body < (last.high - last.low) * 0.3 && lowerWick > body * 2) {
      return { name: 'Hammer', signal: 'Bullish reversal' };
    }
    return null;
  }

  return (
    <div style={{ padding: 32 }}>
      <h1>Charts</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        {indexSymbolList.map((idx) => (
          <button
            key={idx}
            onClick={() => setSymbol(idx)}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: symbol === idx ? '#22c55e' : '#020617',
              color: symbol === idx ? 'black' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            {idx}
          </button>
        ))}
        {intervalOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setTf(opt.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: tf === opt.value ? '#22c55e' : '#020617',
              color: tf === opt.value ? 'black' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <div
        key={chartKey}
        ref={chartContainerRef}
        style={{
          width: '100%',
          height: 500,
          background: '#18181b',
          borderRadius: 8
        }}
      />
      {loading && <p>Loading chart...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {pattern && (
        <div
          style={{
            marginTop: 24,
            padding: 16,
            background: '#0f172a',
            color: '#22c55e',
            borderRadius: 8
          }}
        >
          <strong>{pattern.name} pattern detected!</strong>
          <div>Signal: {pattern.signal}</div>
        </div>
      )}
      {!pattern && !loading && (
        <div
          style={{
            marginTop: 24,
            padding: 16,
            background: '#0f172a',
            color: '#fff',
            borderRadius: 8
          }}
        >
          No candlestick pattern detected in the latest candle.
        </div>
      )}
    </div>
  );
}
