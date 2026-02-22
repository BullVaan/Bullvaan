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
        border: '2px solid #334155',
        borderRadius: 10,
        padding: 18,
        marginBottom: 18,
        maxWidth: 860
      }}
    >
      {/* HEADER ROW */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
          flexWrap: 'wrap',
          gap: 10
        }}
      >
        {/* Signal */}
        <div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Signal</div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: signalColor[recommendation.type]
            }}
          >
            {signal}
          </div>
        </div>

        {/* Expiry */}
        <select
          value={selectedExpiry}
          onChange={(e) => setSelectedExpiry(e.target.value)}
          style={selectStyle}
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

        {/* Price */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: '#64748b' }}>{config.name}</div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            ₹{Math.round(price)}
          </div>
        </div>
      </div>

      {/* OPTION BOXES */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 8,
          marginBottom: 10,
          flexWrap: 'wrap'
        }}
      >
        <MiniCard title="ATM" value={recommendation.atm} color="#3b82f6" />
        <MiniCard title="OTM" value={recommendation.otm} color="#a855f7" />
        <MiniCard
          title="BEST"
          value={recommendation.suggested}
          color="#10b981"
          highlight
        />
      </div>

      {/* BUY BUTTON CENTER */}
      <div style={{ textAlign: 'center' }}>
        {recommendation.type !== 'WAIT' ? (
          <button
            style={{
              padding: '8px 20px',
              background: signalColor[recommendation.type],
              border: 'none',
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
              minWidth: 180
            }}
          >
            BUY {recommendation.suggested}
          </button>
        ) : (
          <div style={{ fontSize: 12, color: '#64748b' }}>
            Waiting for signal…
          </div>
        )}
      </div>
    </div>
  );
}

const selectStyle = {
  padding: '6px 10px',
  borderRadius: 6,
  background: '#020617',
  color: 'white',
  border: '1px solid #475569',
  fontSize: 12
};

function MiniCard({ title, value, color, highlight }) {
  return (
    <div
      style={{
        background: '#020617',
        border: `1px solid ${color}`,
        borderRadius: 6,
        padding: '6px 10px',
        textAlign: 'center',
        minWidth: 90,
        boxShadow: highlight ? `0 0 6px ${color}` : 'none'
      }}
    >
      <div style={{ fontSize: 9, color }}>{title}</div>
      <div style={{ fontSize: 13, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
