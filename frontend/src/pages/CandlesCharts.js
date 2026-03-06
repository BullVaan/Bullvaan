import { useEffect, useRef, useState } from 'react';
import { FaArrowUp } from 'react-icons/fa';
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
  const [symbol, setSymbol] = useState('NIFTY');
  const [chartKey, setChartKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError('');
    fetch(`/candles?symbol=${symbol}&interval=${tf}`)
      .then((res) => res.json())
      .then((data) => {
        setLoading(false);
        if (!Array.isArray(data) || data.length === 0) {
          setError('Failed to load chart data');
          return;
        }
        setError('');
        if (chartInstance.current && chartInstance.current.remove) {
          try {
            chartInstance.current.remove();
          } catch (e) {}
        }
        // Convert all candle times to IST (add 5.5 hours)
        const dataIST = data.map((candle) => ({
          ...candle,
          time: candle.time + 19800 // 5.5 hours in seconds
        }));
        // Filter to regular market hours (9:15 AM to 3:30 PM IST)
        const dataISTFiltered = dataIST.filter((candle) => {
          const d = new Date(candle.time * 1000);
          const hour = d.getHours();
          const minute = d.getMinutes();
          // Market open: 9:15, close: 15:30
          if (hour < 9 || hour > 15) return false;
          if (hour === 9 && minute < 15) return false;
          if (hour === 15 && minute > 30) return false;
          return true;
        });
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
        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#22c55e',
          downColor: '#ef4444',
          wickDownColor: '#ef4444'
        });
        candleSeries.setData(dataISTFiltered);
        drawSRLines(chart, dataISTFiltered);
        const detected = detectPattern(dataISTFiltered);
        let detectedTime = null;
        if (detected) {
          detectedTime = dataISTFiltered[dataISTFiltered.length - 1].time;
        }
        setPattern(detected ? { ...detected, time: detectedTime } : null);
        if (detected) {
          candleSeries.setMarkers([
            {
              time: dataISTFiltered[dataISTFiltered.length - 1].time,
              position: 'belowBar',
              color: '#fbbf24',
              shape: 'arrowUp',
              text: detected.name,
              size: 2
            }
          ]);
        } else {
          candleSeries.setMarkers([]);
        }
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
    // Use last 20 candles for pivots
    const recent = data.slice(-20);
    const highs = recent.map((d) => d.high);
    const lows = recent.map((d) => d.low);
    const closes = recent.map((d) => d.close);
    const high = Math.max(...highs);
    const low = Math.min(...lows);
    const close = closes[closes.length - 1];
    // Pivot point
    const pivot = (high + low + close) / 3;
    // Immediate support and resistance
    const r1 = 2 * pivot - low;
    const s1 = 2 * pivot - high;
    const levels = [
      { value: r1, color: '#fde047', label: 'R1' },
      { value: s1, color: '#bbf7d0', label: 'S1' },
    ];
    levels.forEach(({ value, color, label }) => {
      const line = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        lineStyle: 2
      });
      line.setData([
        { time: data[0].time, value },
        { time: data[data.length - 1].time, value }
      ]);
      if (line.createPriceLine) {
        line.createPriceLine({
          price: value,
          color,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: label
        });
      }
    });
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
      {pattern && (
        <div
          style={{
            marginBottom: 18,
            padding: 16,
            background: '#0f172a',
            color: '#fbbf24',
            borderRadius: 8,
            fontWeight: 600,
            fontSize: 18,
            display: 'inline-block'
          }}
        >
          <FaArrowUp
            style={{
              color: '#fbbf24',
              marginRight: 8,
              verticalAlign: 'middle'
            }}
          />
          {pattern.name} pattern detected!
          <span style={{ marginLeft: 12 }}>Signal: {pattern.signal}</span>
          {pattern.time && (
            <span
              style={{
                marginLeft: 12,
                color: '#fff',
                fontWeight: 400,
                fontSize: 14
              }}
            >
              at{' '}
              {new Date(pattern.time * 1000).toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata'
              })}{' '}
              IST
            </span>
          )}
        </div>
      )}
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
          borderRadius: 8,
          overflowX: 'auto',
          whiteSpace: 'nowrap'
        }}
      />
      {loading && <p>Loading chart...</p>}
      {error && !loading && chartKey === 0 && (
        <p style={{ color: 'red' }}>{error}</p>
      )}
      {/* Pattern signal now shown above chart */}
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
