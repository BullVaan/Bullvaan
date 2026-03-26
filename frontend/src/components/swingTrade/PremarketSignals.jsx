import { useEffect, useState, useCallback } from 'react';
import { getAuthHeaders } from '../../utils/auth';
import { API_BASE_URL } from '../../utils/api';

const BACKEND_URL = API_BASE_URL;

// NSE holidays and non-trading days
const MARKET_HOLIDAYS = {
  2026: [
    '01-26', // Republic Day
    '03-25', // Holi
    '04-02', // Good Friday
    '04-21', // Ram Navami
    '05-15', // Eid
    '08-15', // Independence Day
    '09-16', // Milad-un-Nabi
    '10-02', // Gandhi Jayanti
    '10-25', // Dussehra
    '11-11', // Diwali
    '12-25' // Christmas
  ]
};

function isMarketOpen() {
  // Convert to IST (UTC+5:30)
  const now = new Date();
  const istTime = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);

  // Get day and date in IST using UTC methods (since we've already adjusted the time)
  const day = istTime.getUTCDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday
  const month = String(istTime.getUTCMonth() + 1).padStart(2, '0');
  const date = String(istTime.getUTCDate()).padStart(2, '0');
  const year = istTime.getUTCFullYear();
  const dateStr = `${month}-${date}`;

  // Check if weekend
  if (day === 0 || day === 6) {
    return false;
  }

  // Check if holiday
  const holidays = MARKET_HOLIDAYS[year] || [];
  if (holidays.includes(dateStr)) {
    return false;
  }

  return true;
}

export default function PremarketSignals({ symbol = '^NSEI' }) {
  const [signals, setSignals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [marketClosed, setMarketClosed] = useState(false);

  const fetchPremarketSignals = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(
        `${BACKEND_URL}/premarket/signals?symbol=${symbol}`,
        { headers: getAuthHeaders() }
      );
      if (!res.ok) throw new Error('Failed to fetch premarket signals');

      const data = await res.json();
      setSignals(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setSignals(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    // Check if market is open
    if (!isMarketOpen()) {
      setMarketClosed(true);
      setLoading(false);
      return;
    }

    setMarketClosed(false);
    fetchPremarketSignals();
  }, [symbol, fetchPremarketSignals]);

  if (loading) {
    return (
      <div
        style={{
          padding: '12px 16px',
          background: '#1e293b',
          borderRadius: '6px',
          textAlign: 'center',
          color: '#94a3b8'
        }}
      >
        Loading premarket analysis...
      </div>
    );
  }

  if (marketClosed) {
    const today = new Date();
    const day = today.getDay();
    const dayName = [
      'Sunday',
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday'
    ][day];

    return (
      <div
        style={{
          padding: '16px',
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          border: '2px solid #94a3b8',
          borderRadius: '8px',
          marginBottom: '16px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '24px' }}>🏙️</span>
          <div>
            <div
              style={{ color: '#94a3b8', fontSize: '14px', fontWeight: 'bold' }}
            >
              MARKET CLOSED
            </div>
            <div
              style={{ color: '#cbd5e1', fontSize: '12px', marginTop: '4px' }}
            >
              {dayName} is not a trading day. NSE market will reopen on Monday.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: '16px',
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          border: '2px solid #ef4444',
          borderRadius: '8px',
          marginBottom: '16px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '24px' }}>⚠️</span>
          <div>
            <div
              style={{ color: '#ef4444', fontSize: '14px', fontWeight: 'bold' }}
            >
              Could not load premarket data
            </div>
            <div
              style={{ color: '#cbd5e1', fontSize: '12px', marginTop: '4px' }}
            >
              Backend may be temporarily unavailable. Try refreshing the page.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!signals) return null;

  const signalColor =
    {
      BUY: '#22c55e',
      SELL: '#ef4444',
      NEUTRAL: '#eab308'
    }[signals.signal] || '#94a3b8';

  const signalIcon =
    {
      BUY: '📈',
      SELL: '📉',
      NEUTRAL: '⏸️'
    }[signals.signal] || '●';

  const gapColor = signals.gap_percent >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div
      style={{
        padding: '16px',
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        border: `2px solid ${signalColor}`,
        borderRadius: '8px',
        marginBottom: '16px'
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px'
        }}
      >
        <h3
          style={{
            color: 'white',
            margin: 0,
            fontSize: '14px',
            fontWeight: 'bold'
          }}
        >
          📊 PREMARKET ANALYSIS
        </h3>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>
          {new Date(signals.timestamp).toLocaleTimeString('en-IN')}
        </span>
      </div>

      {/* Main Signal */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px',
          background: 'rgba(0,0,0,0.3)',
          borderRadius: '6px',
          marginBottom: '12px'
        }}
      >
        <span style={{ fontSize: '24px' }}>{signalIcon}</span>
        <div style={{ flex: 1 }}>
          <div
            style={{ color: signalColor, fontSize: '18px', fontWeight: 'bold' }}
          >
            {signals.signal} ({signals.strength})
          </div>
          <div style={{ color: '#cbd5e1', fontSize: '12px', marginTop: '4px' }}>
            {signals.reason}
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          marginBottom: '12px'
        }}
      >
        {/* Gap Analysis */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            PRICE GAP
          </div>
          <div
            style={{ color: gapColor, fontSize: '14px', fontWeight: 'bold' }}
          >
            {signals.gap_percent > 0 ? '+' : ''}
            {signals.gap_percent}%
          </div>
          <div style={{ fontSize: '10px', color: '#cbd5e1', marginTop: '2px' }}>
            {signals.current_open > signals.previous_close
              ? 'Gap Up'
              : 'Gap Down'}
          </div>
        </div>

        {/* Previous Close */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            PREVIOUS CLOSE
          </div>
          <div
            style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 'bold' }}
          >
            ₹{signals.previous_close}
          </div>
        </div>

        {/* Support Level */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            SUPPORT
          </div>
          <div
            style={{ color: '#22c55e', fontSize: '14px', fontWeight: 'bold' }}
          >
            ₹{signals.support_level}
          </div>
        </div>

        {/* Resistance Level */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            RESISTANCE
          </div>
          <div
            style={{ color: '#ef4444', fontSize: '14px', fontWeight: 'bold' }}
          >
            ₹{signals.resistance_level}
          </div>
        </div>

        {/* Volume Trend */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            YESTERDAY VOLUME
          </div>
          <div
            style={{ color: '#3b82f6', fontSize: '14px', fontWeight: 'bold' }}
          >
            {(signals.yesterday_volume / 1000000).toFixed(1)}M
          </div>
        </div>

        {/* Avg Volume */}
        <div
          style={{
            padding: '10px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '4px'
          }}
        >
          <div
            style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}
          >
            AVG VOLUME (10d)
          </div>
          <div
            style={{ color: '#3b82f6', fontSize: '14px', fontWeight: 'bold' }}
          >
            {(signals.prev_volume_avg / 1000000).toFixed(1)}M
          </div>
        </div>
      </div>

      {/* Recommendation */}
      <div
        style={{
          padding: '10px',
          background: signalColor + '15',
          border: `1px solid ${signalColor}`,
          borderRadius: '4px',
          fontSize: '12px',
          color: signalColor
        }}
      >
        💡 <strong>Action:</strong>{' '}
        {getRecommendation(signals.signal, signals.strength)}
      </div>
    </div>
  );
}

function getRecommendation(signal, strength) {
  if (signal === 'BUY') {
    if (strength === 'STRONG')
      return 'Strong buy setup - Good risk/reward for CALL options';
    if (strength === 'MEDIUM')
      return 'Decent buy setup - Wait for retracement into support';
    return 'Mild bullish bias - Avoid shorts, consider entering on dips';
  }
  if (signal === 'SELL') {
    if (strength === 'STRONG')
      return 'Strong sell setup - Good risk/reward for PUT options';
    if (strength === 'MEDIUM')
      return 'Decent sell setup - Wait for bounce into resistance';
    return 'Mild bearish bias - Avoid longs, consider entering on rallies';
  }
  return 'No clear setup - Wait for better entry or watch for breakout';
}
