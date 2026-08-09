import { useEffect, useState, useCallback } from 'react';
import MarketTicker from '../components/dashboard/MarketTicker';
import { getAuthHeaders } from '../utils/auth';
import { API_BASE_URL } from '../utils/api';

const INDEX_OPTIONS = {
  '^NSEI': 'NIFTY 50',
  '^NSEBANK': 'BANK NIFTY',
  '^BSESN': 'Sensex'
};

const TIMEFRAME_OPTIONS = [
  { value: '5m', label: '5m - Scalping' },
  { value: '15m', label: '15m - Trend' },
  { value: '30m', label: '30m - Swing' }
];

const ROLE_COLORS = {
  BUY: '#22c55e',
  SELL: '#ef4444',
  NEUTRAL: '#eab308'
};

export default function TestingStrategies() {
  const [selectedSymbol, setSelectedSymbol] = useState('^NSEI');
  const [selectedTimeframe, setSelectedTimeframe] = useState('15m');
  const [signalsByRole, setSignalsByRole] = useState({});
  const [price, setPrice] = useState('-');
  const [consensus, setConsensus] = useState('NEUTRAL');
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = 'Testing Strategies | BullVaan';
  }, []);

  const fetchSignals = useCallback(async (symbol, timeframe) => {
    try {
      setLoading(true);
      setError('');

      const res = await fetch(
        `${API_BASE_URL}/signals?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,
        { headers: getAuthHeaders() }
      );
      const data = await res.json();

      if (data.error) {
        setError(data.error);
        setSignalsByRole({});
        setConsensus('NEUTRAL');
        setPrice('-');
      } else {
        setSignalsByRole(data.signals_by_role || {});
        setConsensus(data.consensus || 'NEUTRAL');
        setPrice(data.price ?? '-');
      }
      setLoaded(true);
    } catch (err) {
      setError('Failed to load signals.');
      setSignalsByRole({});
      setConsensus('NEUTRAL');
      setPrice('-');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSymbolChange = (e) => {
    setSelectedSymbol(e.target.value);
  };

  const handleTimeframeChange = (e) => {
    setSelectedTimeframe(e.target.value);
  };

  useEffect(() => {
    fetchSignals(selectedSymbol, selectedTimeframe);
    const interval = setInterval(() => {
      fetchSignals(selectedSymbol, selectedTimeframe);
    }, 15 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchSignals, selectedSymbol, selectedTimeframe]);

  const renderRoleCard = (role, items) => (
    <div
      key={role}
      style={{
        flex: '1 1 280px',
        minWidth: 280,
        background: '#020617',
        border: '1px solid #334155',
        borderRadius: 16,
        padding: 20,
        boxShadow: '0 0 15px rgba(0,0,0,0.4)'
      }}
    >
      <div style={{ fontSize: 18, fontWeight: 700, color: '#f8fafc', marginBottom: 14 }}>
        {role}
      </div>
      {items.map((signal) => (
        <div
          key={signal.name}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 14px',
            marginBottom: 10,
            borderRadius: 10,
            background: '#0f172a',
            border: '1px solid #334155'
          }}
        >
          <span style={{ color: '#cbd5f5' }}>{signal.name}</span>
          <span style={{ color: ROLE_COLORS[signal.signal] || '#94a3b8', fontWeight: 700 }}>
            {signal.signal}
          </span>
        </div>
      ))}
      {!items.length && (
        <div style={{ color: '#64748b', fontSize: 13 }}>
          No strategy signals loaded.
        </div>
      )}
    </div>
  );

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ width: '100%' }}>
        <MarketTicker />
      </div>

      <div style={{ width: '100%', maxWidth: 1100, padding: 20 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 15,
            flexWrap: 'wrap'
          }}
        >
          <div
            style={{
              background: '#020617',
              border: '1px solid #334155',
              padding: '14px 22px',
              borderRadius: 12,
              width: 250,
              boxShadow: '0 0 15px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
              Select Index
            </div>
            <select
              value={selectedSymbol}
              onChange={handleSymbolChange}
              style={{
                width: '100%',
                padding: 10,
                borderRadius: 8,
                background: '#020617',
                color: 'white',
                border: '1px solid #475569',
                fontSize: 14,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {Object.entries(INDEX_OPTIONS).map(([symbol, label]) => (
                <option key={symbol} value={symbol}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div
            style={{
              background: '#020617',
              border: '1px solid #334155',
              padding: '14px 22px',
              borderRadius: 12,
              width: 250,
              boxShadow: '0 0 15px rgba(0,0,0,0.4)'
            }}
          >
            <div style={{ fontSize: 15, color: '#94a3b8', marginBottom: 6 }}>
              Select Timeframe
            </div>
            <select
              value={selectedTimeframe}
              onChange={handleTimeframeChange}
              style={{
                width: '100%',
                padding: 10,
                borderRadius: 8,
                background: '#020617',
                color: 'white',
                border: '1px solid #475569',
                fontSize: 14,
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {TIMEFRAME_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div style={{ color: '#ef4444', marginTop: 16, textAlign: 'center' }}>{error}</div>
        )}

        {loading && (
          <div style={{ color: '#94a3b8', marginTop: 16, textAlign: 'center' }}>
            Loading strategy signals...
          </div>
        )}

        {loaded && !loading && (
          <div
            style={{
              display: 'flex',
              gap: 20,
              flexWrap: 'wrap',
              justifyContent: 'center',
              marginTop: 24
            }}
          >
            {renderRoleCard('Trend', signalsByRole.Trend || [])}
          </div>
        )}
      </div>
    </div>
  );
}
