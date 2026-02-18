import { useState } from 'react';

export default function OptionSuggestion({ signal, price, symbol }) {
  const [selectedExpiry, setSelectedExpiry] = useState('weekly');

  const symbolConfig = {
    '^NSEI': { name: 'NIFTY 50', interval: 100, expiryDays: [3, 10, 17] },
    '^NSEBANK': { name: 'BANK NIFTY', interval: 100, expiryDays: [2, 9, 16] },
    '^BSESN': { name: 'SENSEX', interval: 100, expiryDays: [3, 10, 17] }
  };

  const config = symbolConfig[symbol] || {
    name: symbol,
    interval: 100,
    expiryDays: [7]
  };

  // Calculate strikes
  const roundToInterval = (num, interval) =>
    Math.round(num / interval) * interval;
  const atmStrike = roundToInterval(price, config.interval);
  const otmCall = atmStrike + config.interval; // Higher call = OTM
  const otmPut = atmStrike - config.interval; // Lower put = OTM

  // Get today's date for calculating expiry
  const today = new Date();
  const getExpiryDate = (daysAhead) => {
    const date = new Date(today);
    date.setDate(date.getDate() + daysAhead);
    return date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
  };

  // Determine recommended option based on signal
  const getRecommendation = () => {
    if (signal === 'BUY') {
      return {
        type: 'CALL',
        atm: `${atmStrike} CE`,
        otm: `${otmCall} CE`,
        logic: 'Bullish: Buy CALL options',
        riskNote: 'OTM = Lower premium, higher leverage',
        suggested: `${atmStrike} CE`
      };
    } else if (signal === 'SELL') {
      return {
        type: 'PUT',
        atm: `${atmStrike} PE`,
        otm: `${otmPut} PE`,
        logic: 'Bearish: Buy PUT options',
        riskNote: 'OTM = Lower premium, higher leverage',
        suggested: `${atmStrike} PE`
      };
    } else {
      return {
        type: 'WAIT',
        atm: '—',
        otm: '—',
        logic: 'Neutral: Wait for clearer signal',
        riskNote: 'No clear direction',
        suggested: 'HOLD'
      };
    }
  };

  const recommendation = getRecommendation();
  const expiryDate = getExpiryDate(
    config.expiryDays[
      selectedExpiry === 'weekly' ? 0 : selectedExpiry === 'monthly' ? 1 : 2
    ] || 7
  );

  const signalColor = {
    BUY: '#16a34a',
    SELL: '#dc2626',
    WAIT: '#eab308'
  };

  return (
    <div
      style={{
        background: '#020617',
        border: '2px solid #475569',
        borderRadius: 12,
        padding: 20,
        marginBottom: 30,
        boxShadow: '0 0 15px rgba(0,0,0,0.5)'
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>Overall Signal</div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 'bold',
              color: signalColor[recommendation.type]
            }}
          >
            {signal}
          </div>
        </div>

        {/* Expiry Selector */}
        <div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
            Expiry
          </div>
          <select
            value={selectedExpiry}
            onChange={(e) => setSelectedExpiry(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: '#0f172a',
              color: 'white',
              border: '1px solid #475569',
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            <option value="weekly">
              Weekly ({getExpiryDate(config.expiryDays[0])})
            </option>
            <option value="monthly">
              Monthly ({getExpiryDate(config.expiryDays[1])})
            </option>
            <option value="next">
              Next ({getExpiryDate(config.expiryDays[2])})
            </option>
          </select>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>{config.name}</div>
          <div style={{ fontSize: 18, fontWeight: 'bold', color: '#22c55e' }}>
            ₹ {Math.round(price)}
          </div>
        </div>
      </div>

      {/* Signal Logic */}
      <div
        style={{
          background: '#0f172a',
          padding: 12,
          borderRadius: 8,
          marginBottom: 15
        }}
      >
        <div style={{ fontSize: 13, color: '#cbd5e1' }}>
          {recommendation.logic}
        </div>
      </div>

      {/* Options Recommendation Grid */}
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}
      >
        {/* ATM */}
        <div
          style={{
            background: '#1e3a5f',
            padding: 12,
            borderRadius: 8,
            border: '1px solid #3b82f6'
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: '#60a5fa',
              marginBottom: 4,
              fontWeight: 'bold'
            }}
          >
            ATM (Balanced)
          </div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 'bold',
              color: '#ffffff',
              marginBottom: 4
            }}
          >
            {recommendation.atm}
          </div>
          <div style={{ fontSize: 10, color: '#60a5fa' }}>Medium premium</div>
        </div>

        {/* OTM (Higher Leverage) */}
        <div
          style={{
            background: '#3a1e4e',
            padding: 12,
            borderRadius: 8,
            border: '1px solid #a855f7'
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: '#d946ef',
              marginBottom: 4,
              fontWeight: 'bold'
            }}
          >
            OTM (High Leverage)
          </div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 'bold',
              color: '#ffffff',
              marginBottom: 4
            }}
          >
            {recommendation.otm}
          </div>
          <div style={{ fontSize: 10, color: '#d946ef' }}>Lower premium</div>
        </div>

        {/* Suggested */}
        <div
          style={{
            background: '#1e3a2e',
            padding: 12,
            borderRadius: 8,
            border: '2px solid #10b981'
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: '#10b981',
              marginBottom: 4,
              fontWeight: 'bold'
            }}
          >
            ✅ Suggested
          </div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 'bold',
              color: '#ffffff',
              marginBottom: 4
            }}
          >
            {recommendation.suggested}
          </div>
          <div style={{ fontSize: 10, color: '#10b981' }}>Best risk/reward</div>
        </div>
      </div>

      {/* Risk Note */}
      <div
        style={{
          marginTop: 12,
          padding: 10,
          background: '#0f172a',
          borderRadius: 6,
          borderLeft: '3px solid #f59e0b'
        }}
      >
        <div style={{ fontSize: 11, color: '#fbbf24' }}>
          💡 {recommendation.riskNote}
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 10, marginTop: 15 }}>
        {recommendation.type !== 'WAIT' && (
          <>
            <button
              style={{
                flex: 1,
                padding: '12px 15px',
                background: signalColor[recommendation.type],
                border: 'none',
                borderRadius: 6,
                color: 'black',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontSize: 13,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              BUY {recommendation.type} → {recommendation.suggested}
            </button>
            <button
              style={{
                flex: 1,
                padding: '12px 15px',
                background: 'rgba(255, 255, 255, 0.1)',
                border: `2px solid ${signalColor[recommendation.type]}`,
                borderRadius: 6,
                color: '#ffffff',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontSize: 13,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              View Chart
            </button>
          </>
        )}
        {recommendation.type === 'WAIT' && (
          <div
            style={{
              flex: 1,
              padding: '10px',
              textAlign: 'center',
              color: '#94a3b8'
            }}
          >
            Waiting for BUY or SELL signal...
          </div>
        )}
      </div>
    </div>
  );
}
